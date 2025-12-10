"""TeamSpeak 3 服务器监控插件

支持多服务器监控、用户进出通知、定时状态推送等功能。
"""

import asyncio
import time
from dataclasses import dataclass
from queue import Empty, Queue

from astrbot.api import logger, star
from astrbot.api.event import AstrMessageEvent, filter

from .core import TS3_AVAILABLE, Notifier, TS3Client, TS3Monitor
from .core.ts3_client import ClientInfo
from .models import ServerInfo
from .storage import DataManager


@dataclass
class PendingNotification:
    """待发送的通知"""

    subscriber_settings: dict[str, bool]  # {umo -> at_all}
    message: str
    retry_count: int = 0


class Main(star.Star):
    """TeamSpeak 3 服务器监控插件

    命令列表:
    - /ts add <别名> <主机> <用户名> <密码> [端口] [虚拟服务器ID] - 添加服务器（管理员）
    - /ts del <别名> - 删除服务器（管理员）
    - /ts ls - 查看监控列表
    - /ts sub <别名> - 订阅通知
    - /ts unsub <别名> - 取消订阅
    - /ts mysub - 查看我的订阅
    - /ts status [别名] - 查看服务器状态
    - /ts join <别名> [on/off] - 切换加入通知（管理员）
    - /ts leave <别名> [on/off] - 切换离开通知（管理员）
    - /ts interval <别名> <分钟> - 设置状态推送间隔（管理员）
    - /ts restart [别名] - 重启监控（管理员）
    """

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        self.context = context

        # 主事件循环引用（用于子线程回调）
        self.loop: asyncio.AbstractEventLoop | None = None

        # 初始化模块
        self.data = DataManager()
        self.notifier = Notifier(context)
        self.monitors: dict[str, TS3Monitor] = {}

        # 通知队列
        self._notification_queue: Queue[PendingNotification] = Queue()
        self._queue_processor_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        """插件激活时启动所有监控"""
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.get_event_loop()

        if not TS3_AVAILABLE:
            logger.error("ts3 库未安装，TeamSpeak 监控插件无法正常工作")
            return

        # 启动通知队列处理任务
        self._queue_processor_task = asyncio.create_task(self._process_notification_queue())

        # 启动所有已保存服务器的监控
        for server_name in self.data.server_info.keys():
            self._start_monitor(server_name)

        logger.info(f"TeamSpeak 监控插件已启动，监控 {len(self.monitors)} 个服务器")

    async def terminate(self) -> None:
        """插件禁用时停止所有监控"""
        if self._queue_processor_task:
            self._queue_processor_task.cancel()
            try:
                await self._queue_processor_task
            except asyncio.CancelledError:
                pass

        # 使用 run_in_executor 避免 thread.join 阻塞事件循环
        loop = asyncio.get_running_loop()
        for monitor in self.monitors.values():
            await loop.run_in_executor(None, monitor.stop)
        self.monitors.clear()
        self.data.save()
        logger.info("TeamSpeak 监控插件已停止")

    # ==================== 监控管理 ====================

    def _start_monitor(self, server_name: str) -> bool:
        """启动单个服务器的监控"""
        if server_name in self.monitors:
            return True

        server_info = self.data.get_server(server_name)
        if not server_info:
            return False

        monitor = TS3Monitor(
            server_name=server_name,
            host=server_info.host,
            query_port=server_info.query_port,
            query_user=server_info.query_user,
            query_password=server_info.query_password,
            virtual_server_id=server_info.virtual_server_id,
            status_interval=server_info.status_interval,
            on_client_join=self._on_client_join,
            on_client_leave=self._on_client_leave,
            on_status_tick=self._on_status_tick,
        )
        if monitor.start():
            self.monitors[server_name] = monitor
            return True
        return False

    def _stop_monitor(self, server_name: str) -> None:
        """停止单个服务器的监控"""
        if server_name in self.monitors:
            self.monitors[server_name].stop()
            del self.monitors[server_name]

    async def _process_notification_queue(self) -> None:
        """处理通知队列的后台任务"""
        MAX_RETRIES = 5
        while True:
            try:
                await asyncio.sleep(1)

                pending_items: list[PendingNotification] = []
                while True:
                    try:
                        item = self._notification_queue.get_nowait()
                        pending_items.append(item)
                    except Empty:
                        break

                for item in pending_items:
                    try:
                        await self.notifier.send_to_subscribers(
                            item.subscriber_settings, item.message
                        )
                    except Exception as e:
                        item.retry_count += 1
                        if item.retry_count < MAX_RETRIES:
                            self._notification_queue.put(item)
                            logger.warning(
                                f"发送通知失败，将重试 ({item.retry_count}/{MAX_RETRIES}): {e}"
                            )
                        else:
                            logger.error(f"发送通知失败，已达最大重试次数: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"通知队列处理器出错: {e}")

    def _schedule_notification(
        self, subscriber_settings: dict[str, bool], message: str
    ) -> None:
        """安全地调度通知发送"""
        if not subscriber_settings:
            return

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.notifier.send_to_subscribers(subscriber_settings, message),
                self.loop,
            )
        else:
            logger.warning("事件循环暂时不可用，通知已加入队列")
            self._notification_queue.put(
                PendingNotification(subscriber_settings=subscriber_settings, message=message)
            )

    def _on_client_join(self, server_name: str, client: ClientInfo) -> None:
        """用户加入回调"""
        sub_configs = self.data.get_all_subscription_configs(server_name)
        if not sub_configs:
            return

        # 筛选开启加入通知的订阅者
        join_subscribers = {
            umo: False  # 加入通知不 @全体
            for umo, config in sub_configs.items()
            if config.notify_join
        }

        if not join_subscribers:
            return

        notification = self.notifier.build_join_notification(server_name, client)
        self._schedule_notification(join_subscribers, notification)

    def _on_client_leave(self, server_name: str, client: ClientInfo) -> None:
        """用户离开回调"""
        sub_configs = self.data.get_all_subscription_configs(server_name)
        if not sub_configs:
            return

        # 筛选开启离开通知的订阅者
        leave_subscribers = {
            umo: False  # 离开通知不 @全体
            for umo, config in sub_configs.items()
            if config.notify_leave
        }

        if not leave_subscribers:
            return

        notification = self.notifier.build_leave_notification(server_name, client)
        self._schedule_notification(leave_subscribers, notification)

    def _on_status_tick(self, server_name: str) -> None:
        """状态推送回调"""
        sub_configs = self.data.get_all_subscription_configs(server_name)
        if not sub_configs:
            return

        # 筛选开启状态通知的订阅者
        status_subscribers = {
            umo: config.at_all
            for umo, config in sub_configs.items()
            if config.notify_status
        }

        if not status_subscribers:
            return

        # 获取服务器状态
        server_info = self.data.get_server(server_name)
        if not server_info:
            return

        client = TS3Client(
            host=server_info.host,
            query_port=server_info.query_port,
            query_user=server_info.query_user,
            query_password=server_info.query_password,
            virtual_server_id=server_info.virtual_server_id,
        )

        try:
            if client.connect():
                status = client.get_server_status()
                if status:
                    notification = self.notifier.build_status_notification(server_name, status)
                    self._schedule_notification(status_subscribers, notification)
        finally:
            client.disconnect()

    # ==================== 命令组 ====================

    @filter.command_group("ts")
    def ts(self):
        """TeamSpeak 服务器监控命令组"""
        pass

    @ts.command("add")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def ts_add(
        self,
        event: AstrMessageEvent,
        alias: str,
        host: str,
        username: str,
        password: str,
        port: int = 10011,
        vsid: int = 1,
    ):
        """添加 TS3 服务器监控（管理员）

        Args:
            alias: 服务器别名（用于后续命令引用）
            host: 服务器地址
            username: ServerQuery 用户名
            password: ServerQuery 密码
            port: ServerQuery 端口（默认 10011）
            vsid: 虚拟服务器 ID（默认 1）
        """
        if not TS3_AVAILABLE:
            yield event.plain_result("❌ ts3 库未安装，请先安装: pip install ts3")
            return

        if self.data.has_server(alias):
            yield event.plain_result(f"⚠️ 服务器 {alias} 已存在")
            return

        # 测试连接（使用线程池避免阻塞事件循环）
        client = TS3Client(
            host=host,
            query_port=port,
            query_user=username,
            query_password=password,
            virtual_server_id=vsid,
        )

        # 同步操作放入线程池执行
        connected = await asyncio.to_thread(client.connect)
        if not connected:
            yield event.plain_result(
                "❌ 无法连接到服务器\n"
                "请检查地址、端口和凭据是否正确"
            )
            return

        # 获取服务器名称
        server_status = await asyncio.to_thread(client.get_server_status)
        await asyncio.to_thread(client.disconnect)

        if not server_status:
            yield event.plain_result("❌ 无法获取服务器信息")
            return

        # 保存服务器信息
        info = ServerInfo(
            name=alias,
            host=host,
            query_port=port,
            query_user=username,
            query_password=password,
            virtual_server_id=vsid,
            added_by=event.get_sender_id(),
            added_time=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            status_interval=60,
        )
        self.data.add_server(info)

        # 启动监控
        if self._start_monitor(alias):
            yield event.plain_result(
                f"✅ 已添加服务器监控\n"
                f"别名: {alias}\n"
                f"服务器: {server_status.name}\n"
                f"地址: {host}:{port}\n"
                f"使用 /ts sub {alias} 订阅通知"
            )
        else:
            self.data.remove_server(alias)
            yield event.plain_result("❌ 启动监控失败")

    @ts.command("del")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def ts_del(self, event: AstrMessageEvent, alias: str):
        """删除服务器监控（管理员）"""
        if not self.data.has_server(alias):
            yield event.plain_result(f"⚠️ 服务器 {alias} 不存在")
            return

        self._stop_monitor(alias)
        self.data.remove_server(alias)
        yield event.plain_result(f"✅ 已删除服务器 {alias} 的监控")

    @ts.command("ls")
    async def ts_ls(self, event: AstrMessageEvent):
        """查看监控列表"""
        servers = self.data.get_all_servers()
        if not servers:
            yield event.plain_result("📋 当前没有监控的服务器\n使用 /ts add 添加")
            return

        lines = ["📋 TeamSpeak 服务器监控列表", "━━━━━━━━━━━━━━"]
        for idx, (name, info) in enumerate(servers.items(), 1):
            sub_count = len(self.data.get_subscribers(name))
            status = "🟢 运行中" if name in self.monitors and self.monitors[name].running else "🔴 已停止"
            lines.append(
                f"{idx}. {name}\n"
                f"   地址: {info.host}:{info.query_port}\n"
                f"   订阅数: {sub_count}\n"
                f"   状态: {status}"
            )

        yield event.plain_result("\n".join(lines))

    @ts.command("sub")
    async def ts_sub(self, event: AstrMessageEvent, alias: str):
        """订阅服务器通知"""
        if not self.data.has_server(alias):
            yield event.plain_result(
                f"⚠️ 服务器 {alias} 不存在\n"
                f"使用 /ts ls 查看可订阅的服务器"
            )
            return

        umo = event.unified_msg_origin
        if not self.data.subscribe(alias, umo):
            yield event.plain_result(f"⚠️ 你已经订阅了服务器 {alias}")
            return

        is_running = alias in self.monitors and self.monitors[alias].running
        status_tip = "" if is_running else "\n⚠️ 注意: 该服务器监控未运行"

        yield event.plain_result(
            f"✅ 订阅成功！\n"
            f"服务器: {alias}\n"
            f"用户进出和定时状态将推送到此处{status_tip}"
        )

    @ts.command("unsub")
    async def ts_unsub(self, event: AstrMessageEvent, alias: str):
        """取消订阅服务器"""
        umo = event.unified_msg_origin

        if not self.data.unsubscribe(alias, umo):
            yield event.plain_result(f"⚠️ 你没有订阅服务器 {alias}")
            return

        yield event.plain_result(f"✅ 已取消订阅服务器 {alias}")

    @ts.command("mysub")
    async def ts_mysub(self, event: AstrMessageEvent):
        """查看当前群的订阅"""
        umo = event.unified_msg_origin
        server_names = self.data.get_user_subscriptions(umo)

        if not server_names:
            yield event.plain_result(
                "📋 当前群还没有订阅任何服务器\n"
                "使用 /ts ls 查看可订阅的服务器\n"
                "使用 /ts sub <别名> 订阅"
            )
            return

        my_subs = []
        for name in server_names:
            config = self.data.get_subscription_config(name, umo)
            if config:
                join_icon = "✅" if config.notify_join else "❌"
                leave_icon = "✅" if config.notify_leave else "❌"
                status_icon = "✅" if config.notify_status else "❌"
                my_subs.append(
                    f"• {name}\n"
                    f"  加入:{join_icon} | 离开:{leave_icon} | 状态:{status_icon}"
                )
            else:
                my_subs.append(f"• {name}")

        yield event.plain_result("📋 当前群的订阅列表\n━━━━━━━━━━━━━━\n" + "\n".join(my_subs))

    @ts.command("status")
    async def ts_status(self, event: AstrMessageEvent, alias: str | None = None):
        """查看服务器状态

        Args:
            alias: 服务器别名，不填则显示所有服务器摘要
        """
        if not TS3_AVAILABLE:
            yield event.plain_result("⚠️ ts3 库未安装")
            return

        if alias is None:
            # 显示所有服务器摘要
            total_servers = len(self.data.server_info)
            running = sum(1 for m in self.monitors.values() if m.running)
            total_subs = self.data.get_total_subscriptions()

            yield event.plain_result(
                f"📊 TeamSpeak 监控状态\n"
                f"━━━━━━━━━━━━━━\n"
                f"🖥️ 监控服务器: {total_servers}\n"
                f"🟢 运行中: {running}\n"
                f"👥 总订阅数: {total_subs}"
            )
            return

        server_info = self.data.get_server(alias)
        if not server_info:
            yield event.plain_result(f"⚠️ 服务器 {alias} 不存在")
            return

        # 获取实时状态（使用线程池避免阻塞事件循环）
        client = TS3Client(
            host=server_info.host,
            query_port=server_info.query_port,
            query_user=server_info.query_user,
            query_password=server_info.query_password,
            virtual_server_id=server_info.virtual_server_id,
        )

        # 同步操作放入线程池执行
        connected = await asyncio.to_thread(client.connect)
        if not connected:
            yield event.plain_result(f"❌ 无法连接到服务器 {alias}")
            return

        try:
            status = await asyncio.to_thread(client.get_server_status)
            if status:
                notification = self.notifier.build_status_notification(alias, status)
                yield event.plain_result(notification)
            else:
                yield event.plain_result(f"❌ 无法获取服务器 {alias} 的状态")
        finally:
            await asyncio.to_thread(client.disconnect)

    @ts.command("join")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def ts_join(self, event: AstrMessageEvent, alias: str, enable: str = ""):
        """切换加入通知（管理员）

        Args:
            alias: 服务器别名
            enable: on/off 或留空切换状态
        """
        if not self.data.has_server(alias):
            yield event.plain_result(f"⚠️ 服务器 {alias} 不存在")
            return

        umo = event.unified_msg_origin
        config = self.data.get_subscription_config(alias, umo)
        if not config:
            yield event.plain_result(f"⚠️ 当前群还没有订阅服务器 {alias}")
            return

        if enable.lower() == "on":
            new_status = True
        elif enable.lower() == "off":
            new_status = False
        else:
            new_status = not config.notify_join

        self.data.update_subscription_config(alias, umo, notify_join=new_status)
        status_text = "开启" if new_status else "关闭"
        yield event.plain_result(f"✅ 服务器 {alias} 的加入通知已{status_text}")

    @ts.command("leave")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def ts_leave(self, event: AstrMessageEvent, alias: str, enable: str = ""):
        """切换离开通知（管理员）

        Args:
            alias: 服务器别名
            enable: on/off 或留空切换状态
        """
        if not self.data.has_server(alias):
            yield event.plain_result(f"⚠️ 服务器 {alias} 不存在")
            return

        umo = event.unified_msg_origin
        config = self.data.get_subscription_config(alias, umo)
        if not config:
            yield event.plain_result(f"⚠️ 当前群还没有订阅服务器 {alias}")
            return

        if enable.lower() == "on":
            new_status = True
        elif enable.lower() == "off":
            new_status = False
        else:
            new_status = not config.notify_leave

        self.data.update_subscription_config(alias, umo, notify_leave=new_status)
        status_text = "开启" if new_status else "关闭"
        yield event.plain_result(f"✅ 服务器 {alias} 的离开通知已{status_text}")

    @ts.command("interval")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def ts_interval(self, event: AstrMessageEvent, alias: str, minutes: int):
        """设置状态推送间隔（管理员）

        Args:
            alias: 服务器别名
            minutes: 推送间隔（分钟），最小 10 分钟
        """
        if not self.data.has_server(alias):
            yield event.plain_result(f"⚠️ 服务器 {alias} 不存在")
            return

        if minutes < 10:
            yield event.plain_result("⚠️ 间隔最小为 10 分钟")
            return

        self.data.update_server(alias, status_interval=minutes)

        # 更新运行中的监控器
        if alias in self.monitors:
            self.monitors[alias].update_status_interval(minutes)

        yield event.plain_result(f"✅ 服务器 {alias} 的状态推送间隔已设为 {minutes} 分钟")

    @ts.command("restart")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def ts_restart(self, event: AstrMessageEvent, alias: str | None = None):
        """重启监控（管理员）

        Args:
            alias: 服务器别名，不填则重启所有
        """
        if alias is not None:
            if not self.data.has_server(alias):
                yield event.plain_result(f"⚠️ 服务器 {alias} 不存在")
                return

            self._stop_monitor(alias)
            if self._start_monitor(alias):
                yield event.plain_result(f"✅ 服务器 {alias} 监控已重启")
            else:
                yield event.plain_result(f"❌ 服务器 {alias} 监控重启失败")
        else:
            # 重启所有
            success = 0
            for name in list(self.data.server_info.keys()):
                self._stop_monitor(name)
                if self._start_monitor(name):
                    success += 1

            yield event.plain_result(
                f"✅ 已重启 {success}/{len(self.data.server_info)} 个服务器监控"
            )

    @ts.command("atall")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def ts_atall(self, event: AstrMessageEvent, alias: str, enable: str = ""):
        """切换状态推送时的 @全体（管理员）

        Args:
            alias: 服务器别名
            enable: on/off 或留空切换状态
        """
        if not self.data.has_server(alias):
            yield event.plain_result(f"⚠️ 服务器 {alias} 不存在")
            return

        umo = event.unified_msg_origin
        config = self.data.get_subscription_config(alias, umo)
        if not config:
            yield event.plain_result(f"⚠️ 当前群还没有订阅服务器 {alias}")
            return

        if enable.lower() == "on":
            new_status = True
        elif enable.lower() == "off":
            new_status = False
        else:
            new_status = not config.at_all

        self.data.update_subscription_config(alias, umo, at_all=new_status)
        status_text = "开启" if new_status else "关闭"
        yield event.plain_result(f"✅ 服务器 {alias} 的状态推送 @全体 已{status_text}")

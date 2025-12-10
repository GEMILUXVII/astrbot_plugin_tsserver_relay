"""TS3 服务器监控器模块"""

import time
from collections.abc import Callable
from threading import Lock, Thread

from astrbot.api import logger

from .ts3_client import TS3_AVAILABLE, ClientInfo, ServerStatus, TS3Client


class TS3Monitor:
    """TeamSpeak 3 服务器监控器

    使用轮询方式监控服务器状态，检测用户加入/离开。
    """

    def __init__(
        self,
        server_name: str,
        host: str,
        query_port: int,
        query_user: str,
        query_password: str,
        virtual_server_id: int = 1,
        status_interval: int = 60,
        poll_interval: int = 10,
        on_client_join: Callable[[str, ClientInfo], None] | None = None,
        on_client_leave: Callable[[str, ClientInfo], None] | None = None,
        on_status_tick: Callable[[str, ServerStatus], None] | None = None,
    ):
        """初始化监控器

        Args:
            server_name: 服务器别名
            host: 服务器地址
            query_port: ServerQuery 端口
            query_user: ServerQuery 用户名
            query_password: ServerQuery 密码
            virtual_server_id: 虚拟服务器 ID
            status_interval: 状态推送间隔（分钟）
            poll_interval: 轮询间隔（秒）
            on_client_join: 用户加入回调
            on_client_leave: 用户离开回调
            on_status_tick: 状态推送回调
        """
        self.server_name = server_name
        self.status_interval = status_interval
        self.poll_interval = poll_interval

        self.on_client_join = on_client_join
        self.on_client_leave = on_client_leave
        self.on_status_tick = on_status_tick

        # TS3 客户端
        self.client = TS3Client(
            host=host,
            query_port=query_port,
            query_user=query_user,
            query_password=query_password,
            virtual_server_id=virtual_server_id,
        )

        # 状态
        self.running = False
        self._stop_flag = False
        self._thread: Thread | None = None
        self._lock = Lock()

        # 客户端追踪
        self._known_clients: dict[int, ClientInfo] = {}  # clid -> ClientInfo
        self._last_status_time: float = 0

        # 防抖动
        self._pending_leaves: dict[int, tuple[ClientInfo, float]] = {}  # clid -> (info, leave_time)
        self._leave_debounce_seconds = 5  # 用户离开后等待 5 秒确认

    def _run(self) -> None:
        """监控主循环"""
        reconnect_attempts = 0
        max_reconnect_attempts = 5
        initial_retry_delay = 30  # 首次连接失败后的重试间隔

        try:
            # 首次连接，失败则进入重试循环
            while not self._stop_flag:
                if self.client.connect():
                    break
                reconnect_attempts += 1
                if reconnect_attempts >= max_reconnect_attempts:
                    logger.error(f"[{self.server_name}] 连接失败次数过多，监控停止")
                    return
                logger.warning(
                    f"[{self.server_name}] 连接失败，{initial_retry_delay}秒后重试 "
                    f"({reconnect_attempts}/{max_reconnect_attempts})"
                )
                time.sleep(initial_retry_delay)

            if self._stop_flag:
                return

            with self._lock:
                self.running = True

            logger.info(f"[{self.server_name}] 监控已启动")

            # 初始化客户端列表
            initial_clients = self.client.get_client_list()
            for c in initial_clients:
                self._known_clients[c.clid] = c
            logger.info(f"[{self.server_name}] 初始在线: {len(self._known_clients)} 人")

            # 设置首次状态推送时间
            self._last_status_time = time.time()

            # 重置重连计数
            reconnect_attempts = 0

            while not self._stop_flag:
                try:
                    # 获取当前客户端列表
                    current_clients = self.client.get_client_list()
                    current_clids = {c.clid for c in current_clients}
                    current_map = {c.clid: c for c in current_clients}

                    now = time.time()

                    # 检测新加入的客户端
                    for clid, client in current_map.items():
                        # 如果在待离开列表中，取消离开
                        if clid in self._pending_leaves:
                            del self._pending_leaves[clid]
                            logger.debug(f"[{self.server_name}] 用户 {client.client_nickname} 取消离开（重连）")
                            continue

                        if clid not in self._known_clients:
                            self._known_clients[clid] = client
                            logger.info(f"[{self.server_name}] 用户加入: {client.client_nickname}")
                            if self.on_client_join:
                                try:
                                    self.on_client_join(self.server_name, client)
                                except Exception as e:
                                    logger.error(f"加入回调出错: {e}")

                    # 检测离开的客户端（加入待离开列表）
                    known_clids = set(self._known_clients.keys())
                    for clid in known_clids - current_clids:
                        if clid not in self._pending_leaves:
                            client = self._known_clients[clid]
                            self._pending_leaves[clid] = (client, now)
                            logger.debug(f"[{self.server_name}] 用户 {client.client_nickname} 可能离开，等待确认")

                    # 处理确认离开的客户端
                    confirmed_leaves = []
                    for clid, (client, leave_time) in list(self._pending_leaves.items()):
                        if now - leave_time >= self._leave_debounce_seconds:
                            confirmed_leaves.append((clid, client))

                    for clid, client in confirmed_leaves:
                        del self._pending_leaves[clid]
                        if clid in self._known_clients:
                            del self._known_clients[clid]
                        logger.info(f"[{self.server_name}] 用户离开: {client.client_nickname}")
                        if self.on_client_leave:
                            try:
                                self.on_client_leave(self.server_name, client)
                            except Exception as e:
                                logger.error(f"离开回调出错: {e}")

                    # 检查是否需要推送状态
                    status_interval_seconds = self.status_interval * 60
                    if now - self._last_status_time >= status_interval_seconds:
                        self._last_status_time = now
                        logger.info(f"[{self.server_name}] 触发状态推送")
                        if self.on_status_tick:
                            try:
                                # 复用现有连接获取状态
                                status = self.client.get_server_status()
                                if status:
                                    self.on_status_tick(self.server_name, status)
                            except Exception as e:
                                logger.error(f"状态推送回调出错: {e}")

                    # 重置重连计数
                    reconnect_attempts = 0

                except Exception as e:
                    logger.error(f"[{self.server_name}] 监控循环出错: {e}")
                    reconnect_attempts += 1

                    if reconnect_attempts >= max_reconnect_attempts:
                        logger.error(f"[{self.server_name}] 重连次数过多，停止监控")
                        break

                    # 尝试重连
                    logger.info(f"[{self.server_name}] 尝试重连 ({reconnect_attempts}/{max_reconnect_attempts})")
                    if not self.client.reconnect():
                        time.sleep(30)  # 重连失败，等待 30 秒后重试
                        continue

                # 等待下一次轮询
                time.sleep(self.poll_interval)

        except Exception as e:
            logger.error(f"[{self.server_name}] 监控器异常: {e}")
        finally:
            with self._lock:
                self.running = False
            self.client.disconnect()
            logger.info(f"[{self.server_name}] 监控已停止")

    def start(self) -> bool:
        """启动监控

        Returns:
            是否成功启动
        """
        if not TS3_AVAILABLE:
            logger.error("ts3 库未安装，无法启动监控")
            return False

        if self.running:
            return True

        self._stop_flag = False
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        """停止监控"""
        self._stop_flag = True
        with self._lock:
            self.running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10.0)

        self._known_clients.clear()
        self._pending_leaves.clear()
        logger.info(f"[{self.server_name}] 监控器已停止")

    def update_status_interval(self, minutes: int) -> None:
        """更新状态推送间隔

        Args:
            minutes: 新的间隔（分钟）
        """
        self.status_interval = minutes
        logger.info(f"[{self.server_name}] 状态推送间隔已更新为 {minutes} 分钟")

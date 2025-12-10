"""通知发送模块"""

import asyncio
import time
from typing import TYPE_CHECKING

from astrbot.api import logger
from astrbot.api.event import MessageEventResult
from astrbot.api.message_components import AtAll, Plain

from ..utils.constants import format_duration
from .ts3_client import ClientInfo, ServerStatus

if TYPE_CHECKING:
    from astrbot.api import star


class Notifier:
    """通知发送器

    负责构建和发送 TS3 服务器通知消息。
    """

    def __init__(self, context: "star.Context"):
        """初始化通知器

        Args:
            context: AstrBot 上下文
        """
        self.context = context

    def build_join_notification(
        self,
        server_name: str,
        client: ClientInfo,
        timestamp: float | None = None,
    ) -> str:
        """构建用户加入通知

        Args:
            server_name: 服务器别名
            client: 客户端信息
            timestamp: 时间戳

        Returns:
            格式化的通知消息
        """
        if timestamp is None:
            timestamp = time.time()

        time_str = time.strftime("%H:%M:%S", time.localtime(timestamp))

        return (
            f"📢 TeamSpeak 用户加入\n"
            f"━━━━━━━━━━━━━━\n"
            f"🖥️ 服务器: {server_name}\n"
            f"👤 用户: {client.client_nickname}\n"
            f"⏰ 时间: {time_str}\n"
            f"━━━━━━━━━━━━━━\n"
            f"欢迎加入语音！"
        )

    def build_leave_notification(
        self,
        server_name: str,
        client: ClientInfo,
        timestamp: float | None = None,
    ) -> str:
        """构建用户离开通知

        Args:
            server_name: 服务器别名
            client: 客户端信息
            timestamp: 时间戳

        Returns:
            格式化的通知消息
        """
        if timestamp is None:
            timestamp = time.time()

        time_str = time.strftime("%H:%M:%S", time.localtime(timestamp))

        return (
            f"📤 TeamSpeak 用户离开\n"
            f"━━━━━━━━━━━━━━\n"
            f"🖥️ 服务器: {server_name}\n"
            f"👤 用户: {client.client_nickname}\n"
            f"⏰ 时间: {time_str}\n"
            f"━━━━━━━━━━━━━━\n"
            f"下次再见！"
        )

    def build_status_notification(
        self,
        server_name: str,
        status: ServerStatus,
        timestamp: float | None = None,
    ) -> str:
        """构建服务器状态通知

        Args:
            server_name: 服务器别名
            status: 服务器状态
            timestamp: 时间戳

        Returns:
            格式化的状态消息
        """
        if timestamp is None:
            timestamp = time.time()

        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

        # 格式化运行时间（复用 utils 中的函数）
        uptime_str = format_duration(status.uptime)

        # 构建在线用户列表
        if status.clients:
            client_names = [c.client_nickname for c in status.clients]
            if len(client_names) <= 10:
                clients_str = "、".join(client_names)
            else:
                clients_str = "、".join(client_names[:10]) + f" 等共 {len(client_names)} 人"
        else:
            clients_str = "无人在线"

        return (
            f"📊 TeamSpeak 服务器状态\n"
            f"━━━━━━━━━━━━━━\n"
            f"🖥️ 服务器: {server_name}\n"
            f"📛 名称: {status.name}\n"
            f"👥 在线人数: {status.clients_online}/{status.max_clients}\n"
            f"📁 频道数: {status.channels_online}\n"
            f"⏱️ 运行时间: {uptime_str}\n"
            f"━━━━━━━━━━━━━━\n"
            f"👤 在线用户: {clients_str}\n"
            f"━━━━━━━━━━━━━━\n"
            f"🕐 更新时间: {time_str}"
        )

    async def send_to_subscribers(
        self,
        subscriber_settings: dict[str, bool],
        message: str,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        """发送通知给所有订阅者

        Args:
            subscriber_settings: {umo -> at_all} 每个订阅者的 @全体设置
            message: 通知消息内容
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
        """
        for umo, at_all in subscriber_settings.items():
            for attempt in range(max_retries):
                try:
                    result = MessageEventResult()
                    # 第一次尝试时使用 @全体，重试时不用
                    if at_all and attempt == 0:
                        result.chain.append(AtAll())
                        result.chain.append(Plain("\n"))
                    result.chain.append(Plain(message))
                    await self.context.send_message(umo, result)
                    logger.info(f"已发送通知到: {umo} (at_all={at_all})")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"发送通知失败 ({umo})，{retry_delay}秒后重试 "
                            f"({attempt + 1}/{max_retries}): {e}"
                        )
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.error(f"发送通知失败 ({umo})，已达最大重试次数: {e}")

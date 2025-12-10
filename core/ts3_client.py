"""TeamSpeak 3 ServerQuery 客户端封装"""

from dataclasses import dataclass
from typing import Any

from astrbot.api import logger

try:
    import ts3

    TS3_AVAILABLE = True
except ImportError:
    TS3_AVAILABLE = False
    ts3 = None
    logger.warning("ts3 库未安装，请运行: pip install ts3")


@dataclass
class ClientInfo:
    """TS3 客户端信息"""

    clid: int  # 客户端 ID
    client_nickname: str  # 昵称
    client_database_id: int  # 数据库 ID
    cid: int  # 当前频道 ID
    client_type: int  # 客户端类型 (0=普通, 1=ServerQuery)


@dataclass
class ChannelInfo:
    """TS3 频道信息"""

    cid: int  # 频道 ID
    channel_name: str  # 频道名称
    total_clients: int  # 频道内客户端数量


@dataclass
class ServerStatus:
    """服务器状态信息"""

    name: str  # 服务器名称
    platform: str  # 平台
    version: str  # 版本
    clients_online: int  # 在线客户端数
    max_clients: int  # 最大客户端数
    channels_online: int  # 频道数
    uptime: int  # 运行时间（秒）
    clients: list[ClientInfo]  # 在线客户端列表
    channels: list[ChannelInfo]  # 频道列表


class TS3Client:
    """TeamSpeak 3 ServerQuery 客户端

    封装 ts3 库，提供连接管理和常用查询方法。
    """

    def __init__(
        self,
        host: str,
        query_port: int,
        query_user: str,
        query_password: str,
        virtual_server_id: int = 1,
    ):
        """初始化客户端

        Args:
            host: 服务器地址
            query_port: ServerQuery 端口
            query_user: ServerQuery 用户名
            query_password: ServerQuery 密码
            virtual_server_id: 虚拟服务器 ID
        """
        self.host = host
        self.query_port = query_port
        self.query_user = query_user
        self.query_password = query_password
        self.virtual_server_id = virtual_server_id
        self._connection: Any = None

    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connection is not None

    def connect(self) -> bool:
        """连接到服务器

        Returns:
            是否成功连接
        """
        if not TS3_AVAILABLE:
            logger.error("ts3 库未安装")
            return False

        try:
            self._connection = ts3.query.TS3Connection(self.host, self.query_port)
            self._connection.login(
                client_login_name=self.query_user,
                client_login_password=self.query_password,
            )
            self._connection.use(sid=self.virtual_server_id)
            logger.info(f"已连接到 TS3 服务器: {self.host}:{self.query_port}")
            return True
        except Exception as e:
            logger.error(f"连接 TS3 服务器失败: {e}")
            self._connection = None
            return False

    def disconnect(self) -> None:
        """断开连接"""
        if self._connection:
            try:
                self._connection.quit()
            except Exception:
                pass
            finally:
                self._connection = None
            logger.info(f"已断开 TS3 服务器: {self.host}")

    def reconnect(self) -> bool:
        """重新连接

        Returns:
            是否成功重连
        """
        self.disconnect()
        return self.connect()

    def get_client_list(self) -> list[ClientInfo]:
        """获取在线客户端列表

        Returns:
            客户端信息列表（不包括 ServerQuery 客户端）
        """
        if not self._connection:
            return []

        try:
            resp = self._connection.clientlist()
            clients = []
            for client_data in resp.parsed:
                client_type = int(client_data.get("client_type", 0))
                # 跳过 ServerQuery 客户端
                if client_type == 1:
                    continue
                clients.append(
                    ClientInfo(
                        clid=int(client_data.get("clid", 0)),
                        client_nickname=client_data.get("client_nickname", "Unknown"),
                        client_database_id=int(client_data.get("client_database_id", 0)),
                        cid=int(client_data.get("cid", 0)),
                        client_type=client_type,
                    )
                )
            return clients
        except Exception as e:
            logger.error(f"获取客户端列表失败: {e}")
            return []

    def get_channel_list(self) -> list[ChannelInfo]:
        """获取频道列表

        Returns:
            频道信息列表
        """
        if not self._connection:
            return []

        try:
            resp = self._connection.channellist()
            channels = []
            for channel_data in resp.parsed:
                channels.append(
                    ChannelInfo(
                        cid=int(channel_data.get("cid", 0)),
                        channel_name=channel_data.get("channel_name", "Unknown"),
                        total_clients=int(channel_data.get("total_clients", 0)),
                    )
                )
            return channels
        except Exception as e:
            logger.error(f"获取频道列表失败: {e}")
            return []

    def get_server_info(self) -> dict[str, Any] | None:
        """获取服务器信息

        Returns:
            服务器信息字典
        """
        if not self._connection:
            return None

        try:
            resp = self._connection.serverinfo()
            if resp.parsed:
                return resp.parsed[0]
            return None
        except Exception as e:
            logger.error(f"获取服务器信息失败: {e}")
            return None

    def get_server_status(self) -> ServerStatus | None:
        """获取完整的服务器状态

        Returns:
            服务器状态对象
        """
        server_info = self.get_server_info()
        if not server_info:
            return None

        clients = self.get_client_list()
        channels = self.get_channel_list()

        return ServerStatus(
            name=server_info.get("virtualserver_name", "Unknown"),
            platform=server_info.get("virtualserver_platform", "Unknown"),
            version=server_info.get("virtualserver_version", "Unknown"),
            clients_online=int(server_info.get("virtualserver_clientsonline", 0)) - 1,  # 减去 ServerQuery
            max_clients=int(server_info.get("virtualserver_maxclients", 0)),
            channels_online=int(server_info.get("virtualserver_channelsonline", 0)),
            uptime=int(server_info.get("virtualserver_uptime", 0)),
            clients=clients,
            channels=channels,
        )

    def __enter__(self) -> "TS3Client":
        """上下文管理器入口"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器退出"""
        self.disconnect()

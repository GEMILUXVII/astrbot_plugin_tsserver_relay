"""服务器信息数据模型"""

from dataclasses import asdict, dataclass
from typing import Any

from ..utils.constants import (
    DEFAULT_QUERY_PORT,
    DEFAULT_STATUS_INTERVAL,
    DEFAULT_VIRTUAL_SERVER_ID,
)


@dataclass
class ServerInfo:
    """TS3 服务器信息

    Attributes:
        name: 服务器别名（用于命令引用）
        host: 服务器地址
        query_port: ServerQuery 端口
        query_user: ServerQuery 用户名
        query_password: ServerQuery 密码
        virtual_server_id: 虚拟服务器 ID
        added_by: 添加者 ID
        added_time: 添加时间
        status_interval: 状态推送间隔（分钟）
    """

    name: str
    host: str
    query_user: str
    query_password: str
    query_port: int = DEFAULT_QUERY_PORT
    virtual_server_id: int = DEFAULT_VIRTUAL_SERVER_ID
    added_by: str = ""
    added_time: str = ""
    status_interval: int = DEFAULT_STATUS_INTERVAL

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServerInfo":
        """从字典创建实例"""
        return cls(
            name=data.get("name", ""),
            host=data.get("host", ""),
            query_user=data.get("query_user", ""),
            query_password=data.get("query_password", ""),
            query_port=data.get("query_port", DEFAULT_QUERY_PORT),
            virtual_server_id=data.get("virtual_server_id", DEFAULT_VIRTUAL_SERVER_ID),
            added_by=data.get("added_by", ""),
            added_time=data.get("added_time", ""),
            status_interval=data.get("status_interval", DEFAULT_STATUS_INTERVAL),
        )


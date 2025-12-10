"""订阅配置数据模型"""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class SubscriptionConfig:
    """订阅配置

    每个群对每个服务器的独立配置。

    Attributes:
        notify_join: 是否推送用户加入通知
        notify_leave: 是否推送用户离开通知
        notify_status: 是否接收定时状态推送
        at_all: 是否 @全体成员（仅状态推送）
    """

    notify_join: bool = True
    notify_leave: bool = True
    notify_status: bool = True
    at_all: bool = False

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubscriptionConfig":
        """从字典创建实例"""
        return cls(
            notify_join=data.get("notify_join", True),
            notify_leave=data.get("notify_leave", True),
            notify_status=data.get("notify_status", True),
            at_all=data.get("at_all", False),
        )

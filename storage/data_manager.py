"""数据持久化管理模块"""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any

from astrbot.api import logger
from astrbot.api.star import StarTools

if TYPE_CHECKING:
    from ..models.server import ServerInfo
    from ..models.subscription import SubscriptionConfig


class DataManager:
    """数据管理器

    负责插件数据的加载、保存和管理。
    数据存储在 JSON 文件中。

    该类是线程安全的，使用 RLock 保护所有数据访问。
    """

    def __init__(self, plugin_name: str = "astrbot_plugin_tsserver_relay"):
        """初始化数据管理器

        Args:
            plugin_name: 插件名称，用于确定数据目录
        """
        self.data_dir: Path = StarTools.get_data_dir(plugin_name)
        self.data_file: Path = self.data_dir / "ts3_data.json"

        # 线程锁，使用 RLock 支持同一线程多次获取
        self._lock = RLock()

        # 数据结构
        # server_name -> {umo -> SubscriptionConfig}
        self.subscriptions: dict[str, dict[str, SubscriptionConfig]] = {}
        self.server_info: dict[str, ServerInfo] = {}  # server_name -> ServerInfo

        # 加载数据
        self.load()

    def load(self) -> None:
        """从文件加载数据"""
        from ..models.server import ServerInfo as ServerInfoClass
        from ..models.subscription import SubscriptionConfig as SubConfigClass

        with self._lock:
            if not os.path.exists(self.data_file):
                self.subscriptions = {}
                self.server_info = {}
                return

            try:
                with open(self.data_file, encoding="utf-8") as f:
                    data = json.load(f)

                    # 加载服务器信息
                    self.server_info = {
                        k: ServerInfoClass.from_dict(v)
                        for k, v in data.get("server_info", {}).items()
                    }

                    # 加载订阅数据
                    raw_subs = data.get("subscriptions", {})
                    self.subscriptions = {}

                    for server_name, sub_data in raw_subs.items():
                        self.subscriptions[server_name] = {}
                        if isinstance(sub_data, dict):
                            for umo, config in sub_data.items():
                                if isinstance(config, dict):
                                    self.subscriptions[server_name][umo] = SubConfigClass.from_dict(config)
                                else:
                                    self.subscriptions[server_name][umo] = SubConfigClass()

            except Exception as e:
                logger.error(f"加载 TS3 数据失败: {e}")
                self.subscriptions = {}
                self.server_info = {}

    def save(self) -> None:
        """保存数据到文件"""
        with self._lock:
            try:
                # 确保目录存在
                self.data_dir.mkdir(parents=True, exist_ok=True)

                data = {
                    "subscriptions": {
                        server_name: {
                            umo: config.to_dict()
                            for umo, config in sub_dict.items()
                        }
                        for server_name, sub_dict in self.subscriptions.items()
                    },
                    "server_info": {
                        k: v.to_dict() for k, v in self.server_info.items()
                    },
                }
                with open(self.data_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"保存 TS3 数据失败: {e}")

    # ==================== 服务器管理 ====================

    def add_server(self, info: ServerInfo) -> None:
        """添加服务器

        Args:
            info: 服务器信息
        """
        with self._lock:
            self.server_info[info.name] = info
            if info.name not in self.subscriptions:
                self.subscriptions[info.name] = {}
            self.save()

    def remove_server(self, name: str) -> bool:
        """删除服务器

        Args:
            name: 服务器别名

        Returns:
            是否成功删除
        """
        with self._lock:
            if name not in self.server_info:
                return False
            del self.server_info[name]
            if name in self.subscriptions:
                del self.subscriptions[name]
            self.save()
            return True

    def get_server(self, name: str) -> ServerInfo | None:
        """获取服务器信息

        Args:
            name: 服务器别名

        Returns:
            服务器信息，不存在返回 None
        """
        with self._lock:
            return self.server_info.get(name)

    def has_server(self, name: str) -> bool:
        """检查服务器是否存在"""
        with self._lock:
            return name in self.server_info

    def get_all_servers(self) -> dict[str, ServerInfo]:
        """获取所有服务器"""
        with self._lock:
            return self.server_info.copy()

    def update_server(self, name: str, **kwargs: Any) -> bool:
        """更新服务器信息

        Args:
            name: 服务器别名
            **kwargs: 要更新的字段

        Returns:
            是否成功更新
        """
        with self._lock:
            if name not in self.server_info:
                return False
            for key, value in kwargs.items():
                if hasattr(self.server_info[name], key):
                    setattr(self.server_info[name], key, value)
            self.save()
            return True

    # ==================== 订阅管理 ====================

    def subscribe(self, server_name: str, umo: str) -> bool:
        """添加订阅

        Args:
            server_name: 服务器别名
            umo: unified_msg_origin

        Returns:
            是否成功（False 表示已订阅）
        """
        from ..models.subscription import SubscriptionConfig as SubConfigClass

        with self._lock:
            if server_name not in self.subscriptions:
                self.subscriptions[server_name] = {}
            if umo in self.subscriptions[server_name]:
                return False

            self.subscriptions[server_name][umo] = SubConfigClass()
            self.save()
            return True

    def unsubscribe(self, server_name: str, umo: str) -> bool:
        """取消订阅

        Args:
            server_name: 服务器别名
            umo: unified_msg_origin

        Returns:
            是否成功（False 表示未订阅）
        """
        with self._lock:
            if server_name not in self.subscriptions:
                return False
            if umo not in self.subscriptions[server_name]:
                return False
            del self.subscriptions[server_name][umo]
            self.save()
            return True

    def get_subscribers(self, server_name: str) -> set[str]:
        """获取服务器的订阅者列表"""
        with self._lock:
            if server_name not in self.subscriptions:
                return set()
            return set(self.subscriptions[server_name].keys())

    def get_subscription_config(self, server_name: str, umo: str) -> SubscriptionConfig | None:
        """获取指定订阅的配置

        Args:
            server_name: 服务器别名
            umo: unified_msg_origin

        Returns:
            订阅配置，不存在返回 None
        """
        with self._lock:
            if server_name not in self.subscriptions:
                return None
            return self.subscriptions[server_name].get(umo)

    def get_all_subscription_configs(self, server_name: str) -> dict[str, SubscriptionConfig]:
        """获取服务器所有订阅的配置

        Args:
            server_name: 服务器别名

        Returns:
            {umo -> SubscriptionConfig} 字典
        """
        with self._lock:
            return self.subscriptions.get(server_name, {}).copy()

    def update_subscription_config(self, server_name: str, umo: str, **kwargs: Any) -> bool:
        """更新指定订阅的配置

        Args:
            server_name: 服务器别名
            umo: unified_msg_origin
            **kwargs: 要更新的字段

        Returns:
            是否成功更新
        """
        with self._lock:
            if server_name not in self.subscriptions:
                return False
            if umo not in self.subscriptions[server_name]:
                return False

            config = self.subscriptions[server_name][umo]
            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            self.save()
            return True

    def get_user_subscriptions(self, umo: str) -> list[str]:
        """获取用户订阅的服务器列表"""
        with self._lock:
            return [
                server_name
                for server_name, sub_dict in self.subscriptions.items()
                if umo in sub_dict
            ]

    def get_total_subscriptions(self) -> int:
        """获取总订阅数"""
        with self._lock:
            return sum(len(s) for s in self.subscriptions.values())

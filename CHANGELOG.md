# 更新日志

本文档记录 AstrBot TeamSpeak 3 服务器监控插件的版本更新历史。

---

## [1.0.1] - 2025-12-10

### 🐛 Bug 修复

- **修复在线人数显示不正确的问题**：改用实际过滤后的客户端列表长度计算在线人数，而非依赖服务器报告的数值（该数值可能包含多个 ServerQuery 连接）

---

## [1.0.0] - 2025-12-10

### 🎉 首次发布

#### 新增功能

- **多服务器监控**：支持同时监控多个 TS3 服务器
- **实时进出通知**：用户加入/离开服务器时自动推送通知
- **定时状态推送**：可配置间隔（默认 60 分钟）自动推送服务器状态
- **订阅管理**：用户可自主订阅/取消订阅
- **@全体成员**：支持状态推送时 @全体成员
- **抗抖动机制**：5 秒确认期，避免网络抖动导致的误报
- **数据持久化**：JSON 格式存储，重启不丢失

#### 命令列表

**管理员命令**

- `/ts add` - 添加服务器
- `/ts del` - 删除服务器
- `/ts join` - 切换加入通知
- `/ts leave` - 切换离开通知
- `/ts interval` - 设置状态推送间隔
- `/ts atall` - 设置 @全体成员
- `/ts restart` - 重启监控

**普通用户命令**

- `/ts ls` - 查看监控列表
- `/ts sub` - 订阅通知
- `/ts unsub` - 取消订阅
- `/ts mysub` - 查看我的订阅
- `/ts status` - 查看服务器状态

---

[1.0.1]: https://github.com/GEMILUXVII/astrbot_plugin_tsserver_relay/releases/tag/v1.0.1
[1.0.0]: https://github.com/GEMILUXVII/astrbot_plugin_tsserver_relay/releases/tag/v1.0.0

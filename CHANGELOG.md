# 更新日志

本文档记录 AstrBot TeamSpeak 3 服务器监控插件的版本更新历史。

---

## [1.0.5] - 2025-12-10

### 🛠️ 代码质量改进

- **Monitor 首次连接容错**：首次连接失败后不再直接退出，而是进入重试循环（30秒间隔，最多5次）
- **Notifier 代码去重**：时长格式化改用 `utils.format_duration()`，消除重复代码
- **常量引用统一**：`ServerInfo` 模型使用 `utils.constants` 中的默认值常量

---

## [1.0.4] - 2025-12-10

### ⚡ 异步优化

- **使用 asyncio.Queue 替代 queue.Queue**：通知队列现在使用 `asyncio.Queue`，实现零延迟异步处理，消除了 1 秒轮询间隔
- **使用 call_soon_threadsafe**：监控线程通过 `call_soon_threadsafe` 安全地将通知放入队列，避免了直接调用协程的开销

---

## [1.0.3] - 2025-12-10

### 🔒 线程安全 & ⚡ 效率优化

- **DataManager 线程安全**：添加 `RLock` 锁保护所有数据访问，防止主线程与监控线程并发访问导致的竞态条件
- **优化状态推送**：`_on_status_tick` 现在直接复用 Monitor 已有的连接获取状态，避免每次推送时创建新连接

---

## [1.0.2] - 2025-12-10

### ⚡ 性能优化

- **修复同步网络 I/O 阻塞事件循环问题**：`/ts add` 和 `/ts status` 命令现在使用 `asyncio.to_thread()` 在线程池中执行同步网络操作，避免阻塞 asyncio 事件循环
- **修复插件卸载时的阻塞问题**：`terminate` 方法使用 `run_in_executor()` 调用 `monitor.stop()`，避免 `thread.join()` 阻塞主线程

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

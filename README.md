<div align="center">
  <img src="LOGO.png" alt="AstrBot TeamSpeak Plugin Logo" width="160" />
</div>

# <div align="center">TeamSpeak Relay</div>

<div align="center">
  <strong>AstrBot TeamSpeak 3 服务器监控通知插件</strong>
</div>

<br>

<div align="center">
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/version-v1.0.3-9644F4?style=for-the-badge" alt="Version"></a>
  <a href="https://github.com/GEMILUXVII/astrbot_plugin_tsserver_relay/blob/master/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-E53935?style=for-the-badge" alt="License"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"></a>
  <a href="https://github.com/AstrBotDevs/AstrBot"><img src="https://img.shields.io/badge/AstrBot-Compatible-00BFA5?style=for-the-badge&logo=robot&logoColor=white" alt="AstrBot Compatible"></a>
</div>

<div align="center">
  <a href="https://teamspeak.com/"><img src="https://img.shields.io/badge/TeamSpeak-Server-2580C3?style=for-the-badge&logo=teamspeak&logoColor=white" alt="TeamSpeak"></a>
  <a href="https://github.com/NapNeko/NapCatQQ"><img src="https://img.shields.io/badge/NapCat-QQ-2196F3?style=for-the-badge&logo=qq&logoColor=white" alt="NapCat"></a>
</div>

<br>

<div align="center">
  <a href="#插件简介">插件简介</a> •
  <a href="#功能特性">功能特性</a> •
  <a href="#命令列表">命令列表</a> •
  <a href="#使用示例">使用示例</a> •
  <a href="CHANGELOG.md">更新日志</a>
</div>

## 插件简介

AstrBot TeamSpeak 3 服务器监控插件，支持多服务器监控、用户进出通知、定时状态推送、订阅管理等功能。

## 功能特性

- **多服务器监控**：同时监控多个 TS3 服务器，支持多开实例
- **实时进出通知**：用户加入/离开服务器时自动推送通知
- **定时状态推送**：可配置间隔（默认 60 分钟）自动推送服务器状态
- **订阅推送**：用户可自主订阅/取消订阅，精准推送到群/私聊
- **@全体成员**：支持状态推送时自动 @全体成员（可选）
- **抗抖动机制**：内置 5 秒确认期，避免网络抖动导致的误报
- **数据持久化**：监控与订阅数据自动保存，重启不丢失
- **权限控制**：添加/删除服务器需管理员权限
- **状态查询**：随时查看服务器实时状态

## 插件安装

1. **安装依赖**

   ```bash
   pip install ts3
   ```

2. **安装插件**

   将本插件目录放入 AstrBot 的 `data/plugins/` 目录下：

   ```
   data/plugins/astrbot_plugin_tsserver_relay/
   ├── main.py
   ├── metadata.yaml
   ├── requirements.txt
   ├── core/
   ├── models/
   ├── storage/
   └── utils/
   ```

3. **重启/重载 AstrBot**

   在 WebUI 重载插件，或直接重启 AstrBot。

## 配置 TeamSpeak 防洪白名单

> [!WARNING]
> **重要：配置 ServerQuery 白名单**
>
> 本插件会以较高的频率与 TeamSpeak 服务器的 ServerQuery 端口通信。为防止被 TeamSpeak 的防洪（Anti-Flood）机制误判为攻击，**必须**将管理工具的 IP 地址加入服务器的白名单。

进入每个 TeamSpeak 服务器的数据目录，创建或编辑 `query_ip_allowlist.txt` 文件：

```
127.0.0.1
::1
172.16.0.0/12  # 覆盖 Docker 默认的内部网络地址范围
```

> [!CAUTION]
> **必须重启 TeamSpeak 服务！**
>
> 这是最容易被忽略但至关重要的一步。白名单配置必须在重启后才能生效。

```bash
# 进入 TeamSpeak 项目目录
cd /path/to/your/teamspeak_project
docker-compose restart
```

## 命令列表

### 管理员命令

| 命令                                                          | 说明              | 示例                                             |
| ------------------------------------------------------------- | ----------------- | ------------------------------------------------ |
| `/ts add <别名> <主机> <用户名> <密码> [端口] [虚拟服务器ID]` | 添加服务器        | `/ts add myts 192.168.1.100 serveradmin pass123` |
| `/ts del <别名>`                                              | 删除服务器        | `/ts del myts`                                   |
| `/ts join <别名> [on/off]`                                    | 切换加入通知      | `/ts join myts off`                              |
| `/ts leave <别名> [on/off]`                                   | 切换离开通知      | `/ts leave myts on`                              |
| `/ts interval <别名> <分钟>`                                  | 设置状态推送间隔  | `/ts interval myts 30`                           |
| `/ts atall <别名> [on/off]`                                   | 设置状态推送@全体 | `/ts atall myts on`                              |
| `/ts restart [别名]`                                          | 重启监控          | `/ts restart myts`                               |

### 普通用户命令

| 命令                | 说明           | 示例              |
| ------------------- | -------------- | ----------------- |
| `/ts ls`            | 查看监控列表   | `/ts ls`          |
| `/ts sub <别名>`    | 订阅服务器通知 | `/ts sub myts`    |
| `/ts unsub <别名>`  | 取消订阅       | `/ts unsub myts`  |
| `/ts mysub`         | 查看我的订阅   | `/ts mysub`       |
| `/ts status [别名]` | 查看服务器状态 | `/ts status myts` |

## 使用示例

### 添加服务器（管理员）

```
/ts add myserver 192.168.1.100 serveradmin MyPassword123
```

默认使用端口 10011 和虚拟服务器 ID 1。如需自定义：

```
/ts add myserver 192.168.1.100 serveradmin MyPassword123 10022 1
```

### 用户订阅

```
/ts sub myserver
```

### 关闭离开通知

```
/ts leave myserver off
```

### 修改状态推送间隔

```
/ts interval myserver 30
```

### 查看服务器状态

```
/ts status myserver
```

## 通知样例

### 用户加入通知

```
📢 TeamSpeak 用户加入
━━━━━━━━━━━━━━
🖥️ 服务器: myserver
👤 用户: PlayerName
⏰ 时间: 20:30:45
━━━━━━━━━━━━━━
欢迎加入语音！
```

### 用户离开通知

```
📤 TeamSpeak 用户离开
━━━━━━━━━━━━━━
🖥️ 服务器: myserver
👤 用户: PlayerName
⏰ 时间: 21:15:30
━━━━━━━━━━━━━━
下次再见！
```

### 服务器状态通知

```
📊 TeamSpeak 服务器状态
━━━━━━━━━━━━━━
🖥️ 服务器: myserver
📛 名称: My Gaming Server
👥 在线人数: 5/32
📁 频道数: 10
⏱️ 运行时间: 3天12小时30分钟
━━━━━━━━━━━━━━
👤 在线用户: Player1、Player2、Player3
━━━━━━━━━━━━━━
🕐 更新时间: 2025-12-10 21:00:00
```

## 数据存储

插件数据默认存储于：

```
data/plugin_data/astrbot_plugin_tsserver_relay/ts3_data.json
```

数据结构示例：

```json
{
  "subscriptions": {
    "myserver": {
      "default:GroupMessage:123456789": {
        "notify_join": true,
        "notify_leave": true,
        "notify_status": true,
        "at_all": false
      }
    }
  },
  "server_info": {
    "myserver": {
      "name": "myserver",
      "host": "192.168.1.100",
      "query_port": 10011,
      "query_user": "serveradmin",
      "query_password": "password",
      "virtual_server_id": 1,
      "status_interval": 60
    }
  }
}
```

## 常见问题

### Q: 提示 "ts3 库未安装"

A: 请运行 `pip install ts3` 安装依赖。

### Q: 无法连接到服务器

A: 请检查：

- 服务器地址和 ServerQuery 端口是否正确（默认 10011，非客户端端口 9987）
- ServerQuery 账户用户名密码是否正确
- 服务器防火墙是否允许该端口访问

### Q: 多开服务器如何配置

A: 为每个实例指定不同的端口：

```
/ts add server1 192.168.1.100 admin pass1 10011
/ts add server2 192.168.1.100 admin pass2 10012
```

### Q: @全体成员 不生效

A: 请确保已开启 @全体，且机器人有群管理员权限，群设置允许 @全体成员。

### Q: 收不到进出通知

A: 检查监控状态、订阅状态，必要时使用 `/ts restart` 重启监控。

## 相关链接

- [AstrBot 官方文档](https://astrbot.app/)
- [AstrBot 插件开发指南](https://docs.astrbot.app/dev/star/plugin-new.html)
- [TeamSpeak 官网](https://teamspeak.com/)
- [ts3 Python 库](https://github.com/benediktschmitt/py-ts3)

## 许可证

[![](https://www.gnu.org/graphics/agplv3-155x51.png "AGPL v3 logo")](https://www.gnu.org/licenses/agpl-3.0.txt)

Copyright (C) 2025 GEMILUXVII

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.

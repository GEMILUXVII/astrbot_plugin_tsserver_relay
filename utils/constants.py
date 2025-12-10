"""常量和工具函数"""


# 默认配置
DEFAULT_QUERY_PORT = 10011
DEFAULT_VIRTUAL_SERVER_ID = 1
DEFAULT_STATUS_INTERVAL = 60  # 分钟
DEFAULT_POLL_INTERVAL = 10  # 秒


def format_duration(seconds: int) -> str:
    """格式化时长

    Args:
        seconds: 秒数

    Returns:
        格式化的时长字符串，如 "1天2小时30分钟"
    """
    if seconds <= 0:
        return "0分钟"

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60

    parts = []
    if days > 0:
        parts.append(f"{days}天")
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}分钟")

    return "".join(parts)

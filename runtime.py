"""
共享运行时状态模块
提供环形日志缓冲、运行状态、最新资讯缓存与 stdout 双写捕获 (供 WebUI 读取)
"""
import threading
from collections import deque
from datetime import datetime

_lock = threading.Lock()
_log_lines = deque(maxlen=400)

# 全局运行状态 (WebUI 展示用)
state = {
    "running": False,
    "last_run": "",
    "last_result": "",
}

# 最近一次运行的资讯缓存 (WebUI 表格展示)
latest_news = []

def add_log(msg: str):
    """写入一条日志到环形缓冲"""
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    with _lock:
        _log_lines.append(line)

def get_logs(n: int = 200) -> list[str]:
    with _lock:
        return list(_log_lines)[-n:]

def set_news(news_list: list[dict]):
    """缓存最近一次运行的资讯 (最多 50 条)"""
    global latest_news
    latest_news = list(news_list)[:50] if news_list else []

class Tee:
    """stdout 双写：保留原始控制台输出的同时，同步追加到 WebUI 日志缓冲"""
    def __init__(self, original):
        self.original = original

    def write(self, s):
        try:
            self.original.write(s)
            s2 = s.rstrip("\n")
            if s2.strip():
                with _lock:
                    _log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] {s2}")
        except Exception:
            pass
        return len(s)

    def flush(self):
        try:
            self.original.flush()
        except Exception:
            pass

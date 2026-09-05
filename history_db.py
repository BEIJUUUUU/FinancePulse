"""
推送历史数据库 (SQLite 零依赖)
提供 24 小时防重复推送过滤与历史归档查询
"""
import os
import sqlite3
import hashlib
from datetime import datetime, timedelta

_DB_DIR = os.path.join(os.path.dirname(__file__), "data")
# 若存在 data 挂载目录 (Docker/NAS 部署)，历史库持久化到该目录，容器重建不丢失
DB_PATH = os.path.join(_DB_DIR if os.path.isdir(_DB_DIR) else os.path.dirname(__file__), "history.db")

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据表"""
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS pushed_news (
                fingerprint TEXT PRIMARY KEY,
                title TEXT,
                tag TEXT,
                sentiment TEXT,
                pushed_at TEXT
            )
        """)

def fingerprint(title: str) -> str:
    """以标题哈希作为新闻唯一指纹"""
    return hashlib.md5(title.strip().encode("utf-8")).hexdigest()

def filter_unpushed(news_list: list[dict], hours: int = 24) -> list[dict]:
    """过滤掉指定小时内已经推送过的资讯 (防重复推送核心)"""
    if not news_list:
        return []
    init_db()
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")

    result = []
    with _conn() as c:
        for item in news_list:
            fp = fingerprint(item.get("title", ""))
            row = c.execute(
                "SELECT 1 FROM pushed_news WHERE fingerprint = ? AND pushed_at >= ?",
                (fp, cutoff)
            ).fetchone()
            if not row:
                result.append(item)
    return result

def record_pushed(news_list: list[dict]):
    """推送成功后登记历史，避免后续重复推送"""
    if not news_list:
        return
    init_db()
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as c:
        for item in news_list:
            title = item.get("title", "")
            if not title:
                continue
            c.execute(
                "INSERT OR REPLACE INTO pushed_news (fingerprint, title, tag, sentiment, pushed_at) VALUES (?, ?, ?, ?, ?)",
                (
                    fingerprint(title),
                    title,
                    item.get("tag", ""),
                    item.get("sentiment", ""),
                    now
                )
            )

def recent_pushes(limit: int = 20) -> list[dict]:
    """查询最近的推送记录 (最新在前)"""
    init_db()
    with _conn() as c:
        rows = c.execute(
            "SELECT title, tag, sentiment, pushed_at FROM pushed_news ORDER BY pushed_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]

def prune_old(days: int = 30):
    """清理超过指定天数的陈旧历史记录"""
    init_db()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    with _conn() as c:
        c.execute("DELETE FROM pushed_news WHERE pushed_at < ?", (cutoff,))

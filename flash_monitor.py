"""
突发要闻实时监控引擎
低频轻量轮询信源，命中突发关键词或自选监控词时立即触发推送回调 (秒级时效，不经 AI 分析)
"""
import threading
import time

import config
import history_db
from fetcher import fetch_cls_news

def check_flash_once(push_fn) -> int:
    """
    执行一次突发监控巡检
    :param push_fn: 推送回调函数，接收命中的新闻列表
    :return: 本次命中的条数
    """
    cfg = config.load_config()

    flash_kws = [k.strip() for k in cfg.get("flash_keywords", "").replace("，", ",").split(",") if k.strip()]
    watch_kws = [k.strip() for k in cfg.get("watchlist", "").replace("，", ",").split(",") if k.strip()]
    if not flash_kws and not watch_kws:
        return 0

    sources = cfg.get("sources", ["sina", "wscn"])
    raw = fetch_cls_news(limit=10, enabled_sources=sources)
    if not raw:
        return 0

    # 过滤掉最近 12 小时内已推送过的内容 (防突发重复轰炸)
    fresh = history_db.filter_unpushed(raw, hours=12)
    if not fresh:
        return 0

    hits = []
    for item in fresh:
        text = item.get("title", "") + " " + item.get("content", "")
        text_lower = text.lower()

        flash_matched = [k for k in flash_kws if k.lower() in text_lower]
        watch_matched = [k for k in watch_kws if k.lower() in text_lower]

        if flash_matched or watch_matched:
            item["flash_hit"] = "、".join(flash_matched)
            if watch_matched:
                item["watch_hit"] = "、".join(watch_matched)
            hits.append(item)

    if hits:
        push_fn(hits)
    return len(hits)

class FlashMonitor(threading.Thread):
    """
    突发监控常驻线程
    :param push_fn: 推送回调 (由 GUI 或 main 提供各自实现)
    :param stop_event: threading.Event，set() 即可优雅停止
    """
    def __init__(self, push_fn, stop_event: threading.Event):
        super().__init__(daemon=True, name="FlashMonitor")
        self.push_fn = push_fn
        self.stop_event = stop_event

    def run(self):
        # 启动即先巡检一次
        try:
            check_flash_once(self.push_fn)
        except Exception as e:
            print(f"[突发监控] 轮询异常: {e}")

        while not self.stop_event.is_set():
            try:
                cfg = config.load_config()
                interval = max(1, int(cfg.get("flash_interval_minutes", 2)))
            except Exception:
                interval = 2

            # 用 Event.wait 替代 sleep，停止信号可秒级响应
            if self.stop_event.wait(interval * 60):
                break

            try:
                check_flash_once(self.push_fn)
            except Exception as e:
                print(f"[突发监控] 轮询异常: {e}")

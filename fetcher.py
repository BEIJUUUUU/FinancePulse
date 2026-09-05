"""
财经资讯采集引擎 (多源聚合 & 动态信源选择)
支持独立选择信源：
- sina: 新浪财经 7x24 全球快讯
- wscn: 华尔街见闻 实时快讯
- cls: 财联社 / 东方财富 (AKShare 支持)
"""
import json
import re
import urllib.request
import urllib.error
from datetime import datetime

def _fetch_sina_live(limit: int = 30) -> list[dict]:
    """抓取新浪财经 7x24 全球财经直播快讯"""
    url = f"https://zhibo.sina.com.cn/api/zhibo/feed?page=1&page_size={limit}&zhibo_id=152"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://finance.sina.com.cn/"
    }
    req = urllib.request.Request(url, headers=headers)
    items = []
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        feed_list = data.get("result", {}).get("data", {}).get("feed", {}).get("list", [])
        for item in feed_list:
            create_time = item.get("create_time", "")
            time_str = create_time[11:16] if len(create_time) >= 16 else create_time
            
            raw_text = item.get("rich_text", "") or item.get("text", "")
            clean_text = re.sub(r"<[^>]+>", "", raw_text).strip()
            if not clean_text:
                continue

            title = ""
            content = clean_text
            if "【" in clean_text and "】" in clean_text:
                parts = clean_text.split("】", 1)
                title = parts[0].replace("【", "").strip()
                content = parts[1].strip() if len(parts) > 1 else ""
            else:
                title = clean_text[:28] + ("..." if len(clean_text) > 28 else "")

            items.append({
                "time": time_str or datetime.now().strftime("%H:%M"),
                "title": title,
                "content": content or title,
                "source": "新浪财经"
            })
    return items

def _fetch_wscn_live(limit: int = 30) -> list[dict]:
    """抓取华尔街见闻 7x24 全球快讯"""
    url = f"https://api-one-wscn.awtmt.com/apiv1/content/lives?channel=global-channel&limit={limit}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    items = []
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        live_list = data.get("data", {}).get("items", [])
        for item in live_list:
            display_time = item.get("display_time", 0)
            time_str = datetime.fromtimestamp(display_time).strftime("%H:%M") if display_time else datetime.now().strftime("%H:%M")

            title = item.get("title", "")
            content_text = item.get("content_text", "") or item.get("content", "")
            clean_content = re.sub(r"<[^>]+>", "", content_text).strip()

            if not title and clean_content:
                if "【" in clean_content and "】" in clean_content:
                    parts = clean_content.split("】", 1)
                    title = parts[0].replace("【", "").strip()
                    clean_content = parts[1].strip()
                else:
                    title = clean_content[:28] + ("..." if len(clean_content) > 28 else "")

            if title:
                items.append({
                    "time": time_str,
                    "title": title.strip(),
                    "content": clean_content or title.strip(),
                    "source": "华尔街见闻"
                })
    return items

def _fetch_cls_akshare(limit: int = 30) -> list[dict]:
    """通过 AKShare 抓取财联社全球快讯 (如可用)"""
    items = []
    try:
        import akshare as ak
        df = ak.stock_info_global_cls()
        if df is not None and not df.empty:
            for _, row in df.head(limit).iterrows():
                content_str = str(row.iloc[1])
                t_str = str(row.iloc[0])[-5:] if len(str(row.iloc[0])) >= 5 else ""
                
                title = content_str[:26] + "..."
                content = content_str
                if "【" in content_str and "】" in content_str:
                    parts = content_str.split("】", 1)
                    title = parts[0].replace("【", "").strip()
                    content = parts[1].strip()
                
                items.append({
                    "time": t_str or datetime.now().strftime("%H:%M"),
                    "title": title,
                    "content": content,
                    "source": "财联社"
                })
    except Exception:
        pass
    return items

def fetch_cls_news(limit: int = 20, enabled_sources: list[str] = None) -> list[dict]:
    """
    根据勾选的信源并发抓取财经快讯 (ThreadPoolExecutor 多路同时请求，总耗时≈单源耗时)
    :param limit: 抓取条数
    :param enabled_sources: 启用的信源列表，如 ['sina', 'wscn', 'cls']
    """
    if enabled_sources is None:
        enabled_sources = ["sina", "wscn"]

    all_raw_items = []
    fetch_limit = max(limit + 10, 25)

    source_map = {
        "sina": (_fetch_sina_live, "新浪财经"),
        "wscn": (_fetch_wscn_live, "华尔街见闻"),
        "cls": (_fetch_cls_akshare, "财联社"),
    }

    active = [(fn, name) for key, (fn, name) in source_map.items() if key in enabled_sources]
    if not active:
        return all_raw_items

    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=len(active)) as executor:
        future_to_name = {
            executor.submit(fn, limit=fetch_limit): name for fn, name in active
        }
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                items = future.result()
                all_raw_items.extend(items)
            except Exception as e:
                print(f"[信源] {name} 抓取跳过: {e}")

    return all_raw_items

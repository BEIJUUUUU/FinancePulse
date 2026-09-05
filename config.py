"""
系统配置驱动模块
支持 settings.json 持久化与 Docker 容器全量环境变量注入
"""
import os
import json

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

DEFAULT_CONFIG = {
    "smtp_server": "smtp.qq.com",
    "smtp_port": 465,
    "sender_email": "",
    "sender_auth_code": "",
    "receiver_email": "",
    "news_limit": 20,
    "sources": ["sina", "wscn"],
    "enable_dedup": True,
    "categories": ["宏观政策", "A股市场", "科技产业", "大宗商品", "全球要闻"],
    "schedule_enabled": False,
    "schedule_mode": "classic",
    "schedule_times": ["08:30", "12:00", "16:00"],
    "custom_times": "09:15, 14:30, 21:00",
    "filter_keywords": "",
    "llm_provider": "DeepSeek (深度求索)",
    "llm_enabled": False,
    "llm_api_key": "",
    "llm_base_url": "https://api.deepseek.com",
    "llm_model": "deepseek-v4-flash",
    "llm_reasoning_level": "balanced",
    "llm_max_concurrent": 1,
    "custom_prompt": "",
    "watchlist": "",
    "flash_enabled": False,
    "flash_keywords": "降息,降准,加息,证监会,国务院,突发,暴涨,暴跌,熔断,停火,开战,重大政策",
    "flash_interval_minutes": 2,
    "ui_theme": "System"
}

def load_config() -> dict:
    """加载配置：优先读取 settings.json，并允许 Docker 环境变量覆盖"""
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                cfg.update(saved)
        except Exception as e:
            print(f"[配置] 读取 settings.json 失败: {e}")

    # 环境变量覆盖 (Docker / NAS 容器化支持)
    if os.getenv("SENDER_EMAIL"):
        cfg["sender_email"] = os.getenv("SENDER_EMAIL").strip()
    if os.getenv("SENDER_AUTH_CODE"):
        cfg["sender_auth_code"] = os.getenv("SENDER_AUTH_CODE").strip()
    if os.getenv("RECEIVER_EMAIL"):
        cfg["receiver_email"] = os.getenv("RECEIVER_EMAIL").strip()
    if os.getenv("LLM_API_KEY"):
        cfg["llm_api_key"] = os.getenv("LLM_API_KEY").strip()
        cfg["llm_enabled"] = True
    if os.getenv("LLM_BASE_URL"):
        cfg["llm_base_url"] = os.getenv("LLM_BASE_URL").strip()
    if os.getenv("LLM_MODEL"):
        cfg["llm_model"] = os.getenv("LLM_MODEL").strip()
    if os.getenv("LLM_REASONING_LEVEL"):
        cfg["llm_reasoning_level"] = os.getenv("LLM_REASONING_LEVEL").strip()
    if os.getenv("LLM_MAX_CONCURRENT"):
        try:
            cfg["llm_max_concurrent"] = max(1, min(3, int(os.getenv("LLM_MAX_CONCURRENT"))))
        except ValueError:
            pass
    if os.getenv("NEWS_LIMIT"):
        try:
            cfg["news_limit"] = int(os.getenv("NEWS_LIMIT"))
        except ValueError:
            pass
    if os.getenv("CRON_TIMES"):
        times = [t.strip() for t in os.getenv("CRON_TIMES").split(",") if t.strip()]
        if times:
            cfg["schedule_times"] = times
    if os.getenv("SOURCES"):
        cfg["sources"] = [s.strip() for s in os.getenv("SOURCES").split(",") if s.strip()]
    if os.getenv("CATEGORIES"):
        cfg["categories"] = [c.strip() for c in os.getenv("CATEGORIES").split(",") if c.strip()]
    if os.getenv("CUSTOM_PROMPT"):
        cfg["custom_prompt"] = os.getenv("CUSTOM_PROMPT").strip()

    # 突发监控与自选监控配置
    if os.getenv("WATCHLIST"):
        cfg["watchlist"] = os.getenv("WATCHLIST").strip()
    if os.getenv("FLASH_KEYWORDS"):
        cfg["flash_keywords"] = os.getenv("FLASH_KEYWORDS").strip()
    if os.getenv("FLASH_INTERVAL"):
        try:
            cfg["flash_interval_minutes"] = max(1, int(os.getenv("FLASH_INTERVAL")))
        except ValueError:
            pass
    if os.getenv("FLASH_ENABLED", "").lower() in ("1", "true", "yes"):
        cfg["flash_enabled"] = True

    return cfg

def save_config(config_dict: dict) -> bool:
    """保存配置到 settings.json"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"[配置] 写入 settings.json 失败: {e}")
        return False

# 导出变量
_active_cfg = load_config()
SMTP_SERVER = _active_cfg.get("smtp_server", "smtp.qq.com")
SMTP_PORT = int(_active_cfg.get("smtp_port", 465))
SENDER_EMAIL = _active_cfg.get("sender_email", "")
SENDER_AUTH_CODE = _active_cfg.get("sender_auth_code", "")
RECEIVER_EMAIL = _active_cfg.get("receiver_email", "") or SENDER_EMAIL
NEWS_LIMIT = _active_cfg.get("news_limit", 20)
SOURCES = _active_cfg.get("sources", ["sina", "wscn"])
ENABLE_DEDUP = _active_cfg.get("enable_dedup", True)
CATEGORIES = _active_cfg.get("categories", ["宏观政策", "A股市场", "科技产业", "大宗商品", "全球要闻"])
FILTER_KEYWORDS = [k.strip() for k in _active_cfg.get("filter_keywords", "").split(",") if k.strip()]
LLM_ENABLED = _active_cfg.get("llm_enabled", False)
LLM_API_KEY = _active_cfg.get("llm_api_key", "")
LLM_BASE_URL = _active_cfg.get("llm_base_url", "https://api.deepseek.com")
LLM_MODEL = _active_cfg.get("llm_model", "deepseek-v4-flash")
LLM_REASONING_LEVEL = _active_cfg.get("llm_reasoning_level", "balanced")
LLM_MAX_CONCURRENT = max(1, min(3, int(_active_cfg.get("llm_max_concurrent", 1))))
CUSTOM_PROMPT = _active_cfg.get("custom_prompt", "")
UI_THEME = _active_cfg.get("ui_theme", "System")

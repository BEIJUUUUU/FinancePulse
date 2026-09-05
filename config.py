"""
系统配置驱动模块
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
    "schedule_enabled": False,
    "schedule_mode": "classic",
    "schedule_times": ["08:30", "12:00", "16:00"],
    "custom_times": "09:15, 14:30, 21:00",
    "filter_keywords": "",
    "llm_provider": "DeepSeek (深度求索)",
    "llm_enabled": False,
    "llm_api_key": "",
    "llm_base_url": "https://api.deepseek.com",
    "llm_model": "deepseek-chat",
    "ui_theme": "System"
}

def load_config() -> dict:
    """加载当前配置"""
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config.update(saved)
        except Exception as e:
            print(f"[配置] 读取 settings.json 失败: {e}")
    return config

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
SMTP_SERVER = _active_cfg["smtp_server"]
SMTP_PORT = _active_cfg["smtp_port"]
SENDER_EMAIL = _active_cfg["sender_email"]
SENDER_AUTH_CODE = _active_cfg["sender_auth_code"]
RECEIVER_EMAIL = _active_cfg["receiver_email"]
NEWS_LIMIT = _active_cfg.get("news_limit", 20)
SOURCES = _active_cfg.get("sources", ["sina", "wscn"])
ENABLE_DEDUP = _active_cfg.get("enable_dedup", True)
FILTER_KEYWORDS = [k.strip() for k in _active_cfg.get("filter_keywords", "").split(",") if k.strip()]
LLM_ENABLED = _active_cfg.get("llm_enabled", False)
LLM_API_KEY = _active_cfg.get("llm_api_key", "")
LLM_BASE_URL = _active_cfg.get("llm_base_url", "https://api.deepseek.com")
LLM_MODEL = _active_cfg.get("llm_model", "deepseek-chat")
UI_THEME = _active_cfg.get("ui_theme", "System")

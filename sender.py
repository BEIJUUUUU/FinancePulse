"""
飞书自定义机器人 (Webhook) 消息推送模块
"""
import requests
import json
from datetime import datetime

def send_feishu_card(webhook_url: str, title: str, markdown_content: str) -> bool:
    """
    向飞书群自定义机器人发送交互式富文本卡片
    """
    if not webhook_url:
        print("[警告] 未配置 FEISHU_WEBHOOK_URL，跳过发送。请在 config.py 中配置。")
        return False

    current_date = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 构造飞书 2.0 交互式消息卡片结构
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📊 {title}"
                },
                "template": "blue"  # 卡片主题色：blue(科技蓝), orange, red, green
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**更新时间**：{current_date}\n\n{markdown_content}"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": "💡 数据来源：财联社 / 东方财富 7x24小时全球快讯"
                        }
                    ]
                }
            ]
        }
    }

    try:
        response = requests.post(
            webhook_url,
            headers={"Content-Type": "application/json; charset=utf-8"},
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=10
        )
        result = response.json()
        if result.get("StatusCode") == 0 or result.get("code") == 0:
            print("[成功] 飞书卡片消息推送成功！")
            return True
        else:
            print(f"[失败] 飞书接口返回错误: {result}")
            return False
    except Exception as e:
        print(f"[异常] 发送飞书请求异常: {e}")
        return False

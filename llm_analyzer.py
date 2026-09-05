"""
大模型 (LLM) 财经分析与点评引擎
支持动态自定义 Prompt 提示词与思考强度 (Reasoning Depth) 调节
全兼容 OpenAI 标准接口协议
"""
import json
import urllib.request
import urllib.error

LLM_PROVIDERS = {
    "DeepSeek (深度求索)": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "note": "官方标准模型名 deepseek-chat (对应 V3) 或 deepseek-reasoner (对应 R1 深度思考)"
    },
    "Kimi / Moonshot (月之暗面)": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "note": "长文本处理优秀，资讯提炼自然"
    },
    "智谱 AI (GLM)": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "note": "glm-4-flash 官方永久免费或极低费率"
    },
    "阿里通义千问 (Qwen)": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-turbo",
        "note": "阿里云稳定支持，商业级表现"
    },
    "OpenAI (ChatGPT)": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "note": "国际标准模型，速度快质量高"
    },
    "Ollama (本地私有大模型)": {
        "base_url": "http://localhost:11434/v1",
        "model": "qwen2.5:7b",
        "note": "纯本地离线运行，100% 隐私，无需 API Key"
    },
    "自定义 API (Custom)": {
        "base_url": "https://api.example.com/v1",
        "model": "custom-model",
        "note": "手动指定任意支持 OpenAI 格式的中转或开源接口"
    }
}

DEFAULT_SYSTEM_PROMPT = """你是一位资深的宏观经济与证券市场投研分析师。
请对输入的财经快讯列表进行专业过滤与深度提炼：
1. 挑选出最具有投资决策价值、宏观或行业影响力的重点事件；
2. 为每条资讯提供精炼的核心要点；
3. 输出一句话【AI 点评 / 市场影响】，明确标出潜在利好/利空导向或宏观风向。

请严格返回如下 JSON 数组格式（严禁输出任何 markdown 格式标记、反引号或额外解释）：
[
  {
    "time": "原始时间",
    "title": "精练标题(15字内)",
    "content": "核心事实摘要(50字内)",
    "ai_comment": "一句话投研点评(30字内)",
    "tag": "宏观/A股/美股/大宗/产业",
    "sentiment": "利好/利空/中性"
  }
]
"""

# 针对不同思考强度的温度与引导设定
REASONING_PROMPTS = {
    "fast": {
        "temperature": 0.1,
        "suffix": "\n[要求: 采用快速提炼模式，严格以事实为依据，点评尽量简明扼要。]"
    },
    "balanced": {
        "temperature": 0.3,
        "suffix": "\n[要求: 采用深度研判模式，注重宏观经济、行业供需与资本市场情绪的传导关系。]"
    },
    "deep": {
        "temperature": 0.5,
        "suffix": "\n[要求: 采用长思维链推演模式，深入挖掘事件背后的次级衍生影响、潜在受益受损标的与宏观流动性冲击。]"
    }
}

def analyze_news_with_llm(
    news_list: list[dict],
    api_key: str = "",
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-chat",
    system_prompt: str = "",
    reasoning_level: str = "balanced"
) -> list[dict]:
    """
    调用大模型对财经资讯进行深度结构化分析与点评
    :param reasoning_level: 思考强度，可选 'fast' (快速), 'balanced' (均衡推荐), 'deep' (深度推演)
    """
    if not news_list:
        return []

    if "localhost" in base_url or "127.0.0.1" in base_url:
        if not api_key:
            api_key = "ollama"
    elif not api_key:
        print("[LLM 提示] 未配置 API_KEY，跳过大模型分析。")
        return news_list

    endpoint = base_url.rstrip("/")
    if not endpoint.endswith("/v1") and not endpoint.endswith("/chat/completions"):
        endpoint = f"{endpoint}/v1/chat/completions"
    elif endpoint.endswith("/v1"):
        endpoint = f"{endpoint}/chat/completions"

    input_texts = []
    for idx, item in enumerate(news_list, 1):
        input_texts.append(f"{idx}. [{item.get('time', '')}] {item.get('title', '')} - {item.get('content', '')}")
    user_prompt = "以下是最新抓取的全球与国内财经快讯列表，请精选并给出专业投研点评：\n" + "\n".join(input_texts)

    # 结合思考强度
    prompt_config = REASONING_PROMPTS.get(reasoning_level, REASONING_PROMPTS["balanced"])
    base_prompt = system_prompt.strip() if system_prompt and system_prompt.strip() else DEFAULT_SYSTEM_PROMPT.strip()
    full_prompt = base_prompt + prompt_config["suffix"]

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": full_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": prompt_config["temperature"]
    }

    try:
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
        )

        with urllib.request.urlopen(req, timeout=40) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            raw_reply = res_json["choices"][0]["message"]["content"].strip()

            if "```json" in raw_reply:
                raw_reply = raw_reply.split("```json")[1].split("```")[0]
            elif "```" in raw_reply:
                raw_reply = raw_reply.split("```")[1].split("```")[0]

            parsed_list = json.loads(raw_reply.strip())
            if isinstance(parsed_list, list) and len(parsed_list) > 0:
                print(f"[LLM] 大模型分析成功 ({reasoning_level} 强度)！生成 {len(parsed_list)} 条精选专业点评。")
                return parsed_list

    except urllib.error.HTTPError as e:
        err_detail = ""
        try:
            err_detail = e.read().decode("utf-8")
        except Exception:
            pass
        print(f"[LLM 接口错误 HTTP {e.code}] {e.reason} -> 详情: {err_detail}")
    except Exception as e:
        print(f"[LLM 异常] 调用大模型分析异常: {e}，自动降级为原始资讯。")

    return news_list

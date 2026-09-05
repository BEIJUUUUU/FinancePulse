"""
大模型 (LLM) 财经分析与点评引擎
全兼容 OpenAI 标准接口协议，内置各大主流服务商快速预设：
- DeepSeek (深度求索)
- Kimi / Moonshot (月之暗面)
- 智谱 AI (GLM-4-Flash / GLM-4)
- 阿里通义千问 (Qwen-Turbo / Qwen-Plus)
- OpenAI (GPT-4o-mini / GPT-4o)
- Ollama 本地开源大模型 (Qwen / Llama，无需 API Key)
- 自定义兼容接口 (Custom)
"""
import json
import urllib.request
import urllib.error

# 预设各大服务商的推荐配置
LLM_PROVIDERS = {
    "DeepSeek (深度求索)": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "note": "超高性价比，逻辑分析能力强 (推荐)"
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

PROMPT_SYSTEM = """你是一位资深的宏观经济与证券市场投研分析师。
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

def analyze_news_with_llm(
    news_list: list[dict],
    api_key: str = "",
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-chat"
) -> list[dict]:
    """
    调用大模型对财经资讯进行深度结构化分析与点评
    """
    if not news_list:
        return []

    # 如果是本地 Ollama，允许 api_key 为空或填 ollama
    if "localhost" in base_url or "127.0.0.1" in base_url:
        if not api_key:
            api_key = "ollama"
    elif not api_key:
        print("[LLM] 未配置 API_KEY，跳过大模型分析。")
        return news_list

    # 规范 base_url 补全
    endpoint = base_url.rstrip("/")
    if not endpoint.endswith("/v1") and not endpoint.endswith("/chat/completions"):
        endpoint = f"{endpoint}/v1/chat/completions"
    elif endpoint.endswith("/v1"):
        endpoint = f"{endpoint}/chat/completions"

    # 整理输入的新闻文本
    input_texts = []
    for idx, item in enumerate(news_list, 1):
        input_texts.append(f"{idx}. [{item.get('time', '')}] {item.get('title', '')} - {item.get('content', '')}")
    user_prompt = "以下是最新抓取的全球与国内财经快讯列表，请精选并给出专业投研点评：\n" + "\n".join(input_texts)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": PROMPT_SYSTEM},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2
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

        with urllib.request.urlopen(req, timeout=35) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            raw_reply = res_json["choices"][0]["message"]["content"].strip()

            # 清洗包裹的 json markdown 代码块
            if "```json" in raw_reply:
                raw_reply = raw_reply.split("```json")[1].split("```")[0]
            elif "```" in raw_reply:
                raw_reply = raw_reply.split("```")[1].split("```")[0]

            parsed_list = json.loads(raw_reply.strip())
            if isinstance(parsed_list, list) and len(parsed_list) > 0:
                print(f"[LLM] 大模型分析成功！生成了 {len(parsed_list)} 条精选点评。")
                return parsed_list

    except Exception as e:
        print(f"[LLM 异常] 调用大模型分析异常: {e}，自动降级为原始资讯。")

    return news_list

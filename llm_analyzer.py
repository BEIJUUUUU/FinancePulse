"""
大模型 (LLM) 财经分析与点评引擎
支持动态自定义 Prompt、自动获取可用模型列表、行业利好/利空细分与影响程度分级
"""
import json
import urllib.request
import urllib.error

LLM_PROVIDERS = {
    "DeepSeek (深度求索)": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
        "note": "支持 deepseek-v4-flash / deepseek-v4-pro / deepseek-chat"
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

DEFAULT_SYSTEM_PROMPT = """你是一位资深的证券市场与宏观经济投研分析师。
请对输入的财经快讯列表进行专业过滤、深度研判与行业影响分级：
1. 挑选出具有投资决策价值的核心事件；
2. 为每条资讯提供精练标题(15字内)与事实摘要(50字内)；
3. 明确指出【潜在受益行业】与【潜在受损行业】；
4. 明确评估【市场影响程度】（可选: 重大影响 / 中度影响 / 轻度扰动）；
5. 输出一句话【投研视点】(30字内)，给出客观逻辑传导；
6. 情绪导向标注为【利好】/【利空】/【中性】。

请严格返回如下 JSON 数组格式（严禁输出任何 markdown 格式标记、反引号或多余文字）：
[
  {
    "time": "原始时间",
    "title": "精练标题(15字内)",
    "content": "核心事实摘要(50字内)",
    "ai_comment": "一句话投研视点(30字内)",
    "tag": "所属领域(宏观/A股/美股/产业/大宗)",
    "sentiment": "利好/利空/中性",
    "impact_degree": "重大影响/中度影响/轻度扰动",
    "beneficiary": "潜在受益行业或板块(如: 算力硬件、半导体材料，无则填无)",
    "adverse": "潜在受损行业或板块(如: 传统燃油车、海外高负债资产，无则填无)"
  }
]
"""

REASONING_PROMPTS = {
    "fast": {
        "temperature": 0.1,
        "suffix": "\n[分析模式: 快速提炼，紧扣核心事实，极简输出。分析结果仅供参考，不构成投资建议。]"
    },
    "balanced": {
        "temperature": 0.3,
        "suffix": "\n[分析模式: 深度研判，兼顾宏观政策传导与产业链上下游关联。分析结果仅供参考，不构成投资建议。]"
    },
    "deep": {
        "temperature": 0.5,
        "suffix": "\n[分析模式: 长链推演，深度挖掘次级传导逻辑与行业分化。分析结果仅供参考，不构成投资建议。]"
    }
}

def fetch_available_models(base_url: str, api_key: str = "") -> list[str]:
    """
    通过 GET /v1/models 自动查询当前 API Key 支持的可用模型列表
    """
    if not base_url:
        return []

    endpoint = base_url.rstrip("/")
    if not endpoint.endswith("/v1") and not endpoint.endswith("/models"):
        endpoint = f"{endpoint}/v1/models"
    elif endpoint.endswith("/v1"):
        endpoint = f"{endpoint}/models"

    headers = {
        "User-Agent": "FinancePulse/2.5"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        req = urllib.request.Request(endpoint, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            model_items = data.get("data", [])
            model_ids = []
            for item in model_items:
                if isinstance(item, dict) and "id" in item:
                    model_ids.append(item["id"])
            if model_ids:
                model_ids.sort()
                print(f"[LLM] 成功获取到 {len(model_ids)} 个可用模型: {model_ids[:5]}...")
                return model_ids
    except Exception as e:
        print(f"[LLM 提示] 获取模型列表异常: {e}")

    return []

def analyze_news_with_llm(
    news_list: list[dict],
    api_key: str = "",
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-v4-flash",
    system_prompt: str = "",
    reasoning_level: str = "balanced",
    max_analyze: int = 15
) -> list[dict]:
    """
    调用大模型对财经资讯进行深度结构化分析与行业利好利空研判
    :param max_analyze: 单次分析最大上限(默认15条最关键快讯，保证3-8秒内极速返回防超时)
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

    # 截取前 max_analyze 条进行深度 AI 研判，杜绝超长 prompt 导致网络超时
    target_news = news_list[:max_analyze]
    input_texts = []
    for idx, item in enumerate(target_news, 1):
        input_texts.append(f"{idx}. [{item.get('time', '')}] {item.get('title', '')} - {item.get('content', '')}")
    user_prompt = "以下是精选财经快讯列表，请提炼要闻并输出行业利好利空与影响程度：\n" + "\n".join(input_texts)

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

        with urllib.request.urlopen(req, timeout=45) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            raw_reply = res_json["choices"][0]["message"]["content"].strip()

            if "```json" in raw_reply:
                raw_reply = raw_reply.split("```json")[1].split("```")[0]
            elif "```" in raw_reply:
                raw_reply = raw_reply.split("```")[1].split("```")[0]

            parsed_list = json.loads(raw_reply.strip())
            if isinstance(parsed_list, list) and len(parsed_list) > 0:
                print(f"[LLM] 大模型分析成功 ({model})！成功生成 {len(parsed_list)} 条精选专业行业研判。")
                # 如果用户抓取条数多于已分析条数，将剩余原始资讯拼接在后，保证完整性
                if len(news_list) > max_analyze:
                    parsed_list.extend(news_list[max_analyze:])
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

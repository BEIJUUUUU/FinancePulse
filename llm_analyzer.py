"""
大模型 (LLM) 财经分析与点评引擎
分片并发研判：每组少量快讯独立请求，保证单条分析细节与诊断模式同级
支持动态自定义 Prompt、自动获取可用模型列表、行业利好/利空细分与影响程度分级
"""
import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

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
2. 为每条资讯提供精练标题(15字内)与事实要点摘要(80字内，必须保留关键数字、政策主体与具体动作，禁止过度压缩)；
3. 明确指出【潜在受益行业】与【潜在受损行业】(必须具体到细分板块，如"光模块/CPO"、"存储芯片"、"白酒消费"，多个用顿号分隔，确无影响则填"无")；
4. 明确评估【市场影响程度】(可选: 重大影响 / 中度影响 / 轻度扰动)；
5. 输出【投研视点】(50字内，需写清逻辑传导路径，如"政策落地→需求回暖→板块估值修复")；
6. 情绪导向标注为【利好】/【利空】/【中性】。

注意：即使一次输入多条快讯，每一条的分析深度都必须与单条分析时保持同等细节，严禁偷懒压缩。

请严格返回如下 JSON 数组格式（严禁输出任何 markdown 格式标记、反引号或多余文字）：
[
  {
    "time": "原始时间",
    "title": "精练标题(15字内)",
    "content": "事实要点摘要(80字内，保留关键数字与主体)",
    "ai_comment": "投研视点(50字内，含逻辑传导路径)",
    "tag": "所属领域(宏观/A股/美股/产业/大宗)",
    "sentiment": "利好/利空/中性",
    "impact_degree": "重大影响/中度影响/轻度扰动",
    "beneficiary": "潜在受益行业(细分板块，无则填无)",
    "adverse": "潜在受损行业(细分板块，无则填无)"
  }
]
"""

REASONING_PROMPTS = {
    "fast": {
        "temperature": 0.1,
        "suffix": "\n[分析模式: 快速提炼，紧扣核心事实。分析结果仅供参考，不构成投资建议。]"
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
    """通过 GET /v1/models 自动查询当前 API Key 支持的可用模型列表"""
    if not base_url:
        return []

    endpoint = base_url.rstrip("/")
    if not endpoint.endswith("/v1") and not endpoint.endswith("/models"):
        endpoint = f"{endpoint}/v1/models"
    elif endpoint.endswith("/v1"):
        endpoint = f"{endpoint}/models"

    headers = {"User-Agent": "FinancePulse/2.5"}
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
                return model_ids
    except Exception as e:
        print(f"[LLM 提示] 获取模型列表异常: {e}")

    return []

def _call_chat(endpoint: str, api_key: str, payload: dict, timeout: int = 60) -> list[dict]:
    """底层单次大模型调用，返回解析后的 JSON 数组"""
    data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data_bytes,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )

    with urllib.request.urlopen(req, timeout=timeout) as response:
        res_body = response.read().decode("utf-8")
        res_json = json.loads(res_body)
        raw_reply = res_json["choices"][0]["message"]["content"].strip()

        if "```json" in raw_reply:
            raw_reply = raw_reply.split("```json")[1].split("```")[0]
        elif "```" in raw_reply:
            raw_reply = raw_reply.split("```")[1].split("```")[0]

        parsed = json.loads(raw_reply.strip())
        return parsed if isinstance(parsed, list) else []

def _analyze_chunk(
    chunk: list[dict],
    endpoint: str,
    api_key: str,
    model: str,
    full_prompt: str,
    temperature: float
) -> list[dict]:
    """分析单个分片 (少量条目)，确保每条获得与单条诊断同级的分析细节"""
    input_texts = []
    for idx, item in enumerate(chunk, 1):
        input_texts.append(f"{idx}. [{item.get('time', '')}] {item.get('title', '')} - {item.get('content', '')}")
    user_prompt = "以下是精选财经快讯列表，请逐条深度研判并输出行业利好利空与影响程度分级：\n" + "\n".join(input_texts)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": full_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temperature
    }

    try:
        parsed = _call_chat(endpoint, api_key, payload, timeout=90)
        if parsed:
            # 按位置回填原始信源
            for i, p_item in enumerate(parsed):
                if isinstance(p_item, dict) and not p_item.get("source") and i < len(chunk):
                    p_item["source"] = chunk[i].get("source", "实时快讯")
            return parsed
    except urllib.error.HTTPError as e:
        err_detail = ""
        try:
            err_detail = e.read().decode("utf-8")
        except Exception:
            pass
        print(f"[LLM 接口错误 HTTP {e.code}] {e.reason} -> 详情: {err_detail[:200]}")
    except Exception as e:
        print(f"[LLM 分片异常] {e}，该分片降级为原始资讯。")

    return list(chunk)

def analyze_news_with_llm(
    news_list: list[dict],
    api_key: str = "",
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-v4-flash",
    system_prompt: str = "",
    reasoning_level: str = "balanced",
    max_analyze: int = 12,
    chunk_size: int = 4
) -> list[dict]:
    """
    调用大模型对财经资讯进行深度结构化分析与行业利好利空研判
    采用分片并发策略：每片仅含 chunk_size 条，多片同时请求，
    既保证单条分析细节与诊断模式同级，又维持整体响应速度不变。
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

    prompt_config = REASONING_PROMPTS.get(reasoning_level, REASONING_PROMPTS["balanced"])
    base_prompt = system_prompt.strip() if system_prompt and system_prompt.strip() else DEFAULT_SYSTEM_PROMPT.strip()
    full_prompt = base_prompt + prompt_config["suffix"]

    target_news = list(news_list)[:max_analyze]
    chunks = [target_news[i:i + chunk_size] for i in range(0, len(target_news), chunk_size)]

    # 分片并发研判 (多路同时请求，总耗时 ≈ 单片耗时；实测 3 路并发为吞吐最优解)
    results_by_index = {}
    with ThreadPoolExecutor(max_workers=min(3, len(chunks))) as executor:
        future_to_idx = {
            executor.submit(
                _analyze_chunk, chunk, endpoint, api_key, model,
                full_prompt, prompt_config["temperature"]
            ): ci for ci, chunk in enumerate(chunks)
        }
        for future in as_completed(future_to_idx):
            ci = future_to_idx[future]
            try:
                results_by_index[ci] = future.result()
            except Exception as e:
                print(f"[LLM 并发异常] {e}")
                results_by_index[ci] = chunks[ci]

    # 按原始顺序拼接，超出分析上限的直接保留原始资讯
    final = []
    for ci in sorted(results_by_index.keys()):
        final.extend(results_by_index[ci])
    if len(news_list) > max_analyze:
        final.extend(news_list[max_analyze:])

    ok_count = sum(1 for x in final if isinstance(x, dict) and x.get("ai_comment"))
    print(f"[LLM] 大模型分片并发研判完成 ({model})，{len(chunks)} 路并发，成功生成 {ok_count} 条深度行业分析。")
    return final

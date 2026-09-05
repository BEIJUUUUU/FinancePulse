"""
资讯处理模块：多维相似度智能去重、领域分类过滤、行业利好/利空细分与苹果风研报生成
"""
import csv
import difflib
from datetime import datetime

# 权威领域分类词典
CATEGORY_KEYWORDS = {
    "科技产业": [
        "AI", "人工智能", "算力", "芯片", "半导体", "光模块", "具身智能", "机器人",
        "大模型", "自动驾驶", "智能汽车", "锂电", "电池", "储能", "光伏", "低空经济",
        "新能源", "智能终端", "英伟达", "华为", "苹果", "鸿海", "OpenAI", "软银", "通信"
    ],
    "A股市场": [
        "A股", "沪指", "深成指", "创业板", "科创板", "上交所", "深交所", "证监会",
        "券商", "中证协", "涨停", "跌停", "增持", "回购", "减持", "分红", "净利",
        "业绩", "上市公司", "ETF", "两市", "融资融券", "龙虎榜", "IPO", "股票"
    ],
    "宏观政策": [
        "央行", "财政部", "发改委", "降息", "降准", "公开市场", "逆回购", "国债",
        "利率", "汇率", "通胀", "CPI", "PPI", "GDP", "稳增长", "稳就业", "货币政策",
        "财政政策", "国务院", "宏观", "管委会"
    ],
    "大宗商品": [
        "原油", "布伦特", "WTI", "黄金", "贵金属", "白银", "铜", "铝", "钢铁",
        "煤炭", "天然气", "现货", "期货", "铁矿石", "油价", "粮食", "农产品", "产气"
    ],
    "全球要闻": [
        "美联储", "美股", "纳斯达克", "道琼斯", "标普", "欧洲央行", "非农", "外贸",
        "出口", "美债", "特使", "停火", "俄乌", "中东", "加息", "国际", "莫斯科", "俄罗斯", "乌克兰"
    ],
    "社会民生": [
        "暴雨", "洪涝", "汛限", "水库", "泥石流", "台风", "抢险", "遇难", "搜救",
        "地质灾害", "通报", "违规", "立案", "染色", "莴笋", "降温", "受灾", "民用", "事故"
    ]
}

def detect_category(title: str, content: str) -> str:
    """基于词典多重加权算法自动识别资讯所属领域"""
    text = f"{title} {title} {content}".lower()  # 标题双倍权重
    best_cat = "综合财经"
    max_score = 0

    for cat, kws in CATEGORY_KEYWORDS.items():
        score = 0
        for kw in kws:
            if kw.lower() in text:
                # 标题命中加 3 分，正文命中加 1 分
                if kw.lower() in title.lower():
                    score += 3
                else:
                    score += 1
        if score > max_score:
            max_score = score
            best_cat = cat

    return best_cat

def _calculate_similarity(text1: str, text2: str) -> float:
    """计算两篇快讯的综合相似度 (序列匹配 + 字符二元组重叠)"""
    if not text1 or not text2:
        return 0.0
    if text1 == text2 or text1 in text2 or text2 in text1:
        return 1.0

    seq_ratio = difflib.SequenceMatcher(None, text1, text2).ratio()
    grams1 = set(text1[i:i+2] for i in range(len(text1)-1))
    grams2 = set(text2[i:i+2] for i in range(len(text2)-1))
    jaccard = len(grams1 & grams2) / len(grams1 | grams2) if (grams1 and grams2) else 0.0

    return 0.5 * seq_ratio + 0.5 * jaccard

def filter_and_clean_news(
    news_list: list[dict],
    keywords: list[str] = None,
    allowed_categories: list[str] = None,
    dedup_threshold: float = 0.48,
    max_limit: int = 20
) -> list[dict]:
    """
    智能领域分类过滤与跨源相似度去重
    :param allowed_categories: 允许保留的领域列表 (如: ['科技产业', 'A股市场', '宏观政策'])
    """
    if not news_list:
        return []

    # 1. 领域自动识别与初筛
    filtered = []
    for item in news_list:
        title = item.get("title", "").strip()
        content = item.get("content", "").strip()
        if not title:
            continue

        # 自动判定并赋予领域标签 (若原本未打标)
        if not item.get("tag") or item.get("tag") == "综合":
            item["tag"] = detect_category(title, content)

        # 领域分类过滤：如果不属于用户勾选的领域，直接剔除！
        if allowed_categories and len(allowed_categories) > 0:
            if item["tag"] not in allowed_categories:
                continue

        # 关键词过滤
        if keywords:
            full_text = title + content
            if not any(kw.lower() in full_text.lower() for kw in keywords):
                continue

        filtered.append(item)

    # 2. 跨源相似度去重
    unique_items = []
    for item in filtered:
        item_title = item.get("title", "")
        item_content = item.get("content", "")
        is_duplicate = False

        for existing in unique_items:
            ex_title = existing.get("title", "")
            ex_content = existing.get("content", "")

            title_sim = _calculate_similarity(item_title, ex_title)
            content_sim = _calculate_similarity(item_content[:40], ex_content[:40])
            max_sim = max(title_sim, content_sim)

            if max_sim >= dedup_threshold:
                is_duplicate = True
                src1 = existing.get("source", "")
                src2 = item.get("source", "")
                if src2 and src2 not in src1:
                    existing["source"] = f"{src1} · {src2}"
                if len(item_content) > len(existing.get("content", "")):
                    existing["content"] = item_content
                break

        if not is_duplicate:
            unique_items.append(item)

        if len(unique_items) >= max_limit:
            break

    return unique_items

def build_html_card(news_list: list[dict]) -> str:
    """生成具备 Apple 极简现代设计语言的 HTML 邮件研报"""
    if not news_list:
        return "<p>暂无最新快讯。</p>"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    rows_html = []
    for idx, item in enumerate(news_list, 1):
        t = item.get("time", "")
        title = item.get("title", "")
        content = item.get("content", "")
        ai_comment = item.get("ai_comment", "")
        sentiment = item.get("sentiment", "")
        impact = item.get("impact_degree", "")
        beneficiary = item.get("beneficiary", "")
        adverse = item.get("adverse", "")
        tag = item.get("tag", "综合")
        source = item.get("source", "权威快讯")

        sentiment_badge = ""
        if sentiment:
            sent_color = "#dc2626" if "利好" in sentiment else ("#16a34a" if "利空" in sentiment else "#64748b")
            sent_bg = "#fee2e2" if "利好" in sentiment else ("#dcfce7" if "利空" in sentiment else "#f1f5f9")
            sent_txt = f"{sentiment}" + (f" · {impact}" if impact else "")
            sentiment_badge = f'<span style="background: {sent_bg}; color: {sent_color}; font-size: 11px; padding: 2px 8px; border-radius: 9999px; font-weight: 600; margin-left: 6px;">{sent_txt}</span>'

        tag_badge = f'<span style="background: #f3f4f6; color: #4b5563; font-size: 11px; padding: 2px 7px; border-radius: 9999px; margin-left: 4px;">{tag}</span>'

        industry_bar = ""
        if (beneficiary and beneficiary != "无") or (adverse and adverse != "无"):
            ben_txt = f'<span style="color: #15803d; font-weight: 600;">受益: {beneficiary}</span>' if (beneficiary and beneficiary != "无") else ""
            adv_txt = f'<span style="color: #b91c1c; font-weight: 600; margin-left: 10px;">受损: {adverse}</span>' if (adverse and adverse != "无") else ""
            industry_bar = f"""
            <div style="margin-top: 6px; font-size: 11px; background: #f8fafc; padding: 4px 8px; border-radius: 6px; display: inline-block;">
                {ben_txt} {adv_txt}
            </div>
            """

        ai_box = ""
        if ai_comment:
            ai_box = f"""
            <div style="margin-top: 8px; background: #f5f3ff; border-left: 3px solid #7c3aed; padding: 8px 12px; border-radius: 0 8px 8px 0; font-size: 12px; color: #5b21b6; line-height: 1.5;">
                <b>AI 投研视点：</b>{ai_comment} <span style="font-size: 10px; color: #8b5cf6; margin-left: 4px;">(仅供参考)</span>
            </div>
            """

        rows_html.append(f"""
        <div style="background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
            <div style="display: flex; align-items: center; margin-bottom: 6px;">
                <span style="display: inline-block; background: #2563eb; color: #ffffff; font-size: 11px; font-weight: bold; padding: 2px 6px; border-radius: 6px; margin-right: 8px;">#{idx}</span>
                <span style="font-size: 12px; color: #6b7280; font-family: monospace;">{t} · {source}</span>
                <span style="margin-left: auto;">{tag_badge} {sentiment_badge}</span>
            </div>
            <div style="font-size: 14px; font-weight: 700; color: #111827; line-height: 1.4; margin-bottom: 6px;">
                {title}
            </div>
            <div style="font-size: 12px; color: #4b5563; line-height: 1.6;">
                {content}
            </div>
            {industry_bar}
            {ai_box}
        </div>
        """)

    cards_body = "".join(rows_html)

    html_template = f"""
    <div style="max-width: 680px; margin: 0 auto; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; padding: 20px;">
        <div style="margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid #e2e8f0;">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <h2 style="margin: 0; font-size: 20px; font-weight: 800; color: #0f172a; letter-spacing: -0.3px;">财经脉搏 · 智能快讯研报</h2>
                <span style="background: #2563eb; color: #ffffff; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 9999px;">Pro</span>
            </div>
            <p style="margin: 6px 0 0 0; font-size: 12px; color: #64748b;">报告时间：{now_str} ｜ 领域分类过滤 ｜ 行业影响研判</p>
        </div>

        {cards_body}

        <div style="margin-top: 14px; font-size: 11px; color: #94a3b8; text-align: center;">
            本报告由 FinancePulse 自动化生成，信息与情绪判断仅供决策参考，不构成直接投资建议。
        </div>
    </div>
    """
    return html_template

def build_markdown_table(news_list: list[dict]) -> str:
    """生成精简 Markdown 表格"""
    if not news_list:
        return "暂无最新快讯。"

    lines = [
        "| 序号 | 时间 | 领域 | 核心要闻 | 情绪与影响 | 受益/受损行业 | 投研视点 |",
        "| :---: | :---: | :---: | :--- | :---: | :--- | :--- |"
    ]

    for idx, item in enumerate(news_list, 1):
        t = item.get("time", "")
        tag = item.get("tag", "综合")
        title = item.get("title", "").replace("|", " ")
        sentiment = item.get("sentiment", "中性")
        impact = item.get("impact_degree", "")
        sent_str = f"{sentiment} ({impact})" if impact else sentiment
        
        ben = item.get("beneficiary", "无")
        adv = item.get("adverse", "无")
        ind_str = f"益:{ben}; 损:{adv}" if (ben != "无" or adv != "无") else "无明显分化"
        
        ai_comment = item.get("ai_comment", item.get("content", "")[:35] + "...")

        lines.append(f"| **{idx}** | `{t}` | {tag} | **{title}** | {sent_str} | {ind_str} | {ai_comment} |")

    return "\n".join(lines)

def export_to_excel(news_list: list[dict], output_path: str = "财经热点汇总.csv") -> str:
    """导出为本地表格文件"""
    if not news_list:
        return output_path

    try:
        import pandas as pd
        df = pd.DataFrame(news_list)
        column_mapping = {
            "time": "发布时间",
            "title": "新闻标题",
            "tag": "所属领域",
            "content": "核心内容",
            "ai_comment": "AI投研视点",
            "sentiment": "情绪导向",
            "impact_degree": "影响程度",
            "beneficiary": "潜在受益行业",
            "adverse": "潜在受损行业",
            "source": "信源"
        }
        df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns}, inplace=True)
        xlsx_path = output_path.replace(".csv", ".xlsx")
        df.to_excel(xlsx_path, index=False)
        return xlsx_path
    except Exception:
        csv_path = output_path.replace(".xlsx", ".csv")
        all_keys = []
        for item in news_list:
            if isinstance(item, dict):
                for k in item.keys():
                    if k not in all_keys:
                        all_keys.append(k)

        with open(csv_path, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
            writer.writeheader()
            for row in news_list:
                writer.writerow(row)
        return csv_path

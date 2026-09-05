"""
资讯处理模块：多维相似度智能去重、行业利好/利空细分、影响程度分级与苹果风研报生成
"""
import csv
import difflib
from datetime import datetime

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
    dedup_threshold: float = 0.48,
    max_limit: int = 20
) -> list[dict]:
    """智能去重与关键词过滤"""
    if not news_list:
        return []

    filtered = []
    for item in news_list:
        title = item.get("title", "").strip()
        content = item.get("content", "").strip()
        if not title:
            continue

        if keywords:
            full_text = title + content
            if not any(kw.lower() in full_text.lower() for kw in keywords):
                continue
        filtered.append(item)

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
    """生成具备 Apple 极简现代设计语言的 HTML 邮件研报 (包含行业细分与影响分级)"""
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
        tag = item.get("tag", "")
        source = item.get("source", "权威快讯")

        sentiment_badge = ""
        if sentiment:
            sent_color = "#dc2626" if "利好" in sentiment else ("#16a34a" if "利空" in sentiment else "#64748b")
            sent_bg = "#fee2e2" if "利好" in sentiment else ("#dcfce7" if "利空" in sentiment else "#f1f5f9")
            sent_txt = f"{sentiment}" + (f" · {impact}" if impact else "")
            sentiment_badge = f'<span style="background: {sent_bg}; color: {sent_color}; font-size: 11px; padding: 2px 8px; border-radius: 9999px; font-weight: 600; margin-left: 6px;">{sent_txt}</span>'

        tag_badge = f'<span style="background: #f3f4f6; color: #4b5563; font-size: 11px; padding: 2px 7px; border-radius: 9999px; margin-left: 4px;">{tag}</span>' if tag else ""

        # 行业受影响分析栏
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
            <p style="margin: 6px 0 0 0; font-size: 12px; color: #64748b;">报告时间：{now_str} ｜ 多源聚合去重 ｜ 行业影响研判</p>
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
        "| 序号 | 时间 | 来源 | 核心要闻 | 情绪与影响 | 受益/受损行业 | 投研视点 |",
        "| :---: | :---: | :---: | :--- | :---: | :--- | :--- |"
    ]

    for idx, item in enumerate(news_list, 1):
        t = item.get("time", "")
        src = item.get("source", "快讯")
        title = item.get("title", "").replace("|", " ")
        sentiment = item.get("sentiment", "中性")
        impact = item.get("impact_degree", "")
        sent_str = f"{sentiment} ({impact})" if impact else sentiment
        
        ben = item.get("beneficiary", "无")
        adv = item.get("adverse", "无")
        ind_str = f"益:{ben}; 损:{adv}" if (ben != "无" or adv != "无") else "无明显分化"
        
        ai_comment = item.get("ai_comment", item.get("content", "")[:35] + "...")

        lines.append(f"| **{idx}** | `{t}` | {src} | **{title}** | {sent_str} | {ind_str} | {ai_comment} |")

    return "\n".join(lines)

def export_to_excel(news_list: list[dict], output_path: str = "财经热点汇总.csv") -> str:
    """导出为本地表格文件"""
    try:
        import pandas as pd
        df = pd.DataFrame(news_list)
        column_mapping = {
            "time": "发布时间",
            "title": "新闻标题",
            "content": "核心内容",
            "ai_comment": "AI点评",
            "sentiment": "情绪导向",
            "impact_degree": "影响程度",
            "beneficiary": "潜在受益行业",
            "adverse": "潜在受损行业",
            "tag": "所属领域",
            "source": "信源"
        }
        df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns}, inplace=True)
        xlsx_path = output_path.replace(".csv", ".xlsx")
        df.to_excel(xlsx_path, index=False)
        return xlsx_path
    except ImportError:
        csv_path = output_path.replace(".xlsx", ".csv")
        with open(csv_path, mode="w", newline="", encoding="utf-8-sig") as f:
            if news_list:
                fields = list(news_list[0].keys())
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                for row in news_list:
                    writer.writerow(row)
        return csv_path

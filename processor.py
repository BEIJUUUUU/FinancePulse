"""
资讯处理模块：多维相似度智能去重、关键词过滤、结构化表格与苹果风研报生成
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

    # 1. 序列相似度
    seq_ratio = difflib.SequenceMatcher(None, text1, text2).ratio()

    # 2. 2-gram 字符集合重叠度 (Jaccard)
    grams1 = set(text1[i:i+2] for i in range(len(text1)-1))
    grams2 = set(text2[i:i+2] for i in range(len(text2)-1))
    if grams1 and grams2:
        jaccard = len(grams1 & grams2) / len(grams1 | grams2)
    else:
        jaccard = 0.0

    return 0.5 * seq_ratio + 0.5 * jaccard

def filter_and_clean_news(
    news_list: list[dict],
    keywords: list[str] = None,
    dedup_threshold: float = 0.48,
    max_limit: int = 20
) -> list[dict]:
    """
    智能去重与关键词过滤
    :param dedup_threshold: 相似度判定阈值 (默认 0.48，超过则视为同一事件报道并自动合并)
    """
    if not news_list:
        return []

    # 1. 关键词过滤
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

    # 2. 相似度去重与跨源信息聚合
    unique_items = []
    for item in filtered:
        item_title = item.get("title", "")
        item_content = item.get("content", "")
        is_duplicate = False

        for existing in unique_items:
            ex_title = existing.get("title", "")
            ex_content = existing.get("content", "")

            # 比较标题以及前 40 字内容
            title_sim = _calculate_similarity(item_title, ex_title)
            content_sim = _calculate_similarity(item_content[:40], ex_content[:40])
            max_sim = max(title_sim, content_sim)

            if max_sim >= dedup_threshold:
                # 判定为同一新闻事件！合并信源
                is_duplicate = True
                src1 = existing.get("source", "")
                src2 = item.get("source", "")
                if src2 and src2 not in src1:
                    existing["source"] = f"{src1} · {src2}"
                # 保留更详尽的内容
                if len(item_content) > len(existing.get("content", "")):
                    existing["content"] = item_content
                break

        if not is_duplicate:
            unique_items.append(item)

        if len(unique_items) >= max_limit:
            break

    print(f"[智能去重] 原始拉取 {len(news_list)} 条，清洗去重后保留 {len(unique_items)} 条高质量不重复快讯。")
    return unique_items

def build_html_card(news_list: list[dict]) -> str:
    """生成具备 Apple 极简现代设计语言的 HTML 邮件报告"""
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
        tag = item.get("tag", "")
        source = item.get("source", "权威快讯")

        sentiment_badge = ""
        if "利好" in sentiment:
            sentiment_badge = '<span style="background: #fee2e2; color: #dc2626; font-size: 11px; padding: 2px 7px; border-radius: 9999px; font-weight: 600; margin-left: 6px;">🔴 利好</span>'
        elif "利空" in sentiment:
            sentiment_badge = '<span style="background: #dcfce7; color: #16a34a; font-size: 11px; padding: 2px 7px; border-radius: 9999px; font-weight: 600; margin-left: 6px;">🟢 利空</span>'
        elif sentiment:
            sentiment_badge = f'<span style="background: #f1f5f9; color: #64748b; font-size: 11px; padding: 2px 7px; border-radius: 9999px; font-weight: 600; margin-left: 6px;">⚪ {sentiment}</span>'

        tag_badge = f'<span style="background: #f3f4f6; color: #4b5563; font-size: 11px; padding: 2px 7px; border-radius: 9999px; margin-left: 4px;">{tag}</span>' if tag else ""

        ai_box = ""
        if ai_comment:
            ai_box = f"""
            <div style="margin-top: 8px; background: #f5f3ff; border-left: 3px solid #7c3aed; padding: 8px 12px; border-radius: 0 8px 8px 0; font-size: 12px; color: #5b21b6; line-height: 1.5;">
                <b>🤖 AI 投研视点：</b>{ai_comment}
            </div>
            """

        rows_html.append(f"""
        <div style="background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
            <div style="display: flex; align-items: center; margin-bottom: 6px;">
                <span style="display: inline-block; background: #2563eb; color: #ffffff; font-size: 11px; font-weight: bold; padding: 2px 6px; border-radius: 6px; margin-right: 8px;">#{idx}</span>
                <span style="font-size: 12px; color: #6b7280; font-family: monospace;">🕒 {t} · {source}</span>
                <span style="margin-left: auto;">{tag_badge} {sentiment_badge}</span>
            </div>
            <div style="font-size: 14px; font-weight: 700; color: #111827; line-height: 1.4; margin-bottom: 6px;">
                {title}
            </div>
            <div style="font-size: 12px; color: #4b5563; line-height: 1.6;">
                {content}
            </div>
            {ai_box}
        </div>
        """)

    cards_body = "".join(rows_html)

    html_template = f"""
    <div style="max-width: 680px; margin: 0 auto; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; padding: 20px;">
        <!-- 头部 -->
        <div style="margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid #e2e8f0;">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <h2 style="margin: 0; font-size: 20px; font-weight: 800; color: #0f172a; letter-spacing: -0.3px;">📈 财经脉搏 · 智能早报</h2>
                <span style="background: #2563eb; color: #ffffff; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 9999px;">Pro</span>
            </div>
            <p style="margin: 6px 0 0 0; font-size: 12px; color: #64748b;">🕒 报告时间：{now_str} ｜ 多源聚合去重 ｜ AI 智能研判</p>
        </div>

        <!-- 资讯列表 -->
        {cards_body}

        <!-- 底部 -->
        <div style="margin-top: 14px; font-size: 11px; color: #94a3b8; text-align: center;">
            💡 本报告由 FinancePulse 自动化生成，信息仅供决策参考，不构成直接投资建议。
        </div>
    </div>
    """
    return html_template

def build_markdown_table(news_list: list[dict]) -> str:
    """生成精简 Markdown 表格"""
    if not news_list:
        return "暂无最新快讯。"

    lines = [
        "| 序号 | 时间 | 来源 | 核心要闻 | 情绪 | 摘要/AI点评 |",
        "| :---: | :---: | :---: | :--- | :---: | :--- |"
    ]

    for idx, item in enumerate(news_list, 1):
        t = item.get("time", "")
        src = item.get("source", "快讯")
        title = item.get("title", "").replace("|", " ")
        content = item.get("content", "").replace("|", " ")
        sentiment = item.get("sentiment", "中性")
        ai_comment = item.get("ai_comment", "")

        summary_show = f"{content[:40]}..."
        if ai_comment:
            summary_show += f" (💡AI: {ai_comment})"

        lines.append(f"| **{idx}** | `{t}` | {src} | **{title}** | {sentiment} | {summary_show} |")

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

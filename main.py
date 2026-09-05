"""
主程序入口：调度资讯抓取、清洗加工成表格并推送到个人邮箱 (附带微信提醒) / 飞书
支持调用大模型 (DeepSeek / OpenAI) 智能提炼核心事实与情绪点评
"""
import sys
import argparse
from datetime import datetime

import config
from fetcher import fetch_cls_news
from processor import filter_and_clean_news, build_markdown_table, build_html_card, export_to_excel
from email_sender import send_email_digest
from llm_analyzer import analyze_news_with_llm

def run_once():
    """执行一次完整的财经快讯获取、AI分析与邮件推送任务"""
    now_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now_time_str}] 🚀 开始抓取最新财经快讯...")
    
    # 1. 抓取快讯
    raw_news = fetch_cls_news(limit=config.NEWS_LIMIT)
    if not raw_news:
        print("[提示] 本次未获取到最新资讯，流程结束。")
        return

    # 2. 清洗过滤
    cleaned_news = filter_and_clean_news(raw_news, keywords=config.FILTER_KEYWORDS)
    print(f"[处理] 共获取到 {len(raw_news)} 条快讯，有效保留 {len(cleaned_news)} 条。")

    # 3. 若启用了大模型，调用 AI 进行研报提炼
    final_news = cleaned_news
    if config.LLM_ENABLED and config.LLM_API_KEY:
        print(f"[AI 分析] 正在调用大模型 ({config.LLM_MODEL}) 进行深度提炼与点评...")
        final_news = analyze_news_with_llm(
            cleaned_news,
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_BASE_URL,
            model=config.LLM_MODEL
        )

    # 4. 组织表格并导出 Excel/CSV 本地备份
    excel_file = "D:/Desktop/finance-news-bot/财经热点汇总.csv"
    try:
        export_to_excel(final_news, output_path=excel_file)
        print(f"[导出] 表格已同步导出至本地备份: {excel_file}")
    except Exception as e:
        print(f"[导出异常] 写入本地表格失败: {e}")

    # 5. 控制台预览文本表格
    markdown_table = build_markdown_table(final_news)
    print("\n--- [资讯研报表格预览] ---")
    print(markdown_table)
    print("---------------------------\n")

    # 6. 推送到邮箱 (支持直接在微信通过 QQ邮箱提醒 查看)
    if config.SENDER_EMAIL and config.SENDER_AUTH_CODE:
        receiver = config.RECEIVER_EMAIL or config.SENDER_EMAIL
        print(f"[邮件推送] 正在推送到邮箱: {receiver} ...")
        html_card = build_html_card(final_news)
        subject_str = f"📈 财经早报与智能热点精选 ({datetime.now().strftime('%m月%d日 %H:%M')})"
        send_email_digest(
            smtp_server=config.SMTP_SERVER,
            smtp_port=config.SMTP_PORT,
            sender_email=config.SENDER_EMAIL,
            sender_auth_code=config.SENDER_AUTH_CODE,
            receiver_email=receiver,
            subject=subject_str,
            html_content=html_card,
            attachment_path=excel_file
        )
    else:
        print("[提示] 尚未配置 SENDER_EMAIL 或 SENDER_AUTH_CODE。请在 config.py 或桌面 GUI 中配置。")

def main():
    parser = argparse.ArgumentParser(description="Finance News Bot - 财经早报与微信提醒助手")
    parser.add_argument("--cron", action="store_true", help="开启定时运行模式 (每天早中晚固定时间推送)")
    args = parser.parse_args()

    if args.cron:
        try:
            import schedule
            import time
            print("[模式] 已启动定时推送服务...")
            schedule.every().day.at("08:30").do(run_once)  # 盘前早报
            schedule.every().day.at("12:00").do(run_once)  # 午间回顾
            schedule.every().day.at("16:00").do(run_once)  # 盘后总结

            run_once()
            while True:
                schedule.run_pending()
                time.sleep(30)
        except ImportError:
            print("[错误] 未安装 schedule 依赖，请先运行: pip install schedule")
    else:
        run_once()

if __name__ == "__main__":
    main()

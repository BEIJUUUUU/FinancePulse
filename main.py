"""
FinancePulse - 命令行与 Docker / NAS 无人值守调度引擎
内置推送防重复、自选监控标记与突发要闻实时监控
"""
import sys
import os
import time
import argparse
from datetime import datetime

import config
import history_db
import flash_monitor
from fetcher import fetch_cls_news
from processor import filter_and_clean_news, mark_watchlist, prioritize_watchlist, build_markdown_table, build_html_card, export_to_excel
from email_sender import send_email_digest
from llm_analyzer import analyze_news_with_llm

def _flash_push(hits):
    """突发要闻即时推送回调 (秒级时效，不经 AI 分析)"""
    try:
        cfg = config.load_config()
        sender = cfg.get("sender_email")
        auth = cfg.get("sender_auth_code")
        receiver = cfg.get("receiver_email") or sender

        output_dir = os.path.dirname(__file__)
        csv_file = os.path.join(output_dir, "财经热点汇总.csv")
        export_to_excel(hits, output_path=csv_file)
        html_card = build_html_card(hits)
        subject = f"突发要闻提醒 ({datetime.now().strftime('%H:%M')})"

        if sender and auth:
            ok = send_email_digest(
                smtp_server=cfg.get("smtp_server", "smtp.qq.com"),
                smtp_port=int(cfg.get("smtp_port", 465)),
                sender_email=sender,
                sender_auth_code=auth,
                receiver_email=receiver,
                subject=subject,
                html_content=html_card,
                attachment_path=csv_file
            )
            if ok:
                history_db.record_pushed(hits)
                print(f"[突发推送] 已即时推送 {len(hits)} 条突发要闻至 {receiver}！")
        else:
            history_db.record_pushed(hits)
            print(f"[突发监控] 命中 {len(hits)} 条要闻，但邮箱未配置，仅记录历史。")
    except Exception as e:
        print(f"[突发推送] 异常: {e}")

def run_once():
    """执行一次完整的财经快讯获取、去重、AI分析与微信邮件推送任务"""
    cfg = config.load_config()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n[{now_str}] 正在抓取最新财经快讯...")

    sources = cfg.get("sources", ["sina", "wscn"])
    limit = cfg.get("news_limit", 20)
    categories = cfg.get("categories", ["宏观政策", "A股市场", "科技产业", "大宗商品", "全球要闻"])
    dedup = cfg.get("enable_dedup", True)
    watchlist = [k.strip() for k in cfg.get("watchlist", "").replace("，", ",").split(",") if k.strip()]

    raw_news = fetch_cls_news(limit=limit * 2, enabled_sources=sources)
    if not raw_news:
        print("[提示] 本次未获取到资讯，流程结束。")
        return

    # 领域过滤与去重
    cleaned_news = filter_and_clean_news(
        raw_news,
        keywords=cfg.get("filter_keywords", []),
        allowed_categories=categories,
        dedup_threshold=0.48 if dedup else 0.99,
        max_limit=limit
    )

    # 自选监控标记与置顶
    mark_watchlist(cleaned_news, watchlist)
    cleaned_news = prioritize_watchlist(cleaned_news)
    print(f"[处理] 抓取原始数据 {len(raw_news)} 条，经领域过滤与去重后保留 {len(cleaned_news)} 条。")

    # 防重复推送：过滤 24 小时内已推送的内容
    fresh_news = history_db.filter_unpushed(cleaned_news, hours=24)
    skipped = len(cleaned_news) - len(fresh_news)
    if skipped > 0:
        print(f"[防重复] 自动剔除 {skipped} 条 24 小时内已推送的内容。")
    if not fresh_news:
        print("[提示] 本轮快讯均已推送过，无需重复推送，流程结束。")
        return

    # 大模型行业分析
    final_news = fresh_news
    if cfg.get("llm_enabled") and cfg.get("llm_api_key"):
        model = cfg.get("llm_model", "deepseek-v4-flash")
        print(f"[AI 分析] 正在调用大模型 ({model}) 进行行业影响分析与情绪分级...")
        final_news = analyze_news_with_llm(
            fresh_news,
            api_key=cfg.get("llm_api_key"),
            base_url=cfg.get("llm_base_url", "https://api.deepseek.com"),
            model=model,
            system_prompt=cfg.get("custom_prompt", ""),
            reasoning_level=cfg.get("llm_reasoning_level", "balanced"),
            max_analyze=12,
            max_concurrent=int(cfg.get("llm_max_concurrent", 1))
        )
        mark_watchlist(final_news, watchlist)
        final_news = prioritize_watchlist(final_news)

    # 导出本地归档
    output_dir = os.path.dirname(__file__)
    excel_file = os.path.join(output_dir, "财经热点汇总.csv")
    try:
        export_to_excel(final_news, output_path=excel_file)
        print(f"[导出] 表格已同步导出至本地备份: {excel_file}")
    except Exception as e:
        print(f"[导出提示] 写入本地表格异常: {e}")

    # 控制台摘要预览
    print("\n--- [资讯研报表格预览] ---")
    print(build_markdown_table(final_news))
    print("---------------------------\n")

    # 邮件与微信推送
    sender = cfg.get("sender_email")
    auth = cfg.get("sender_auth_code")
    receiver = cfg.get("receiver_email") or sender

    if sender and auth:
        print(f"[邮件推送] 正在推送到邮箱: {receiver} ...")
        html_card = build_html_card(final_news)
        subject_str = f"财经早报与智能热点精选 ({datetime.now().strftime('%m月%d日 %H:%M')})"
        ok = send_email_digest(
            smtp_server=cfg.get("smtp_server", "smtp.qq.com"),
            smtp_port=int(cfg.get("smtp_port", 465)),
            sender_email=sender,
            sender_auth_code=auth,
            receiver_email=receiver,
            subject=subject_str,
            html_content=html_card,
            attachment_path=excel_file
        )
        if ok:
            history_db.record_pushed(final_news)
    else:
        print("[提示] 未配置发件邮箱或授权码，跳过邮件发送。")

def main():
    parser = argparse.ArgumentParser(description="FinancePulse - 财经早报与微信提醒调度引擎")
    parser.add_argument("--once", action="store_true", help="单次执行抓取与推送后退出")
    parser.add_argument("--cron", action="store_true", help="开启定时运行模式 (每天固定时点全自动轮询)")
    args = parser.parse_args()

    cfg = config.load_config()

    # 默认模式判断：如果是 Docker 环境且没有指定 --once，自动开启 cron 常驻
    is_docker = os.path.exists("/.dockerenv") or os.getenv("DOCKER_MODE") == "1"
    run_cron = args.cron or (is_docker and not args.once)

    if run_cron:
        try:
            import schedule
            times = cfg.get("schedule_times", ["08:30", "12:00", "16:00"])
            print("======================================================")
            print(" FinancePulse 后台定时服务已启动")
            print(f" 当前系统时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f" 定时推送时段: {', '.join(times)}")
            print(f" 目标接收邮箱: {cfg.get('receiver_email') or cfg.get('sender_email')}")
            print("======================================================")

            # 突发要闻实时监控 (默认在常驻模式下自动开启)
            if cfg.get("flash_enabled", False):
                flash_monitor.FlashMonitor(_flash_push, threading.Event()).start()
                print("[突发监控] 已开启实时监控，命中关键词将秒级推送！")

            for t in times:
                schedule.every().day.at(t).do(run_once)

            # 服务启动时先立即执行一次首发推送
            print("[服务启动] 执行首次开机巡检与推送测试...")
            run_once()

            while True:
                schedule.run_pending()
                time.sleep(15)
        except ImportError:
            print("[错误] 未安装 schedule 依赖，请运行: pip install schedule")
        except KeyboardInterrupt:
            print("\n[退出] 收到退出信号，服务安全关闭。")
    else:
        run_once()

if __name__ == "__main__":
    main()

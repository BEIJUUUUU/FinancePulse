"""
FinancePulse - 现代化桌面智能研报与微信推送助手 (Apple 极简风格版)
遵循 Apple HIG 现代设计规范：大圆角、纯净层级底色、单层原生导航与多信源智能去重
"""
import os
import sys
import threading
import time
from datetime import datetime
import customtkinter as ctk
from tkinter import messagebox

import config
from fetcher import fetch_cls_news
from processor import filter_and_clean_news, build_html_card, export_to_excel
from email_sender import send_email_digest
from llm_analyzer import analyze_news_with_llm, LLM_PROVIDERS

# ==================== Apple 风格配色设计系统 ====================
APPLE_BLUE = "#007AFF"
APPLE_BLUE_HOVER = "#0062CC"
APPLE_GREEN = "#34C759"
APPLE_PURPLE = "#AF52DE"
APPLE_RED = "#FF3B30"

class AppleStyleFinanceApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 加载配置
        self.cfg = config.load_config()

        # 默认完全跟随操作系统深浅色
        ctk.set_appearance_mode(self.cfg.get("ui_theme", "System"))
        ctk.set_default_color_theme("blue")

        self.title("FinancePulse")
        self.geometry("1140x790")
        self.minsize(980, 680)

        # 状态变量
        self.current_page = "dash"
        self.is_scheduling = False
        self.schedule_thread = None
        self.current_news_list = []

        self._build_apple_ui()
        self._load_config_to_ui()
        self._switch_page("dash")
        self.log("✨ 欢迎使用 FinancePulse！已启用 Apple 极简现代设计系统。")

    def _build_apple_ui(self):
        # 整体网格布局：左侧栏 (col 0)，右侧主容器 (col 1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ==================== 1. macOS 风格侧边栏 (Sidebar) ====================
        self.sidebar = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color=("gray92", "#18181b"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)

        # 品牌 Header
        self.brand_title = ctk.CTkLabel(
            self.sidebar,
            text="📈 FinancePulse",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=20, weight="bold")
        )
        self.brand_title.grid(row=0, column=0, padx=22, pady=(26, 2), sticky="w")

        self.brand_sub = ctk.CTkLabel(
            self.sidebar,
            text="智能财经早报 · 微信直推",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
            text_color=("gray50", "gray50")
        )
        self.brand_sub.grid(row=1, column=0, padx=22, pady=(0, 24), sticky="w")

        # 导航按键 (使用动态高亮追踪)
        self.nav_buttons = {}
        
        self.btn_nav_dash = ctk.CTkButton(
            self.sidebar,
            text="  📰  实时快讯大厅",
            height=40,
            corner_radius=10,
            anchor="w",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold"),
            command=lambda: self._switch_page("dash")
        )
        self.btn_nav_dash.grid(row=2, column=0, padx=14, pady=5, sticky="ew")
        self.nav_buttons["dash"] = self.btn_nav_dash

        self.btn_nav_conf = ctk.CTkButton(
            self.sidebar,
            text="  ⚙️  系统与 AI 配置",
            height=40,
            corner_radius=10,
            anchor="w",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=13),
            command=lambda: self._switch_page("settings")
        )
        self.btn_nav_conf.grid(row=3, column=0, padx=14, pady=5, sticky="ew")
        self.nav_buttons["settings"] = self.btn_nav_conf

        self.btn_nav_guide = ctk.CTkButton(
            self.sidebar,
            text="  📖  新手使用指引",
            height=40,
            corner_radius=10,
            anchor="w",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=13),
            command=lambda: self._switch_page("guide")
        )
        self.btn_nav_guide.grid(row=4, column=0, padx=14, pady=5, sticky="ew")
        self.nav_buttons["guide"] = self.btn_nav_guide

        # 定时推送圆角卡片
        self.sched_card = ctk.CTkFrame(self.sidebar, corner_radius=14, fg_color=("gray85", "#27272a"))
        self.sched_card.grid(row=5, column=0, padx=14, pady=(24, 10), sticky="ew")

        self.sched_title = ctk.CTkLabel(
            self.sched_card,
            text="⏰ 后台定时推送",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold")
        )
        self.sched_title.pack(anchor="w", padx=14, pady=(12, 2))

        self.sched_status_lbl = ctk.CTkLabel(
            self.sched_card,
            text="状态: 未运行 ⚪",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
            text_color="gray"
        )
        self.sched_status_lbl.pack(anchor="w", padx=14, pady=(0, 10))

        self.btn_sched_toggle = ctk.CTkButton(
            self.sched_card,
            text="开启定时推送",
            height=32,
            corner_radius=8,
            fg_color=APPLE_GREEN,
            hover_color="#2da84a",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
            command=self._toggle_scheduler
        )
        self.btn_sched_toggle.pack(fill="x", padx=12, pady=(0, 12))

        # 主题偏好切换
        self.theme_lbl = ctk.CTkLabel(
            self.sidebar,
            text="外观模式:",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
            text_color="gray"
        )
        self.theme_lbl.grid(row=11, column=0, padx=20, pady=(0, 2), sticky="w")

        self.theme_opt = ctk.CTkOptionMenu(
            self.sidebar,
            values=["System", "Light", "Dark"],
            height=30,
            corner_radius=8,
            command=self._change_theme
        )
        self.theme_opt.grid(row=12, column=0, padx=16, pady=(0, 20), sticky="ew")
        self.theme_opt.set(self.cfg.get("ui_theme", "System"))

        # ==================== 2. 右侧单层主容器 (Page Container) ====================
        self.content_container = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content_container.grid(row=0, column=1, sticky="nsew", padx=20, pady=16)
        self.content_container.grid_rowconfigure(0, weight=1)
        self.content_container.grid_columnconfigure(0, weight=1)

        # 3 个独立无干扰视图页面
        self.pages = {}
        self.pages["dash"] = self._create_dash_page()
        self.pages["settings"] = self._create_settings_page()
        self.pages["guide"] = self._create_guide_page()

    def _switch_page(self, page_name: str):
        """单层平滑切换视图并更新侧边栏高亮选中状态"""
        self.current_page = page_name

        # 1. 隐藏所有页面，显示目标页面
        for name, page in self.pages.items():
            if name == page_name:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()

        # 2. 更新左侧导航选中样式 (选中的高亮为 Apple Blue，其他透明)
        for name, btn in self.nav_buttons.items():
            if name == page_name:
                btn.configure(
                    fg_color=APPLE_BLUE,
                    hover_color=APPLE_BLUE_HOVER,
                    text_color="#ffffff"
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    hover_color=("gray85", "gray25"),
                    text_color=("gray10", "gray90")
                )

    # -------------------------------------------------------------
    # 页面 1：实时快讯大厅 (Apple 风格卡片资讯流)
    # -------------------------------------------------------------
    def _create_dash_page(self):
        page = ctk.CTkFrame(self.content_container, corner_radius=16, fg_color="transparent")

        # 顶部工具操作条 (Apple 极简大圆角卡片)
        toolbar = ctk.CTkFrame(page, corner_radius=16, fg_color=("white", "#27272a"), border_width=1, border_color=("gray85", "gray30"))
        toolbar.pack(fill="x", pady=(0, 14))

        # 抓取条数选择
        ctk.CTkLabel(toolbar, text="抓取数量:", font=ctk.CTkFont(family="Microsoft YaHei UI", size=12)).pack(side="left", padx=(16, 4), pady=12)
        self.combo_count = ctk.CTkComboBox(
            toolbar,
            values=["10", "15", "20", "30", "50", "80"],
            width=80,
            corner_radius=8,
            command=self._on_count_changed
        )
        self.combo_count.pack(side="left", padx=(0, 10), pady=12)
        self.combo_count.set(str(self.cfg.get("news_limit", 20)))

        # 操作按钮组
        self.btn_fetch = ctk.CTkButton(
            toolbar,
            text="🔄 抓取最新快讯",
            corner_radius=10,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
            fg_color=APPLE_BLUE,
            hover_color=APPLE_BLUE_HOVER,
            width=120,
            command=self._on_fetch_news
        )
        self.btn_fetch.pack(side="left", padx=6, pady=12)

        self.btn_ai = ctk.CTkButton(
            toolbar,
            text="🤖 AI 深度研报点评",
            corner_radius=10,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
            fg_color=APPLE_PURPLE,
            hover_color="#9333ea",
            width=140,
            command=self._on_ai_analyze
        )
        self.btn_ai.pack(side="left", padx=6, pady=12)

        self.btn_export = ctk.CTkButton(
            toolbar,
            text="📁 导出表格",
            corner_radius=10,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
            fg_color=("gray85", "gray35"),
            hover_color=("gray75", "gray40"),
            text_color=("black", "white"),
            width=90,
            command=self._on_export
        )
        self.btn_export.pack(side="left", padx=6, pady=12)

        self.btn_push = ctk.CTkButton(
            toolbar,
            text="🚀 立即推送到微信/邮箱",
            corner_radius=10,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
            fg_color=APPLE_BLUE,
            hover_color=APPLE_BLUE_HOVER,
            width=175,
            command=self._on_send_now
        )
        self.btn_push.pack(side="right", padx=16, pady=12)

        # 资讯卡片流动展示容器 (带柔和边框)
        self.cards_scroll = ctk.CTkScrollableFrame(
            page,
            corner_radius=16,
            fg_color=("white", "#1c1c1e"),
            border_width=1,
            border_color=("gray85", "gray30"),
            label_text="实时财经快讯与研报列表"
        )
        self.cards_scroll.pack(fill="both", expand=True, pady=(0, 10))

        # 底部状态日志卡片
        log_card = ctk.CTkFrame(page, height=72, corner_radius=14, fg_color=("white", "#27272a"), border_width=1, border_color=("gray85", "gray30"))
        log_card.pack(fill="x")

        self.log_text = ctk.CTkTextbox(log_card, height=65, font=("Consolas", 10), wrap="word", fg_color="transparent")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=4)

        return page

    # -------------------------------------------------------------
    # 页面 2：系统与 AI 配置 (Apple 设置项分组卡片风格)
    # -------------------------------------------------------------
    def _create_settings_page(self):
        page = ctk.CTkScrollableFrame(self.content_container, corner_radius=16, fg_color="transparent")

        # 1. 邮箱与微信提醒卡片 (Grouped Section)
        c1 = ctk.CTkFrame(page, corner_radius=16, fg_color=("white", "#1c1c1e"), border_width=1, border_color=("gray85", "gray30"))
        c1.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            c1,
            text="📧 邮箱推送与微信秒级弹窗",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold")
        ).pack(anchor="w", padx=20, pady=(16, 4))

        # 贴心高亮提示条
        tip_box = ctk.CTkFrame(c1, corner_radius=10, fg_color=("#e0f2fe", "#082f49"))
        tip_box.pack(fill="x", padx=20, pady=(4, 12))
        ctk.CTkLabel(
            tip_box,
            text="💡 贴士：接收邮箱直接填回发件人（或留空）！自己发给自己绝对不进垃圾箱，微信开启「QQ邮箱提醒」后可直接秒弹窗！",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
            text_color=("#0369a1", "#38bdf8"),
            wraplength=760,
            justify="left"
        ).pack(anchor="w", padx=12, pady=8)

        # 发件邮箱
        r1 = ctk.CTkFrame(c1, fg_color="transparent")
        r1.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(r1, text="发件人 QQ 邮箱:", width=140, anchor="w", font=ctk.CTkFont(family="Microsoft YaHei UI", size=12)).pack(side="left")
        self.ent_sender = ctk.CTkEntry(r1, width=320, corner_radius=8, placeholder_text="例如: your_qq@qq.com")
        self.ent_sender.pack(side="left", padx=10)

        # 授权码
        r2 = ctk.CTkFrame(c1, fg_color="transparent")
        r2.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(r2, text="16位 SMTP 授权码:", width=140, anchor="w", font=ctk.CTkFont(family="Microsoft YaHei UI", size=12)).pack(side="left")
        self.ent_auth = ctk.CTkEntry(r2, width=320, corner_radius=8, show="*", placeholder_text="QQ邮箱设置页面生成的16位字母")
        self.ent_auth.pack(side="left", padx=10)
        self.btn_pwd_eye = ctk.CTkButton(r2, text="显示", width=55, corner_radius=6, fg_color=("gray80", "gray35"), text_color=("black", "white"), command=self._toggle_pwd)
        self.btn_pwd_eye.pack(side="left")

        # 接收邮箱
        r3 = ctk.CTkFrame(c1, fg_color="transparent")
        r3.pack(fill="x", padx=20, pady=(6, 18))
        ctk.CTkLabel(r3, text="接收人邮箱 (微信接收):", width=140, anchor="w", font=ctk.CTkFont(family="Microsoft YaHei UI", size=12)).pack(side="left")
        self.ent_receiver = ctk.CTkEntry(r3, width=320, corner_radius=8, placeholder_text="填入发件人或留空即默认发给自己")
        self.ent_receiver.pack(side="left", padx=10)

        # 2. 信息源选择与去重策略 (Grouped Section)
        c_src = ctk.CTkFrame(page, corner_radius=16, fg_color=("white", "#1c1c1e"), border_width=1, border_color=("gray85", "gray30"))
        c_src.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            c_src,
            text="🌐 资讯信源抓取与高精度智能去重",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold")
        ).pack(anchor="w", padx=20, pady=(16, 8))

        r_src = ctk.CTkFrame(c_src, fg_color="transparent")
        r_src.pack(fill="x", padx=20, pady=4)
        
        self.chk_sina = ctk.CTkCheckBox(r_src, text="新浪财经 7x24", font=ctk.CTkFont(family="Microsoft YaHei UI", size=12))
        self.chk_sina.pack(side="left", padx=(0, 20))
        self.chk_sina.select()

        self.chk_wscn = ctk.CTkCheckBox(r_src, text="华尔街见闻", font=ctk.CTkFont(family="Microsoft YaHei UI", size=12))
        self.chk_wscn.pack(side="left", padx=(0, 20))
        self.chk_wscn.select()

        self.chk_cls = ctk.CTkCheckBox(r_src, text="财联社 (AKShare)", font=ctk.CTkFont(family="Microsoft YaHei UI", size=12))
        self.chk_cls.pack(side="left", padx=(0, 20))

        # 去重开关与说明
        r_dedup = ctk.CTkFrame(c_src, fg_color="transparent")
        r_dedup.pack(fill="x", padx=20, pady=(10, 16))

        self.chk_dedup = ctk.CTkCheckBox(
            r_dedup,
            text="开启高精度相似度跨源去重 (基于序列算法自动识别多源重复事件，自动归并并保留最丰富报道)",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12)
        )
        self.chk_dedup.pack(side="left")
        self.chk_dedup.select()

        # 3. 大模型 AI 分析设置 (Grouped Section)
        c2 = ctk.CTkFrame(page, corner_radius=16, fg_color=("white", "#1c1c1e"), border_width=1, border_color=("gray85", "gray30"))
        c2.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            c2,
            text="🤖 大模型 AI 智能分析 (全兼容主流厂商)",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold")
        ).pack(anchor="w", padx=20, pady=(16, 6))

        r4 = ctk.CTkFrame(c2, fg_color="transparent")
        r4.pack(fill="x", padx=20, pady=4)
        self.switch_llm = ctk.CTkSwitch(
            r4,
            text="启用 AI 智能分析 (自动提炼精选核心事实，并生成利好/利空投研视点)",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12)
        )
        self.switch_llm.pack(side="left")

        r5 = ctk.CTkFrame(c2, fg_color="transparent")
        r5.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(r5, text="服务商预设 (Provider):", width=140, anchor="w", font=ctk.CTkFont(family="Microsoft YaHei UI", size=12)).pack(side="left")
        self.combo_provider = ctk.CTkComboBox(
            r5,
            values=list(LLM_PROVIDERS.keys()),
            width=260,
            corner_radius=8,
            command=self._on_provider_changed
        )
        self.combo_provider.pack(side="left", padx=10)

        self.lbl_provider_note = ctk.CTkLabel(
            r5,
            text="",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
            text_color=APPLE_PURPLE
        )
        self.lbl_provider_note.pack(side="left", padx=6)

        r6 = ctk.CTkFrame(c2, fg_color="transparent")
        r6.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(r6, text="API Key 秘钥:", width=140, anchor="w", font=ctk.CTkFont(family="Microsoft YaHei UI", size=12)).pack(side="left")
        self.ent_ai_key = ctk.CTkEntry(r6, width=400, corner_radius=8, show="*", placeholder_text="sk-xxxxxxxxxxxxxxxx (若用本地 Ollama 可不填)")
        self.ent_ai_key.pack(side="left", padx=10)

        r7 = ctk.CTkFrame(c2, fg_color="transparent")
        r7.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(r7, text="Base URL 接口地址:", width=140, anchor="w", font=ctk.CTkFont(family="Microsoft YaHei UI", size=12)).pack(side="left")
        self.ent_ai_url = ctk.CTkEntry(r7, width=400, corner_radius=8, placeholder_text="https://api.deepseek.com")
        self.ent_ai_url.pack(side="left", padx=10)

        r8 = ctk.CTkFrame(c2, fg_color="transparent")
        r8.pack(fill="x", padx=20, pady=(4, 18))
        ctk.CTkLabel(r8, text="模型名称 (Model):", width=140, anchor="w", font=ctk.CTkFont(family="Microsoft YaHei UI", size=12)).pack(side="left")
        self.ent_ai_model = ctk.CTkEntry(r8, width=220, corner_radius=8, placeholder_text="deepseek-chat")
        self.ent_ai_model.pack(side="left", padx=10)

        # 4. 定时轮询卡片 (Grouped Section)
        c3 = ctk.CTkFrame(page, corner_radius=16, fg_color=("white", "#1c1c1e"), border_width=1, border_color=("gray85", "gray30"))
        c3.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            c3,
            text="⏰ 定时推送计划时段",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold")
        ).pack(anchor="w", padx=20, pady=(16, 6))

        r9 = ctk.CTkFrame(c3, fg_color="transparent")
        r9.pack(fill="x", padx=20, pady=4)
        self.sched_mode_var = ctk.StringVar(value="classic")
        self.radio_classic = ctk.CTkRadioButton(
            r9,
            text="经典三时段 (早盘 08:30 / 午间 12:00 / 收盘 16:00)",
            variable=self.sched_mode_var,
            value="classic",
            command=self._on_sched_mode_changed
        )
        self.radio_classic.pack(side="left", padx=(0, 20))

        self.radio_custom = ctk.CTkRadioButton(
            r9,
            text="自定义指定时点",
            variable=self.sched_mode_var,
            value="custom",
            command=self._on_sched_mode_changed
        )
        self.radio_custom.pack(side="left")

        r10 = ctk.CTkFrame(c3, fg_color="transparent")
        r10.pack(fill="x", padx=20, pady=(6, 18))
        ctk.CTkLabel(r10, text="自定义时点 (逗号分隔):", width=140, anchor="w", font=ctk.CTkFont(family="Microsoft YaHei UI", size=12)).pack(side="left")
        self.ent_custom_times = ctk.CTkEntry(r10, width=320, corner_radius=8, placeholder_text="例如: 09:15, 14:30, 21:00")
        self.ent_custom_times.pack(side="left", padx=10)

        # 保存所有设置的大胶囊按钮
        self.btn_save_all = ctk.CTkButton(
            page,
            text="💾 保存并应用所有配置",
            height=44,
            corner_radius=12,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=14, weight="bold"),
            fg_color=APPLE_BLUE,
            hover_color=APPLE_BLUE_HOVER,
            command=self._save_all_settings
        )
        self.btn_save_all.pack(fill="x", pady=(6, 24))

        return page

    # -------------------------------------------------------------
    # 页面 3：原生卡片式高颜值新手指南 (告别难看的纯文本框)
    # -------------------------------------------------------------
    def _create_guide_page(self):
        page = ctk.CTkScrollableFrame(self.content_container, corner_radius=16, fg_color="transparent")

        # 页面标题
        header = ctk.CTkFrame(page, fg_color="transparent")
        header.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(
            header,
            text="📖 快速上手与使用指引",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=18, weight="bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="只需 3 步，即可实现电脑自动化抓取财经要闻并推送到你的手机微信。",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
            text_color="gray"
        ).pack(anchor="w", pady=(2, 0))

        # 步骤 1 卡片
        g1 = ctk.CTkFrame(page, corner_radius=16, fg_color=("white", "#1c1c1e"), border_width=1, border_color=("gray85", "gray30"))
        g1.pack(fill="x", pady=(0, 14))

        h1 = ctk.CTkFrame(g1, fg_color="transparent")
        h1.pack(fill="x", padx=18, pady=(16, 6))
        ctk.CTkLabel(
            h1,
            text=" 1 ",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=APPLE_BLUE,
            text_color="white",
            corner_radius=6,
            width=26,
            height=26
        ).pack(side="left")
        ctk.CTkLabel(
            h1,
            text=" 获取 QQ 邮箱「16 位 SMTP 授权码」",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold")
        ).pack(side="left", padx=8)

        steps_text1 = (
            "1. 电脑浏览器打开 QQ 邮箱官网：mail.qq.com 并扫码登录；\n"
            "2. 点击顶部「设置」➔ 切换到「账户」选项卡；\n"
            "3. 向下滚动找到「POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务」；\n"
            "4. 开启「POP3/SMTP服务」，按提示手机发短信验证；\n"
            "5. 验证通过后会生成一串 16 位的英文授权码，复制它！"
        )
        ctk.CTkLabel(
            g1,
            text=steps_text1,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
            text_color=("gray20", "gray80"),
            justify="left"
        ).pack(anchor="w", padx=22, pady=(0, 16))

        # 步骤 2 卡片
        g2 = ctk.CTkFrame(page, corner_radius=16, fg_color=("white", "#1c1c1e"), border_width=1, border_color=("gray85", "gray30"))
        g2.pack(fill="x", pady=(0, 14))

        h2 = ctk.CTkFrame(g2, fg_color="transparent")
        h2.pack(fill="x", padx=18, pady=(16, 6))
        ctk.CTkLabel(
            h2,
            text=" 2 ",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=APPLE_GREEN,
            text_color="white",
            corner_radius=6,
            width=26,
            height=26
        ).pack(side="left")
        ctk.CTkLabel(
            h2,
            text=" 手机微信开启「QQ 邮箱提醒」",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold")
        ).pack(side="left", padx=8)

        steps_text2 = (
            "1. 打开手机微信，在顶部搜索框输入「QQ邮箱提醒」并进入该服务插件；\n"
            "2. 确保开启提醒并绑定你的 QQ 邮箱；\n"
            "3. 搞定！只要程序发出早报邮件，微信就会“叮”的一声弹出推送卡片！"
        )
        ctk.CTkLabel(
            g2,
            text=steps_text2,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
            text_color=("gray20", "gray80"),
            justify="left"
        ).pack(anchor="w", padx=22, pady=(0, 16))

        # 步骤 3 卡片
        g3 = ctk.CTkFrame(page, corner_radius=16, fg_color=("white", "#1c1c1e"), border_width=1, border_color=("gray85", "gray30"))
        g3.pack(fill="x", pady=(0, 14))

        h3 = ctk.CTkFrame(g3, fg_color="transparent")
        h3.pack(fill="x", padx=18, pady=(16, 6))
        ctk.CTkLabel(
            h3,
            text=" 3 ",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=APPLE_PURPLE,
            text_color="white",
            corner_radius=6,
            width=26,
            height=26
        ).pack(side="left")
        ctk.CTkLabel(
            h3,
            text=" 接入 AI 智能研报分析 (可选，逼格极高)",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold")
        ).pack(side="left", padx=8)

        steps_text3 = (
            "• 支持主流模型：DeepSeek、Kimi、智谱 GLM、阿里通义千问、OpenAI 或本地离线 Ollama；\n"
            "• 在【系统与 AI 配置】中选择你的服务商，填入 API Key 即可；\n"
            "• 每次抓取后，AI 会自动归并同类事件，并生成【🤖 AI 投研视点】与利好/利空情绪！"
        )
        ctk.CTkLabel(
            g3,
            text=steps_text3,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
            text_color=("gray20", "gray80"),
            justify="left"
        ).pack(anchor="w", padx=22, pady=(0, 16))

        # 跳转按钮
        ctk.CTkButton(
            page,
            text="👉 前往【系统与 AI 配置】进行配置",
            height=38,
            corner_radius=10,
            fg_color=("gray85", "gray30"),
            hover_color=("gray75", "gray40"),
            text_color=("black", "white"),
            command=lambda: self._switch_page("settings")
        ).pack(fill="x", pady=6)

        return page

    # ==================== 业务逻辑与事件交互 ====================
    def log(self, text: str):
        now_str = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{now_str}] {text}\n")
        self.log_text.see("end")

    def _toggle_pwd(self):
        if self.ent_auth.cget("show") == "*":
            self.ent_auth.configure(show="")
            self.btn_pwd_eye.configure(text="隐藏")
        else:
            self.ent_auth.configure(show="*")
            self.btn_pwd_eye.configure(text="显示")

    def _change_theme(self, mode: str):
        ctk.set_appearance_mode(mode)
        self.cfg["ui_theme"] = mode
        config.save_config(self.cfg)

    def _on_provider_changed(self, choice: str):
        if choice in LLM_PROVIDERS:
            info = LLM_PROVIDERS[choice]
            self.ent_ai_url.delete(0, "end")
            self.ent_ai_url.insert(0, info["base_url"])

            self.ent_ai_model.delete(0, "end")
            self.ent_ai_model.insert(0, info["model"])

            self.lbl_provider_note.configure(text=f"📌 {info['note']}")

    def _on_sched_mode_changed(self):
        mode = self.sched_mode_var.get()
        if mode == "classic":
            self.ent_custom_times.configure(state="disabled")
        else:
            self.ent_custom_times.configure(state="normal")

    def _on_count_changed(self, choice: str):
        try:
            self.cfg["news_limit"] = int(choice)
            config.save_config(self.cfg)
            self.log(f"⚡ 已将抓取条数调整为 {choice} 条！")
        except Exception:
            pass

    def _load_config_to_ui(self):
        self.ent_sender.insert(0, self.cfg.get("sender_email", ""))
        self.ent_auth.insert(0, self.cfg.get("sender_auth_code", ""))
        self.ent_receiver.insert(0, self.cfg.get("receiver_email", ""))

        # 信源勾选
        sources = self.cfg.get("sources", ["sina", "wscn"])
        if "sina" in sources:
            self.chk_sina.select()
        else:
            self.chk_sina.deselect()

        if "wscn" in sources:
            self.chk_wscn.select()
        else:
            self.chk_wscn.deselect()

        if "cls" in sources:
            self.chk_cls.select()
        else:
            self.chk_cls.deselect()

        if self.cfg.get("enable_dedup", True):
            self.chk_dedup.select()
        else:
            self.chk_dedup.deselect()

        if self.cfg.get("llm_enabled", False):
            self.switch_llm.select()
        else:
            self.switch_llm.deselect()

        provider = self.cfg.get("llm_provider", "DeepSeek (深度求索)")
        if provider in LLM_PROVIDERS:
            self.combo_provider.set(provider)
            self.lbl_provider_note.configure(text=f"📌 {LLM_PROVIDERS[provider]['note']}")

        self.ent_ai_key.insert(0, self.cfg.get("llm_api_key", ""))
        self.ent_ai_url.insert(0, self.cfg.get("llm_base_url", "https://api.deepseek.com"))
        self.ent_ai_model.insert(0, self.cfg.get("llm_model", "deepseek-chat"))

        mode = self.cfg.get("schedule_mode", "classic")
        self.sched_mode_var.set(mode)
        self.ent_custom_times.insert(0, self.cfg.get("custom_times", "09:15, 14:30, 21:00"))
        self._on_sched_mode_changed()

    def _get_enabled_sources(self):
        sources = []
        if self.chk_sina.get():
            sources.append("sina")
        if self.chk_wscn.get():
            sources.append("wscn")
        if self.chk_cls.get():
            sources.append("cls")
        return sources or ["sina", "wscn"]

    def _save_all_settings(self):
        self.cfg["sender_email"] = self.ent_sender.get().strip()
        self.cfg["sender_auth_code"] = self.ent_auth.get().strip()
        self.cfg["receiver_email"] = self.ent_receiver.get().strip() or self.cfg["sender_email"]
        self.cfg["sources"] = self._get_enabled_sources()
        self.cfg["enable_dedup"] = bool(self.chk_dedup.get())
        self.cfg["llm_enabled"] = bool(self.switch_llm.get())
        self.cfg["llm_provider"] = self.combo_provider.get()
        self.cfg["llm_api_key"] = self.ent_ai_key.get().strip()
        self.cfg["llm_base_url"] = self.ent_ai_url.get().strip()
        self.cfg["llm_model"] = self.ent_ai_model.get().strip()
        self.cfg["schedule_mode"] = self.sched_mode_var.get()
        self.cfg["custom_times"] = self.ent_custom_times.get().strip()

        if config.save_config(self.cfg):
            self.log("✅ 所有配置已持久化保存！")
            messagebox.showinfo("成功", "所有系统与 AI 配置已保存生效！")
        else:
            messagebox.showerror("错误", "保存失败，请检查读写权限。")

    def _on_fetch_news(self):
        limit = int(self.combo_count.get() or 20)
        sources = self._get_enabled_sources()
        dedup = bool(self.chk_dedup.get())

        self.btn_fetch.configure(state="disabled")
        self.log(f"🔄 正在从已选信源 ({', '.join(sources)}) 抓取前 {limit} 条快讯...")

        def worker():
            try:
                raw = fetch_cls_news(limit=limit, enabled_sources=sources)
                threshold = 0.48 if dedup else 0.99
                cleaned = filter_and_clean_news(raw, dedup_threshold=threshold, max_limit=limit)

                # 若开启 AI 且配了 Key，自动进行提炼
                if self.switch_llm.get() and self.ent_ai_key.get().strip():
                    self.after(0, lambda: self.log("🤖 正在调用大模型进行跨源去重与投研点评..."))
                    analyzed = analyze_news_with_llm(
                        cleaned,
                        api_key=self.ent_ai_key.get().strip(),
                        base_url=self.ent_ai_url.get().strip(),
                        model=self.ent_ai_model.get().strip()
                    )
                    self.current_news_list = analyzed
                else:
                    self.current_news_list = cleaned

                self.after(0, self._render_cards, self.current_news_list)
            except Exception as e:
                self.after(0, lambda: self.log(f"❌ 抓取异常: {e}"))
            finally:
                self.after(0, lambda: self.btn_fetch.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_ai_analyze(self):
        if not self.current_news_list:
            messagebox.showwarning("提示", "请先抓取快讯再进行 AI 分析！")
            return

        api_key = self.ent_ai_key.get().strip()
        base_url = self.ent_ai_url.get().strip()
        if not api_key and "localhost" not in base_url:
            messagebox.showwarning("提示", "请先在【系统与 AI 配置】中填写 API Key！")
            self._switch_page("settings")
            return

        self.btn_ai.configure(state="disabled")
        self.log(f"🤖 正在调用 {self.ent_ai_model.get().strip()} 模型深入研判...")

        def worker():
            try:
                analyzed = analyze_news_with_llm(
                    self.current_news_list,
                    api_key=api_key,
                    base_url=base_url,
                    model=self.ent_ai_model.get().strip()
                )
                self.current_news_list = analyzed
                self.after(0, self._render_cards, self.current_news_list)
                self.after(0, lambda: self.log(f"🎉 AI 分析完成！提炼出 {len(analyzed)} 条高价值要闻。"))
            except Exception as e:
                self.after(0, lambda: self.log(f"❌ AI 分析异常: {e}"))
            finally:
                self.after(0, lambda: self.btn_ai.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _render_cards(self, news_list):
        for widget in self.cards_scroll.winfo_children():
            widget.destroy()

        if not news_list:
            lbl = ctk.CTkLabel(self.cards_scroll, text="暂无快讯数据，请点击上方【抓取最新快讯】。", text_color="gray")
            lbl.pack(pady=40)
            return

        for idx, item in enumerate(news_list, 1):
            t = item.get("time", "")
            title = item.get("title", "")
            content = item.get("content", "")
            ai_comment = item.get("ai_comment", "")
            sentiment = item.get("sentiment", "")
            tag = item.get("tag", "")
            src = item.get("source", "快讯")

            # Apple 现代圆角微阴影卡片
            card = ctk.CTkFrame(
                self.cards_scroll,
                corner_radius=14,
                fg_color=("white", "#27272a"),
                border_width=1,
                border_color=("gray85", "gray30")
            )
            card.pack(fill="x", padx=4, pady=6)

            # 卡片 Header
            head_row = ctk.CTkFrame(card, fg_color="transparent")
            head_row.pack(fill="x", padx=14, pady=(12, 4))

            idx_badge = ctk.CTkLabel(
                head_row,
                text=f"#{idx}",
                font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
                text_color=APPLE_BLUE
            )
            idx_badge.pack(side="left")

            time_badge = ctk.CTkLabel(
                head_row,
                text=f"🕒 {t} · {src}",
                font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
                text_color="gray"
            )
            time_badge.pack(side="left", padx=8)

            title_lbl = ctk.CTkLabel(
                head_row,
                text=title,
                font=ctk.CTkFont(family="Microsoft YaHei UI", size=14, weight="bold"),
                anchor="w"
            )
            title_lbl.pack(side="left", padx=4, fill="x", expand=True)

            if tag:
                ctk.CTkLabel(
                    head_row,
                    text=tag,
                    font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
                    text_color=APPLE_PURPLE
                ).pack(side="right", padx=6)

            if sentiment:
                sent_color = APPLE_RED if "利好" in sentiment else (APPLE_GREEN if "利空" in sentiment else "gray")
                ctk.CTkLabel(
                    head_row,
                    text=f"● {sentiment}",
                    font=ctk.CTkFont(family="Microsoft YaHei UI", size=11, weight="bold"),
                    text_color=sent_color
                ).pack(side="right", padx=6)

            # 正文内容
            ctk.CTkLabel(
                card,
                text=content,
                font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
                text_color=("gray20", "gray80"),
                wraplength=760,
                justify="left"
            ).pack(anchor="w", padx=14, pady=(2, 8))

            # AI 投研视点专属高亮底框
            if ai_comment:
                ai_box = ctk.CTkFrame(card, fg_color=("#f5f3ff", "#1e1b4b"), corner_radius=10)
                ai_box.pack(fill="x", padx=14, pady=(0, 12))
                ctk.CTkLabel(
                    ai_box,
                    text=f"🤖 AI 投研视点：{ai_comment}",
                    font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
                    text_color=("#6d28d9", "#c084fc"),
                    wraplength=730,
                    justify="left"
                ).pack(anchor="w", padx=12, pady=8)

        self.log(f"✅ 成功渲染 {len(news_list)} 条精选快讯卡片！")

    def _on_export(self):
        if not self.current_news_list:
            messagebox.showwarning("提示", "请先抓取快讯再导出！")
            return
        out_path = os.path.join(os.path.dirname(__file__), "财经热点汇总.csv")
        try:
            f = export_to_excel(self.current_news_list, output_path=out_path)
            self.log(f"📁 表格已导出至: {f}")
            messagebox.showinfo("导出成功", f"表格文件已保存至:\n{f}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def _on_send_now(self):
        sender = self.ent_sender.get().strip()
        auth = self.ent_auth.get().strip()
        receiver = self.ent_receiver.get().strip() or sender

        if not sender or not auth:
            messagebox.showwarning("提示", "发件邮箱或授权码为空，请先在【系统与 AI 配置】填写并保存！")
            self._switch_page("settings")
            return

        self.btn_push.configure(state="disabled")
        self.log(f"🚀 正在发送研报邮件至 {receiver} ...")

        def worker():
            try:
                data = self.current_news_list
                if not data:
                    raw = fetch_cls_news(limit=int(self.combo_count.get() or 20), enabled_sources=self._get_enabled_sources())
                    data = filter_and_clean_news(raw, dedup_threshold=0.48 if self.chk_dedup.get() else 0.99)
                    self.current_news_list = data
                    self.after(0, self._render_cards, data)

                # 导出备份表格
                csv_file = os.path.join(os.path.dirname(__file__), "财经热点汇总.csv")
                export_to_excel(data, output_path=csv_file)

                # 渲染 HTML 并发送
                html_card = build_html_card(data)
                subject = f"📈 财经早报与智能热点精选 ({datetime.now().strftime('%m月%d日 %H:%M')})"

                ok = send_email_digest(
                    smtp_server=self.cfg.get("smtp_server", "smtp.qq.com"),
                    smtp_port=int(self.cfg.get("smtp_port", 465)),
                    sender_email=sender,
                    sender_auth_code=auth,
                    receiver_email=receiver,
                    subject=subject,
                    html_content=html_card,
                    attachment_path=csv_file
                )
                if ok:
                    self.after(0, lambda: self.log(f"🎉 推送成功！已送达 {receiver}。微信开启QQ邮箱提醒的会立即收到弹窗！"))
                    self.after(0, lambda: messagebox.showinfo("发送成功", "邮件已成功送达！若微信绑定了 QQ 邮箱提醒将立即收到微信卡片提醒。"))
                else:
                    self.after(0, lambda: self.log("❌ 发送失败，请检查授权码或网络。"))
            except Exception as e:
                self.after(0, lambda: self.log(f"❌ 发送异常: {e}"))
            finally:
                self.after(0, lambda: self.btn_push.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _toggle_scheduler(self):
        if not self.is_scheduling:
            sender = self.ent_sender.get().strip()
            auth = self.ent_auth.get().strip()
            if not sender or not auth:
                messagebox.showwarning("提示", "开启定时前请先在【系统与 AI 配置】中保存好邮箱和授权码！")
                self._switch_page("settings")
                return

            self.is_scheduling = True
            self.btn_sched_toggle.configure(text="停止定时推送", fg_color=APPLE_RED, hover_color="#cc2f26")
            self.sched_status_lbl.configure(text="状态: 运行中 🟢", text_color=APPLE_GREEN)

            times_to_run = ["08:30", "12:00", "16:00"]
            if self.sched_mode_var.get() == "custom":
                raw_times = self.ent_custom_times.get().strip()
                if raw_times:
                    times_to_run = [t.strip() for t in raw_times.replace("，", ",").split(",") if t.strip()]

            self.log(f"⏰ 定时轮询已启动！推送时点: {', '.join(times_to_run)}")

            def run_loop():
                import schedule
                schedule.clear()
                for t in times_to_run:
                    try:
                        schedule.every().day.at(t).do(self._on_send_now)
                    except Exception as err:
                        print(f"设定定时 {t} 异常: {err}")

                while self.is_scheduling:
                    schedule.run_pending()
                    time.sleep(10)

            self.schedule_thread = threading.Thread(target=run_loop, daemon=True)
            self.schedule_thread.start()
        else:
            self.is_scheduling = False
            self.btn_sched_toggle.configure(text="开启定时推送", fg_color=APPLE_GREEN, hover_color="#2da84a")
            self.sched_status_lbl.configure(text="状态: 未运行 ⚪", text_color="gray")
            self.log("⏹ 定时推送服务已停止。")

def main():
    app = AppleStyleFinanceApp()
    app.mainloop()

if __name__ == "__main__":
    main()

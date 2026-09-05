"""
FinancePulse - 现代化桌面智能研报与微信推送助手 (Apple 极简高性能版)
具备底层 Canvas 树极致扁平化、Resize 防抖无感缩放、一键自动拉取模型列表与行业研判分级
"""
import os
import sys
import ctypes
import threading
import time
from datetime import datetime
import customtkinter as ctk
from tkinter import messagebox

# 1. 声明 Windows 进程 AppUserModelID，替换任务栏图标
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("beiju.financepulse.desktop.v2")
except Exception:
    pass

# 2. 启用 Windows 原生 Per-Monitor DPI 感知，根除高分屏字体模糊
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import config
from fetcher import fetch_cls_news
from processor import filter_and_clean_news, build_html_card, export_to_excel
from email_sender import send_email_digest
from llm_analyzer import analyze_news_with_llm, fetch_available_models, LLM_PROVIDERS, DEFAULT_SYSTEM_PROMPT

# Apple 设计规范调色板
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
        self.geometry("1160x820")
        self.minsize(980, 680)

        # 绑定应用专属极简金融图标
        icon_path = os.path.join(os.path.dirname(__file__), "app_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # 全局预定义轻量字体对象，彻底避免循环创建造成的 GDI 泄漏与卡顿
        self.f_brand = ctk.CTkFont(family="Microsoft YaHei UI", size=20, weight="bold")
        self.f_sub = ctk.CTkFont(family="Microsoft YaHei UI", size=11)
        self.f_nav = ctk.CTkFont(family="Microsoft YaHei UI", size=13)
        self.f_nav_bold = ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold")
        self.f_title = ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold")
        self.f_body = ctk.CTkFont(family="Microsoft YaHei UI", size=12)
        self.f_small = ctk.CTkFont(family="Microsoft YaHei UI", size=11)
        self.f_small_bold = ctk.CTkFont(family="Microsoft YaHei UI", size=11, weight="bold")
        self.f_ai_text = ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold")

        # 状态变量
        self.current_page = "dash"
        self.is_scheduling = False
        self.schedule_thread = None
        self.current_news_list = []
        self._resize_timer = None

        self._build_apple_ui()
        self._load_config_to_ui()
        self._switch_page("dash")

        # 窗口缩放防抖机制：拖动窗口大小时暂停重排，松开鼠标后一次性平滑更新
        self.bind("<Configure>", self._on_window_configure)

        self.log("系统已就绪。已启用高分屏 DPI 渲染与高性能抗抖动引擎。")

    def _on_window_configure(self, event):
        # 仅响应主窗口 resize，忽略子组件事件
        if event.widget == self:
            if self._resize_timer:
                self.after_cancel(self._resize_timer)
            self._resize_timer = self.after(150, self._do_smooth_layout_sync)

    def _do_smooth_layout_sync(self):
        """窗口缩放防抖完成后的平滑对齐"""
        pass

    def _build_apple_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. 侧边栏
        self.sidebar = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color=("gray92", "#18181b"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)

        self.brand_title = ctk.CTkLabel(self.sidebar, text="FinancePulse", font=self.f_brand)
        self.brand_title.grid(row=0, column=0, padx=22, pady=(26, 2), sticky="w")

        self.brand_sub = ctk.CTkLabel(self.sidebar, text="智能财经早报 · 微信直推", font=self.f_sub, text_color=("gray50", "gray50"))
        self.brand_sub.grid(row=1, column=0, padx=22, pady=(0, 24), sticky="w")

        self.nav_buttons = {}

        self.btn_nav_dash = ctk.CTkButton(
            self.sidebar,
            text="  实时快讯大厅",
            height=40,
            corner_radius=10,
            anchor="w",
            font=self.f_nav_bold,
            command=lambda: self._switch_page("dash")
        )
        self.btn_nav_dash.grid(row=2, column=0, padx=14, pady=5, sticky="ew")
        self.nav_buttons["dash"] = self.btn_nav_dash

        self.btn_nav_conf = ctk.CTkButton(
            self.sidebar,
            text="  系统与 AI 配置",
            height=40,
            corner_radius=10,
            anchor="w",
            font=self.f_nav,
            command=lambda: self._switch_page("settings")
        )
        self.btn_nav_conf.grid(row=3, column=0, padx=14, pady=5, sticky="ew")
        self.nav_buttons["settings"] = self.btn_nav_conf

        self.btn_nav_guide = ctk.CTkButton(
            self.sidebar,
            text="  新手使用指引",
            height=40,
            corner_radius=10,
            anchor="w",
            font=self.f_nav,
            command=lambda: self._switch_page("guide")
        )
        self.btn_nav_guide.grid(row=4, column=0, padx=14, pady=5, sticky="ew")
        self.nav_buttons["guide"] = self.btn_nav_guide

        # 定时卡片
        self.sched_card = ctk.CTkFrame(self.sidebar, corner_radius=14, fg_color=("gray85", "#27272a"))
        self.sched_card.grid(row=5, column=0, padx=14, pady=(24, 10), sticky="ew")

        ctk.CTkLabel(self.sched_card, text="后台定时推送", font=self.f_nav_bold).pack(anchor="w", padx=14, pady=(12, 2))
        self.sched_status_lbl = ctk.CTkLabel(self.sched_card, text="状态: 未运行", font=self.f_small, text_color="gray")
        self.sched_status_lbl.pack(anchor="w", padx=14, pady=(0, 10))

        self.btn_sched_toggle = ctk.CTkButton(
            self.sched_card,
            text="开启定时推送",
            height=32,
            corner_radius=8,
            fg_color=APPLE_GREEN,
            hover_color="#2da84a",
            font=self.f_nav_bold,
            command=self._toggle_scheduler
        )
        self.btn_sched_toggle.pack(fill="x", padx=12, pady=(0, 12))

        # 外观切换
        ctk.CTkLabel(self.sidebar, text="外观模式:", font=self.f_small, text_color="gray").grid(row=11, column=0, padx=20, pady=(0, 2), sticky="w")
        self.theme_opt = ctk.CTkOptionMenu(
            self.sidebar,
            values=["System", "Light", "Dark"],
            height=30,
            corner_radius=8,
            command=self._change_theme
        )
        self.theme_opt.grid(row=12, column=0, padx=16, pady=(0, 20), sticky="ew")
        self.theme_opt.set(self.cfg.get("ui_theme", "System"))

        # 2. 主页面容器
        self.content_container = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content_container.grid(row=0, column=1, sticky="nsew", padx=20, pady=16)
        self.content_container.grid_rowconfigure(0, weight=1)
        self.content_container.grid_columnconfigure(0, weight=1)

        self.pages = {}
        self.pages["dash"] = self._create_dash_page()
        self.pages["settings"] = self._create_settings_page()
        self.pages["guide"] = self._create_guide_page()

    def _switch_page(self, page_name: str):
        self.current_page = page_name
        for name, page in self.pages.items():
            if name == page_name:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()

        for name, btn in self.nav_buttons.items():
            if name == page_name:
                btn.configure(fg_color=APPLE_BLUE, hover_color=APPLE_BLUE_HOVER, text_color="#ffffff", font=self.f_nav_bold)
            else:
                btn.configure(fg_color="transparent", hover_color=("gray85", "gray25"), text_color=("gray10", "gray90"), font=self.f_nav)

    # -------------------------------------------------------------
    # 页面 1：实时快讯大厅
    # -------------------------------------------------------------
    def _create_dash_page(self):
        page = ctk.CTkFrame(self.content_container, corner_radius=16, fg_color="transparent")

        toolbar = ctk.CTkFrame(page, corner_radius=16, fg_color=("white", "#27272a"), border_width=1, border_color=("gray85", "gray30"))
        toolbar.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(toolbar, text="抓取数量:", font=self.f_body).pack(side="left", padx=(16, 4), pady=12)
        self.combo_count = ctk.CTkComboBox(toolbar, values=["10", "15", "20", "30", "50"], width=80, corner_radius=8, command=self._on_count_changed)
        self.combo_count.pack(side="left", padx=(0, 10), pady=12)
        self.combo_count.set(str(self.cfg.get("news_limit", 20)))

        ctk.CTkLabel(toolbar, text="分类筛选:", font=self.f_body).pack(side="left", padx=(4, 4), pady=12)
        self.combo_cat_filter = ctk.CTkComboBox(
            toolbar,
            values=["全部分类", "宏观政策", "A股市场", "科技产业", "大宗商品", "全球要闻"],
            width=108,
            corner_radius=8,
            command=self._on_category_filter_changed
        )
        self.combo_cat_filter.pack(side="left", padx=(0, 10), pady=12)
        self.combo_cat_filter.set("全部分类")

        self.btn_fetch = ctk.CTkButton(
            toolbar,
            text="抓取最新快讯",
            corner_radius=10,
            font=self.f_nav_bold,
            fg_color=APPLE_BLUE,
            hover_color=APPLE_BLUE_HOVER,
            width=120,
            command=self._on_fetch_news
        )
        self.btn_fetch.pack(side="left", padx=6, pady=12)

        self.btn_ai = ctk.CTkButton(
            toolbar,
            text="AI 研报点评",
            corner_radius=10,
            font=self.f_nav_bold,
            fg_color=APPLE_PURPLE,
            hover_color="#9333ea",
            width=125,
            command=self._on_ai_analyze
        )
        self.btn_ai.pack(side="left", padx=6, pady=12)

        self.btn_test_ai_quick = ctk.CTkButton(
            toolbar,
            text="测试 AI 生效",
            corner_radius=10,
            font=self.f_small_bold,
            fg_color=("#e0e7ff", "#312e81"),
            text_color=("#4338ca", "#c7d2fe"),
            hover_color=("#c7d2fe", "#3730a3"),
            width=115,
            command=self._diagnose_ai_effective
        )
        self.btn_test_ai_quick.pack(side="left", padx=6, pady=12)

        self.btn_export = ctk.CTkButton(
            toolbar,
            text="导出表格",
            corner_radius=10,
            font=self.f_body,
            fg_color=("gray85", "gray35"),
            hover_color=("gray75", "gray40"),
            text_color=("black", "white"),
            width=85,
            command=self._on_export
        )
        self.btn_export.pack(side="left", padx=6, pady=12)

        self.btn_push = ctk.CTkButton(
            toolbar,
            text="推送到微信/邮箱",
            corner_radius=10,
            font=self.f_nav_bold,
            fg_color=APPLE_BLUE,
            hover_color=APPLE_BLUE_HOVER,
            width=160,
            command=self._on_send_now
        )
        self.btn_push.pack(side="right", padx=16, pady=12)

        self.lbl_ai_status_badge = ctk.CTkLabel(toolbar, text="AI 未启用", font=self.f_small, text_color="gray")
        self.lbl_ai_status_badge.pack(side="right", padx=10)

        # 极致扁平化高性能滚动卡片容器
        self.cards_scroll = ctk.CTkScrollableFrame(
            page,
            corner_radius=16,
            fg_color=("white", "#1c1c1e"),
            border_width=1,
            border_color=("gray85", "gray30"),
            label_text="实时财经快讯与投研分析列表"
        )
        self.cards_scroll.pack(fill="both", expand=True, pady=(0, 10))

        log_card = ctk.CTkFrame(page, height=72, corner_radius=14, fg_color=("white", "#27272a"), border_width=1, border_color=("gray85", "gray30"))
        log_card.pack(fill="x")

        self.log_text = ctk.CTkTextbox(log_card, height=65, font=("Consolas", 10), wrap="word", fg_color="transparent")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=4)

        return page

    # -------------------------------------------------------------
    # 页面 2：系统设置 (新增一键获取模型列表)
    # -------------------------------------------------------------
    def _create_settings_page(self):
        page = ctk.CTkScrollableFrame(self.content_container, corner_radius=16, fg_color="transparent")

        # 1. 邮箱与微信配置
        c1 = ctk.CTkFrame(page, corner_radius=16, fg_color=("white", "#1c1c1e"), border_width=1, border_color=("gray85", "gray30"))
        c1.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(c1, text="邮箱推送与微信秒级提醒", font=ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold")).pack(anchor="w", padx=20, pady=(16, 4))

        tip_box = ctk.CTkFrame(c1, corner_radius=10, fg_color=("#e0f2fe", "#082f49"))
        tip_box.pack(fill="x", padx=20, pady=(4, 12))
        ctk.CTkLabel(
            tip_box,
            text="接收邮箱直接填回发件人即可，自己发给自己绝对不进垃圾箱。微信开启「QQ邮箱提醒」后可秒级接收卡片通知。",
            font=self.f_small,
            text_color=("#0369a1", "#38bdf8"),
            wraplength=760,
            justify="left"
        ).pack(anchor="w", padx=12, pady=8)

        r1 = ctk.CTkFrame(c1, fg_color="transparent")
        r1.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(r1, text="发件人 QQ 邮箱:", width=140, anchor="w", font=self.f_body).pack(side="left")
        self.ent_sender = ctk.CTkEntry(r1, width=320, corner_radius=8, placeholder_text="例如: your_qq@qq.com")
        self.ent_sender.pack(side="left", padx=10)

        r2 = ctk.CTkFrame(c1, fg_color="transparent")
        r2.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(r2, text="16位 SMTP 授权码:", width=140, anchor="w", font=self.f_body).pack(side="left")
        self.ent_auth = ctk.CTkEntry(r2, width=320, corner_radius=8, show="*", placeholder_text="QQ邮箱设置页面生成的16位字母")
        self.ent_auth.pack(side="left", padx=10)
        self.btn_pwd_eye = ctk.CTkButton(r2, text="显示", width=55, corner_radius=6, fg_color=("gray80", "gray35"), text_color=("black", "white"), command=self._toggle_pwd)
        self.btn_pwd_eye.pack(side="left")

        r3 = ctk.CTkFrame(c1, fg_color="transparent")
        r3.pack(fill="x", padx=20, pady=(6, 18))
        ctk.CTkLabel(r3, text="接收人邮箱 (微信接收):", width=140, anchor="w", font=self.f_body).pack(side="left")
        self.ent_receiver = ctk.CTkEntry(r3, width=320, corner_radius=8, placeholder_text="多个邮箱用逗号隔开即可群发，留空默认发给自己")
        self.ent_receiver.pack(side="left", padx=10)

        # 2. 信息源与去重
        c_src = ctk.CTkFrame(page, corner_radius=16, fg_color=("white", "#1c1c1e"), border_width=1, border_color=("gray85", "gray30"))
        c_src.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(c_src, text="资讯信源抓取与跨源去重", font=ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold")).pack(anchor="w", padx=20, pady=(16, 8))

        r_src = ctk.CTkFrame(c_src, fg_color="transparent")
        r_src.pack(fill="x", padx=20, pady=4)
        self.chk_sina = ctk.CTkCheckBox(r_src, text="新浪财经 7x24", font=self.f_body)
        self.chk_sina.pack(side="left", padx=(0, 20))
        self.chk_sina.select()

        self.chk_wscn = ctk.CTkCheckBox(r_src, text="华尔街见闻", font=self.f_body)
        self.chk_wscn.pack(side="left", padx=(0, 20))
        self.chk_wscn.select()

        self.chk_cls = ctk.CTkCheckBox(r_src, text="财联社 (AKShare)", font=self.f_body)
        self.chk_cls.pack(side="left", padx=(0, 20))

        r_dedup = ctk.CTkFrame(c_src, fg_color="transparent")
        r_dedup.pack(fill="x", padx=20, pady=(10, 8))
        self.chk_dedup = ctk.CTkCheckBox(
            r_dedup,
            text="开启跨源智能相似度去重 (自动识别同类事件报道并合并归并，保留内容最详尽的源)",
            font=self.f_body
        )
        self.chk_dedup.pack(side="left")
        self.chk_dedup.select()

        # 关注领域分类多选
        r_cat_lbl = ctk.CTkFrame(c_src, fg_color="transparent")
        r_cat_lbl.pack(fill="x", padx=20, pady=(8, 2))
        ctk.CTkLabel(r_cat_lbl, text="关注领域分类 (仅保留所选领域的要闻，未勾选的杂讯自动剔除):", font=self.f_small_bold).pack(side="left")

        r_cats = ctk.CTkFrame(c_src, fg_color="transparent")
        r_cats.pack(fill="x", padx=20, pady=(4, 16))

        self.chk_cat_macro = ctk.CTkCheckBox(r_cats, text="宏观政策", font=self.f_body)
        self.chk_cat_macro.pack(side="left", padx=(0, 14))

        self.chk_cat_stock = ctk.CTkCheckBox(r_cats, text="A股市场", font=self.f_body)
        self.chk_cat_stock.pack(side="left", padx=(0, 14))

        self.chk_cat_tech = ctk.CTkCheckBox(r_cats, text="科技产业", font=self.f_body)
        self.chk_cat_tech.pack(side="left", padx=(0, 14))

        self.chk_cat_comm = ctk.CTkCheckBox(r_cats, text="大宗商品", font=self.f_body)
        self.chk_cat_comm.pack(side="left", padx=(0, 14))

        self.chk_cat_global = ctk.CTkCheckBox(r_cats, text="全球要闻", font=self.f_body)
        self.chk_cat_global.pack(side="left", padx=(0, 14))

        self.chk_cat_social = ctk.CTkCheckBox(r_cats, text="社会民生 (灾害/事故/通报)", font=self.f_body)
        self.chk_cat_social.pack(side="left")

        # 3. 大模型 AI 分析设置 (支持一键拉取可用模型与思考深度)
        c2 = ctk.CTkFrame(page, corner_radius=16, fg_color=("white", "#1c1c1e"), border_width=1, border_color=("gray85", "gray30"))
        c2.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(c2, text="大模型 AI 智能分析、模型获取与提示词", font=ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold")).pack(anchor="w", padx=20, pady=(16, 6))

        r4 = ctk.CTkFrame(c2, fg_color="transparent")
        r4.pack(fill="x", padx=20, pady=4)
        self.switch_llm = ctk.CTkSwitch(r4, text="启用 AI 智能分析 (自动提炼行业利好/利空与影响程度分级，推送时自动生效)", font=self.f_body)
        self.switch_llm.pack(side="left")

        r5 = ctk.CTkFrame(c2, fg_color="transparent")
        r5.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(r5, text="服务商预设 (Provider):", width=140, anchor="w", font=self.f_body).pack(side="left")
        self.combo_provider = ctk.CTkComboBox(r5, values=list(LLM_PROVIDERS.keys()), width=260, corner_radius=8, command=self._on_provider_changed)
        self.combo_provider.pack(side="left", padx=10)
        self.lbl_provider_note = ctk.CTkLabel(r5, text="", font=self.f_small, text_color=APPLE_PURPLE)
        self.lbl_provider_note.pack(side="left", padx=6)

        r_depth = ctk.CTkFrame(c2, fg_color="transparent")
        r_depth.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(r_depth, text="思考强度 / 推理深度:", width=140, anchor="w", font=self.f_body).pack(side="left")
        self.combo_depth = ctk.CTkComboBox(
            r_depth,
            values=["深度研判 (Balanced · 推荐)", "快速精炼 (Fast · 简洁)", "长思维链深度推演 (Deep · 宏观产业链)"],
            width=280,
            corner_radius=8
        )
        self.combo_depth.pack(side="left", padx=10)

        r_conc = ctk.CTkFrame(c2, fg_color="transparent")
        r_conc.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(r_conc, text="请求并发模式:", width=140, anchor="w", font=self.f_body).pack(side="left")
        self.combo_concurrency = ctk.CTkComboBox(
            r_conc,
            values=["串行保守 (推荐 · 兼容所有服务商)", "2 路并发 (需服务商支持)", "3 路并发 (仅限高额度账户)"],
            width=280,
            corner_radius=8
        )
        self.combo_concurrency.pack(side="left", padx=10)
        ctk.CTkLabel(
            r_conc,
            text="遇限流自动退避重试",
            font=self.f_small,
            text_color=APPLE_PURPLE
        ).pack(side="left", padx=6)

        r6 = ctk.CTkFrame(c2, fg_color="transparent")
        r6.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(r6, text="API Key 秘钥:", width=140, anchor="w", font=self.f_body).pack(side="left")
        self.ent_ai_key = ctk.CTkEntry(r6, width=400, corner_radius=8, show="*", placeholder_text="sk-xxxxxxxxxxxxxxxx (若用本地 Ollama 可不填)")
        self.ent_ai_key.pack(side="left", padx=10)

        r7 = ctk.CTkFrame(c2, fg_color="transparent")
        r7.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(r7, text="Base URL 接口地址:", width=140, anchor="w", font=self.f_body).pack(side="left")
        self.ent_ai_url = ctk.CTkEntry(r7, width=400, corner_radius=8, placeholder_text="https://api.deepseek.com")
        self.ent_ai_url.pack(side="left", padx=10)

        # 模型名称行：支持一键获取模型列表
        r8 = ctk.CTkFrame(c2, fg_color="transparent")
        r8.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(r8, text="模型名称 (Model):", width=140, anchor="w", font=self.f_body).pack(side="left")
        self.combo_ai_model = ctk.CTkComboBox(
            r8,
            values=["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"],
            width=230,
            corner_radius=8
        )
        self.combo_ai_model.pack(side="left", padx=10)

        self.btn_fetch_models = ctk.CTkButton(
            r8,
            text="获取可用模型",
            width=115,
            corner_radius=8,
            fg_color=("#e0e7ff", "#312e81"),
            text_color=("#4338ca", "#c7d2fe"),
            hover_color=("#c7d2fe", "#3730a3"),
            font=self.f_small_bold,
            command=self._on_fetch_available_models
        )
        self.btn_fetch_models.pack(side="left", padx=6)

        self.btn_test_ai = ctk.CTkButton(
            r8,
            text="测试连通性",
            width=100,
            corner_radius=8,
            fg_color=APPLE_PURPLE,
            hover_color="#9333ea",
            font=self.f_small_bold,
            command=self._test_ai_connection
        )
        self.btn_test_ai.pack(side="left", padx=6)

        # 自定义提示词
        r_prompt_lbl = ctk.CTkFrame(c2, fg_color="transparent")
        r_prompt_lbl.pack(fill="x", padx=20, pady=(10, 4))
        ctk.CTkLabel(r_prompt_lbl, text="自定义 System Prompt (提示词):", font=self.f_small_bold).pack(side="left")

        btn_reset_prompt = ctk.CTkButton(
            r_prompt_lbl,
            text="恢复默认行业投研提示词",
            width=150,
            height=24,
            corner_radius=6,
            fg_color=("gray85", "gray30"),
            hover_color=("gray75", "gray40"),
            text_color=("black", "white"),
            font=self.f_small,
            command=self._reset_to_default_prompt
        )
        btn_reset_prompt.pack(side="right")

        self.txt_prompt = ctk.CTkTextbox(c2, height=120, font=("Consolas", 10), corner_radius=8)
        self.txt_prompt.pack(fill="x", padx=20, pady=(0, 16))

        # 4. 定时轮询卡片
        c3 = ctk.CTkFrame(page, corner_radius=16, fg_color=("white", "#1c1c1e"), border_width=1, border_color=("gray85", "gray30"))
        c3.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(c3, text="定时推送计划时段", font=ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold")).pack(anchor="w", padx=20, pady=(16, 6))

        r9 = ctk.CTkFrame(c3, fg_color="transparent")
        r9.pack(fill="x", padx=20, pady=4)
        self.sched_mode_var = ctk.StringVar(value="classic")
        self.radio_classic = ctk.CTkRadioButton(r9, text="经典三时段 (早盘 08:30 / 午间 12:00 / 收盘 16:00)", variable=self.sched_mode_var, value="classic", command=self._on_sched_mode_changed)
        self.radio_classic.pack(side="left", padx=(0, 20))

        self.radio_custom = ctk.CTkRadioButton(r9, text="自定义指定时点", variable=self.sched_mode_var, value="custom", command=self._on_sched_mode_changed)
        self.radio_custom.pack(side="left")

        r10 = ctk.CTkFrame(c3, fg_color="transparent")
        r10.pack(fill="x", padx=20, pady=(6, 18))
        ctk.CTkLabel(r10, text="自定义时点 (逗号分隔):", width=140, anchor="w", font=self.f_body).pack(side="left")
        self.ent_custom_times = ctk.CTkEntry(r10, width=320, corner_radius=8, placeholder_text="例如: 09:15, 14:30, 21:00")
        self.ent_custom_times.pack(side="left", padx=10)

        # 保存所有设置
        self.btn_save_all = ctk.CTkButton(
            page,
            text="保存并应用所有配置",
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
    # 页面 3：原生卡片式新手指南
    # -------------------------------------------------------------
    def _create_guide_page(self):
        page = ctk.CTkScrollableFrame(self.content_container, corner_radius=16, fg_color="transparent")

        header = ctk.CTkFrame(page, fg_color="transparent")
        header.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(header, text="快速上手与使用指引", font=ctk.CTkFont(family="Microsoft YaHei UI", size=18, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(header, text="只需 3 步，即可实现电脑自动化抓取财经要闻并推送到你的手机微信。", font=self.f_body, text_color="gray").pack(anchor="w", pady=(2, 0))

        # 步骤 1
        g1 = ctk.CTkFrame(page, corner_radius=16, fg_color=("white", "#1c1c1e"), border_width=1, border_color=("gray85", "gray30"))
        g1.pack(fill="x", pady=(0, 14))

        h1 = ctk.CTkFrame(g1, fg_color="transparent")
        h1.pack(fill="x", padx=18, pady=(16, 6))
        ctk.CTkLabel(h1, text=" 1 ", font=self.f_small_bold, fg_color=APPLE_BLUE, text_color="white", corner_radius=6, width=26, height=26).pack(side="left")
        ctk.CTkLabel(h1, text=" 获取 QQ 邮箱 16 位 SMTP 授权码", font=ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold")).pack(side="left", padx=8)

        steps1 = (
            "1. 电脑浏览器打开 QQ 邮箱官网：mail.qq.com 并扫码登录；\n"
            "2. 点击顶部「设置」➔ 切换到「账户」选项卡；\n"
            "3. 向下滚动找到「POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务」；\n"
            "4. 开启「POP3/SMTP服务」，按提示手机发短信验证；\n"
            "5. 验证通过后生成一串 16 位的英文授权码，复制备用。"
        )
        ctk.CTkLabel(g1, text=steps1, font=self.f_body, text_color=("gray20", "gray80"), justify="left").pack(anchor="w", padx=22, pady=(0, 16))

        # 步骤 2
        g2 = ctk.CTkFrame(page, corner_radius=16, fg_color=("white", "#1c1c1e"), border_width=1, border_color=("gray85", "gray30"))
        g2.pack(fill="x", pady=(0, 14))

        h2 = ctk.CTkFrame(g2, fg_color="transparent")
        h2.pack(fill="x", padx=18, pady=(16, 6))
        ctk.CTkLabel(h2, text=" 2 ", font=self.f_small_bold, fg_color=APPLE_GREEN, text_color="white", corner_radius=6, width=26, height=26).pack(side="left")
        ctk.CTkLabel(h2, text=" 手机微信开启「QQ 邮箱提醒」", font=ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold")).pack(side="left", padx=8)

        steps2 = (
            "1. 打开手机微信，在顶部搜索框输入「QQ邮箱提醒」并进入该服务插件；\n"
            "2. 确保开启提醒并绑定你的 QQ 邮箱；\n"
            "3. 只要程序发出早报邮件，微信就会自动弹出卡片通知！"
        )
        ctk.CTkLabel(g2, text=steps2, font=self.f_body, text_color=("gray20", "gray80"), justify="left").pack(anchor="w", padx=22, pady=(0, 16))

        # 步骤 3
        g3 = ctk.CTkFrame(page, corner_radius=16, fg_color=("white", "#1c1c1e"), border_width=1, border_color=("gray85", "gray30"))
        g3.pack(fill="x", pady=(0, 14))

        h3 = ctk.CTkFrame(g3, fg_color="transparent")
        h3.pack(fill="x", padx=18, pady=(16, 6))
        ctk.CTkLabel(h3, text=" 3 ", font=self.f_small_bold, fg_color=APPLE_PURPLE, text_color="white", corner_radius=6, width=26, height=26).pack(side="left")
        ctk.CTkLabel(h3, text=" 自动获取可用模型与行业研判", font=ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold")).pack(side="left", padx=8)

        steps3 = (
            "• 输入 API Key 后，点击「获取可用模型」可一键拉取当前 Key 支持的全部模型列表并点选；\n"
            "• 每次抓取后自动开展行业受益/受损细分与影响程度评级 (重大/中度/轻度)；\n"
            "• 点击「测试 AI 生效」可随时弹窗进行现场实际效果诊断与对比。"
        )
        ctk.CTkLabel(g3, text=steps3, font=self.f_body, text_color=("gray20", "gray80"), justify="left").pack(anchor="w", padx=22, pady=(0, 16))

        ctk.CTkButton(
            page,
            text="前往【系统与 AI 配置】进行配置",
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
            self.combo_ai_model.set(info["model"])
            self.lbl_provider_note.configure(text=f"{info['note']}")

    def _on_fetch_available_models(self):
        """一键从 API 服务器拉取该 Key 权限下的全部可用模型"""
        api_key = self.ent_ai_key.get().strip()
        base_url = self.ent_ai_url.get().strip()

        if not base_url:
            messagebox.showwarning("提示", "请先填入 Base URL 接口地址！")
            return

        self.btn_fetch_models.configure(state="disabled", text="正在获取...")
        self.log(f"正在从 {base_url} 查询可用模型列表...")

        def worker():
            try:
                models = fetch_available_models(base_url, api_key)
                if models:
                    self.after(0, lambda: self.combo_ai_model.configure(values=models))
                    self.after(0, lambda: self.combo_ai_model.set(models[0]))
                    self.after(0, lambda: self.log(f"成功获取 {len(models)} 个可用模型！首选: {models[0]}"))
                    self.after(0, lambda: messagebox.showinfo("获取成功", f"成功检索到 {len(models)} 个可用模型！\n\n已自动填入下拉列表供直接点选。"))
                else:
                    self.after(0, lambda: self.log("未查询到可用模型列表，请确认 API Key 或接口规范。"))
                    self.after(0, lambda: messagebox.showwarning("提示", "接口未返回模型列表，请确认该服务商是否支持 /v1/models 查询。"))
            except Exception as e:
                self.after(0, lambda: self.log(f"获取模型失败: {e}"))
                self.after(0, lambda: messagebox.showerror("获取失败", str(e)))
            finally:
                self.after(0, lambda: self.btn_fetch_models.configure(state="normal", text="获取可用模型"))

        threading.Thread(target=worker, daemon=True).start()

    def _reset_to_default_prompt(self):
        self.txt_prompt.delete("1.0", "end")
        self.txt_prompt.insert("1.0", DEFAULT_SYSTEM_PROMPT.strip())
        self.log("已恢复默认行业细分与影响程度投研 Prompt。")

    def _get_reasoning_level(self) -> str:
        val = self.combo_depth.get()
        if "Fast" in val:
            return "fast"
        elif "Deep" in val:
            return "deep"
        return "balanced"

    def _get_max_concurrent(self) -> int:
        val = self.combo_concurrency.get()
        if "2 路" in val:
            return 2
        elif "3 路" in val:
            return 3
        return 1

    def _test_ai_connection(self):
        api_key = self.ent_ai_key.get().strip()
        base_url = self.ent_ai_url.get().strip()
        model = self.combo_ai_model.get().strip()

        if not api_key and "localhost" not in base_url:
            messagebox.showwarning("提示", "请先填入 API Key 秘钥！")
            return

        self.btn_test_ai.configure(state="disabled", text="正在连接...")
        self.log(f"开始测试大模型连通性 (Model: {model}) ...")

        def worker():
            start_t = time.time()
            test_sample = [
                {"time": "16:00", "title": "中央汇金加大ETF增持力度", "content": "中央汇金公告已再次扩大ETF增持范围，稳步维护资本市场平稳运行。"}
            ]
            try:
                res = analyze_news_with_llm(
                    test_sample,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    system_prompt=self.txt_prompt.get("1.0", "end").strip(),
                    reasoning_level=self._get_reasoning_level(),
                    max_concurrent=self._get_max_concurrent(),
                    max_analyze=1
                )
                duration = round(time.time() - start_t, 2)
                if res and "ai_comment" in res[0]:
                    comment = res[0]["ai_comment"]
                    ben = res[0].get("beneficiary", "大盘权重")
                    deg = res[0].get("impact_degree", "重大影响")
                    self.after(0, lambda: self.log(f"AI 连通测试成功！耗时 {duration}s。视点: {comment}"))
                    self.after(0, lambda: messagebox.showinfo(
                        "测试成功",
                        f"大模型 API 连接正常！\n\n• 耗时: {duration} 秒\n• 模型: {model}\n• 影响分级: {deg}\n• 受益行业: {ben}\n• 投研视点: 「{comment}」"
                    ))
                else:
                    self.after(0, lambda: self.log("连接成功但未输出规范点评，请检查提示词。"))
                    self.after(0, lambda: messagebox.showwarning("提示", "接口有返回，但未按规范输出点评字段。"))
            except Exception as e:
                self.after(0, lambda: self.log(f"AI 连通测试失败: {e}"))
                self.after(0, lambda: messagebox.showerror("连接失败", f"调用失败:\n{e}"))
            finally:
                self.after(0, lambda: self.btn_test_ai.configure(state="normal", text="测试连通性"))

        threading.Thread(target=worker, daemon=True).start()

    def _update_ai_status_badge(self):
        enabled = self.cfg.get("llm_enabled", False)
        api_key = self.cfg.get("llm_api_key", "").strip()
        base_url = self.cfg.get("llm_base_url", "")
        model = self.cfg.get("llm_model", "deepseek-v4-flash")

        if enabled and (api_key or "localhost" in base_url):
            self.lbl_ai_status_badge.configure(text=f"AI 已就绪 ({model})", text_color=APPLE_GREEN)
        elif enabled and not api_key:
            self.lbl_ai_status_badge.configure(text="AI 未配秘钥", text_color="#f59e0b")
        else:
            self.lbl_ai_status_badge.configure(text="AI 未启用", text_color="gray")

    def _diagnose_ai_effective(self):
        api_key = self.ent_ai_key.get().strip()
        base_url = self.ent_ai_url.get().strip()
        model = self.combo_ai_model.get().strip()

        if not api_key and "localhost" not in base_url:
            messagebox.showwarning("提示", "AI 尚未生效！请先在【系统与 AI 配置】中填写大模型 API Key。")
            self._switch_page("settings")
            return

        self.btn_test_ai_quick.configure(state="disabled", text="正在诊断...")
        self.log(f"开始现场诊断 AI 是否生效 (模型: {model}) ...")

        def worker():
            start_t = time.time()
            if self.current_news_list:
                sample_item = [self.current_news_list[0]]
            else:
                sample_item = [{
                    "time": datetime.now().strftime("%H:%M"),
                    "title": "中央汇金再次扩大ETF增持范围",
                    "content": "中国人民银行与中央汇金表示，充分认可当前A股市场长期配置价值，今日已再次扩大交易型开放式指数基金增持范围。"
                }]

            try:
                res = analyze_news_with_llm(
                    sample_item,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    system_prompt=self.txt_prompt.get("1.0", "end").strip(),
                    reasoning_level=self._get_reasoning_level(),
                    max_concurrent=self._get_max_concurrent(),
                    max_analyze=1
                )
                duration = round(time.time() - start_t, 2)

                if res and "ai_comment" in res[0]:
                    out = res[0]
                    self.after(0, lambda: self._show_ai_diagnosis_dialog(sample_item[0], out, duration, model))
                    self.after(0, lambda: self.log(f"诊断完毕：AI 引擎 100% 正常生效！耗时: {duration}s。"))
                else:
                    self.after(0, lambda: messagebox.showwarning("诊断结果", "API 返回了数据，但未包含标准点评字段。"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("诊断失败", f"AI 未能成功生效！\n{e}"))
                self.after(0, lambda: self.log(f"AI 诊断失败: {e}"))
            finally:
                self.after(0, lambda: self.btn_test_ai_quick.configure(state="normal", text="测试 AI 生效"))

        threading.Thread(target=worker, daemon=True).start()

    def _show_ai_diagnosis_dialog(self, original: dict, analyzed: dict, duration: float, model: str):
        diag_win = ctk.CTkToplevel(self)
        diag_win.title("AI 投研分析现场诊断报告")
        diag_win.geometry("620x520")
        diag_win.minsize(540, 440)
        diag_win.grab_set()

        container = ctk.CTkFrame(diag_win, corner_radius=16, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        status_bar = ctk.CTkFrame(container, corner_radius=12, fg_color=("#ecfdf5", "#064e3b"))
        status_bar.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(
            status_bar,
            text=f"AI 引擎正常生效 · 模型: {model} · 响应耗时: {duration} 秒",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold"),
            text_color=("#047857", "#34d399")
        ).pack(anchor="w", padx=16, pady=10)

        c_orig = ctk.CTkFrame(container, corner_radius=12, fg_color=("white", "#27272a"), border_width=1, border_color=("gray85", "gray30"))
        c_orig.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(c_orig, text="原始抓取快讯输入:", font=self.f_small_bold).pack(anchor="w", padx=14, pady=(10, 4))
        ctk.CTkLabel(
            c_orig,
            text=f"【{original.get('title', '')}】\n{original.get('content', '')}",
            font=self.f_small,
            text_color=("gray30", "gray70"),
            wraplength=520,
            justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 12))

        c_ai = ctk.CTkFrame(container, corner_radius=12, fg_color=("white", "#1c1c1e"), border_width=1, border_color=("gray85", "gray30"))
        c_ai.pack(fill="both", expand=True, pady=(0, 14))

        ctk.CTkLabel(c_ai, text="大模型实时行业影响研判产出:", font=ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold"), text_color=APPLE_PURPLE).pack(anchor="w", padx=14, pady=(12, 6))

        info_row = ctk.CTkFrame(c_ai, fg_color="transparent")
        info_row.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(info_row, text=f"精练标题: {analyzed.get('title', '')}", font=self.f_title).pack(side="left")
        ctk.CTkLabel(info_row, text=f"领域: {analyzed.get('tag', '综合')}", font=self.f_small, text_color=APPLE_PURPLE).pack(side="right", padx=6)
        
        sent = analyzed.get("sentiment", "中性")
        impact = analyzed.get("impact_degree", "中度影响")
        sent_color = APPLE_RED if "利好" in sent else (APPLE_GREEN if "利空" in sent else "gray")
        ctk.CTkLabel(info_row, text=f"● {sent} ({impact})", font=self.f_small_bold, text_color=sent_color).pack(side="right", padx=6)

        # 行业细分
        ben = analyzed.get("beneficiary", "无")
        adv = analyzed.get("adverse", "无")
        ind_box = ctk.CTkFrame(c_ai, fg_color="transparent")
        ind_box.pack(fill="x", padx=14, pady=2)
        ctk.CTkLabel(ind_box, text=f"潜在受益行业: {ben}", font=self.f_small, text_color="#15803d").pack(side="left")
        ctk.CTkLabel(ind_box, text=f"潜在受损行业: {adv}", font=self.f_small, text_color="#b91c1c").pack(side="left", padx=14)

        ctk.CTkLabel(
            c_ai,
            text=f"事实要点: {analyzed.get('content', '')}",
            font=self.f_small,
            text_color=("gray20", "gray80"),
            wraplength=520,
            justify="left"
        ).pack(anchor="w", padx=14, pady=(4, 8))

        ai_box = ctk.CTkFrame(c_ai, corner_radius=8, fg_color=("#f5f3ff", "#1e1b4b"))
        ai_box.pack(fill="x", padx=14, pady=(0, 12))
        ctk.CTkLabel(
            ai_box,
            text=f"AI 投研视点：{analyzed.get('ai_comment', '')} (仅供参考)",
            font=self.f_ai_text,
            text_color=("#6d28d9", "#c084fc"),
            wraplength=500,
            justify="left"
        ).pack(anchor="w", padx=12, pady=10)

        ctk.CTkButton(
            container,
            text="我知道了 (AI 正常生效)",
            height=36,
            corner_radius=10,
            fg_color=APPLE_BLUE,
            hover_color=APPLE_BLUE_HOVER,
            command=diag_win.destroy
        ).pack(fill="x")

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
            self.log(f"已将抓取条数调整为 {choice} 条！")
        except Exception:
            pass

    def _load_config_to_ui(self):
        self.ent_sender.insert(0, self.cfg.get("sender_email", ""))
        self.ent_auth.insert(0, self.cfg.get("sender_auth_code", ""))
        self.ent_receiver.insert(0, self.cfg.get("receiver_email", ""))

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

        # 载入关注领域勾选
        saved_cats = self.cfg.get("categories", ["宏观政策", "A股市场", "科技产业", "大宗商品", "全球要闻"])
        self.chk_cat_macro.select() if "宏观政策" in saved_cats else self.chk_cat_macro.deselect()
        self.chk_cat_stock.select() if "A股市场" in saved_cats else self.chk_cat_stock.deselect()
        self.chk_cat_tech.select() if "科技产业" in saved_cats else self.chk_cat_tech.deselect()
        self.chk_cat_comm.select() if "大宗商品" in saved_cats else self.chk_cat_comm.deselect()
        self.chk_cat_global.select() if "全球要闻" in saved_cats else self.chk_cat_global.deselect()
        self.chk_cat_social.select() if "社会民生" in saved_cats else self.chk_cat_social.deselect()

        if self.cfg.get("llm_enabled", False):
            self.switch_llm.select()
        else:
            self.switch_llm.deselect()

        provider = self.cfg.get("llm_provider", "DeepSeek (深度求索)")
        if provider in LLM_PROVIDERS:
            self.combo_provider.set(provider)
            self.lbl_provider_note.configure(text=f"{LLM_PROVIDERS[provider]['note']}")

        lvl = self.cfg.get("llm_reasoning_level", "balanced")
        if lvl == "fast":
            self.combo_depth.set("快速精炼 (Fast · 简洁)")
        elif lvl == "deep":
            self.combo_depth.set("长思维链深度推演 (Deep · 宏观产业链)")
        else:
            self.combo_depth.set("深度研判 (Balanced · 推荐)")

        conc = int(self.cfg.get("llm_max_concurrent", 1))
        if conc >= 3:
            self.combo_concurrency.set("3 路并发 (仅限高额度账户)")
        elif conc == 2:
            self.combo_concurrency.set("2 路并发 (需服务商支持)")
        else:
            self.combo_concurrency.set("串行保守 (推荐 · 兼容所有服务商)")

        self.ent_ai_key.insert(0, self.cfg.get("llm_api_key", ""))
        self.ent_ai_url.insert(0, self.cfg.get("llm_base_url", "https://api.deepseek.com"))
        self.combo_ai_model.set(self.cfg.get("llm_model", "deepseek-v4-flash"))

        custom_p = self.cfg.get("custom_prompt", "")
        self.txt_prompt.delete("1.0", "end")
        self.txt_prompt.insert("1.0", custom_p.strip() if custom_p.strip() else DEFAULT_SYSTEM_PROMPT.strip())

        mode = self.cfg.get("schedule_mode", "classic")
        self.sched_mode_var.set(mode)
        self.ent_custom_times.insert(0, self.cfg.get("custom_times", "09:15, 14:30, 21:00"))
        self._on_sched_mode_changed()
        self._update_ai_status_badge()

    def _get_enabled_sources(self):
        sources = []
        if self.chk_sina.get():
            sources.append("sina")
        if self.chk_wscn.get():
            sources.append("wscn")
        if self.chk_cls.get():
            sources.append("cls")
        return sources or ["sina", "wscn"]

    def _get_enabled_categories(self):
        cats = []
        if self.chk_cat_macro.get(): cats.append("宏观政策")
        if self.chk_cat_stock.get(): cats.append("A股市场")
        if self.chk_cat_tech.get(): cats.append("科技产业")
        if self.chk_cat_comm.get(): cats.append("大宗商品")
        if self.chk_cat_global.get(): cats.append("全球要闻")
        if self.chk_cat_social.get(): cats.append("社会民生")
        return cats or ["宏观政策", "A股市场", "科技产业", "大宗商品", "全球要闻"]

    def _on_category_filter_changed(self, choice: str):
        if not self.current_news_list:
            return
        if choice == "全部分类":
            self._render_cards(self.current_news_list)
            self.log(f"已恢复呈现全部快讯 (共 {len(self.current_news_list)} 条)")
        else:
            filtered = [item for item in self.current_news_list if item.get("tag") == choice]
            self._render_cards(filtered)
            self.log(f"已切换分类视图: 【{choice}】(呈现 {len(filtered)} 条)")

    def _save_all_settings(self):
        self.cfg["sender_email"] = self.ent_sender.get().strip()
        self.cfg["sender_auth_code"] = self.ent_auth.get().strip()
        self.cfg["receiver_email"] = self.ent_receiver.get().strip() or self.cfg["sender_email"]
        self.cfg["sources"] = self._get_enabled_sources()
        self.cfg["categories"] = self._get_enabled_categories()
        self.cfg["enable_dedup"] = bool(self.chk_dedup.get())
        self.cfg["llm_enabled"] = bool(self.switch_llm.get())
        self.cfg["llm_provider"] = self.combo_provider.get()
        self.cfg["llm_api_key"] = self.ent_ai_key.get().strip()
        self.cfg["llm_base_url"] = self.ent_ai_url.get().strip()
        self.cfg["llm_model"] = self.combo_ai_model.get().strip()
        self.cfg["llm_reasoning_level"] = self._get_reasoning_level()
        self.cfg["llm_max_concurrent"] = self._get_max_concurrent()
        self.cfg["custom_prompt"] = self.txt_prompt.get("1.0", "end").strip()
        self.cfg["schedule_mode"] = self.sched_mode_var.get()
        self.cfg["custom_times"] = self.ent_custom_times.get().strip()

        if config.save_config(self.cfg):
            self.log("所有配置已持久化保存生效！")
            self._update_ai_status_badge()
            messagebox.showinfo("成功", "所有系统与 AI 配置已保存生效！")
        else:
            messagebox.showerror("错误", "保存失败，请检查读写权限。")

    def _on_fetch_news(self):
        limit = int(self.combo_count.get() or 20)
        sources = self._get_enabled_sources()
        categories = self._get_enabled_categories()
        dedup = bool(self.chk_dedup.get())

        self.btn_fetch.configure(state="disabled")
        cat_desc = "、".join(categories[:3]) + ("等" if len(categories) > 3 else "")
        self.log(f"正在从已选信源抓取前 {limit} 条快讯 (关注领域: {cat_desc})...")

        def worker():
            try:
                raw = fetch_cls_news(limit=limit * 2, enabled_sources=sources)
                threshold = 0.48 if dedup else 0.99
                # 传入 allowed_categories 进行领域精准过滤！
                cleaned = filter_and_clean_news(raw, allowed_categories=categories, dedup_threshold=threshold, max_limit=limit)

                # 若开启 AI 且配了 Key，自动触发提炼
                if self.switch_llm.get() and self.ent_ai_key.get().strip():
                    self.after(0, lambda: self.log("正在调用大模型进行行业影响分析与点评..."))
                    analyzed = analyze_news_with_llm(
                        cleaned,
                        api_key=self.ent_ai_key.get().strip(),
                        base_url=self.ent_ai_url.get().strip(),
                        model=self.combo_ai_model.get().strip(),
                        system_prompt=self.txt_prompt.get("1.0", "end").strip(),
                        reasoning_level=self._get_reasoning_level(),
                        max_concurrent=self._get_max_concurrent(),
                        max_analyze=12
                    )
                    self.current_news_list = analyzed
                else:
                    self.current_news_list = cleaned

                self.after(0, self._render_cards, self.current_news_list)
                self.after(0, lambda: self.combo_cat_filter.set("全部分类"))
            except Exception as e:
                self.after(0, lambda: self.log(f"抓取异常: {e}"))
            finally:
                self.after(0, lambda: self.btn_fetch.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_ai_analyze(self):
        if not self.current_news_list:
            messagebox.showwarning("提示", "请先抓取快讯再进行 AI 分析！")
            return

        api_key = self.ent_ai_key.get().strip()
        base_url = self.ent_ai_url.get().strip()
        model = self.combo_ai_model.get().strip()
        if not api_key and "localhost" not in base_url:
            messagebox.showwarning("提示", "请先在【系统与 AI 配置】中填写 API Key！")
            self._switch_page("settings")
            return

        self.btn_ai.configure(state="disabled")
        self.log(f"正在以 {self._get_reasoning_level()} 强度调用 {model} 模型研判行业利好利空...")

        def worker():
            try:
                analyzed = analyze_news_with_llm(
                    self.current_news_list,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    system_prompt=self.txt_prompt.get("1.0", "end").strip(),
                    reasoning_level=self._get_reasoning_level(),
                    max_concurrent=self._get_max_concurrent(),
                    max_analyze=12
                )
                self.current_news_list = analyzed
                self.after(0, self._render_cards, self.current_news_list)
                self.after(0, lambda: self.log(f"AI 行业研报分析完成！提炼出 {len(analyzed)} 条高价值要闻。"))
            except Exception as e:
                self.after(0, lambda: self.log(f"AI 分析异常: {e}"))
            finally:
                self.after(0, lambda: self.btn_ai.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _render_cards(self, news_list):
        """极致扁平化轻量渲染，单张卡片仅 1 个 Canvas，彻底消除窗口放大缩小与滚动的卡顿"""
        for widget in self.cards_scroll.winfo_children():
            widget.destroy()

        if not news_list:
            lbl = ctk.CTkLabel(self.cards_scroll, text="暂无快讯数据，请点击上方【抓取最新快讯】。", text_color="gray", font=self.f_body)
            lbl.pack(pady=40)
            return

        for idx, item in enumerate(news_list, 1):
            t = item.get("time", "")
            title = item.get("title", "")
            content = item.get("content", "")
            ai_comment = item.get("ai_comment", "")
            sentiment = item.get("sentiment", "")
            impact = item.get("impact_degree", "")
            ben = item.get("beneficiary", "")
            adv = item.get("adverse", "")
            tag = item.get("tag", "")
            src = item.get("source", "快讯")

            # 扁平化单层 Card Frame
            card = ctk.CTkFrame(
                self.cards_scroll,
                corner_radius=12,
                fg_color=("white", "#27272a"),
                border_width=1,
                border_color=("gray85", "gray30")
            )
            card.pack(fill="x", padx=4, pady=5)

            # 顶栏单行直接 pack
            head_line = ctk.CTkFrame(card, fg_color="transparent")
            head_line.pack(fill="x", padx=14, pady=(10, 2))

            ctk.CTkLabel(head_line, text=f"#{idx}", font=self.f_small_bold, text_color=APPLE_BLUE).pack(side="left")
            ctk.CTkLabel(head_line, text=f"{t} · {src}", font=self.f_small, text_color="gray").pack(side="left", padx=8)
            ctk.CTkLabel(head_line, text=title, font=self.f_title, anchor="w").pack(side="left", padx=4, fill="x", expand=True)

            if tag:
                ctk.CTkLabel(head_line, text=tag, font=self.f_small, text_color=APPLE_PURPLE).pack(side="right", padx=6)

            if sentiment:
                sent_color = APPLE_RED if "利好" in sentiment else (APPLE_GREEN if "利空" in sentiment else "gray")
                sent_text = f"● {sentiment}" + (f" ({impact})" if impact else "")
                ctk.CTkLabel(head_line, text=sent_text, font=self.f_small_bold, text_color=sent_color).pack(side="right", padx=6)

            # 正文内容
            ctk.CTkLabel(
                card,
                text=content,
                font=self.f_body,
                text_color=("gray20", "gray80"),
                wraplength=760,
                justify="left"
            ).pack(anchor="w", padx=14, pady=(2, 4))

            # 行业影响细分条 (始终展示，与邮件研报和诊断报告对齐)
            ind_line = ctk.CTkFrame(card, fg_color="transparent")
            ind_line.pack(fill="x", padx=14, pady=(0, 4))
            ben_show = ben if (ben and ben != "无") else "暂无明显受益板块"
            adv_show = adv if (adv and adv != "无") else "暂无明显受损板块"
            impact_show = impact if impact else "中性"
            ctk.CTkLabel(ind_line, text=f"受益板块: {ben_show}", font=self.f_small_bold, text_color="#15803d").pack(side="left", padx=(0, 12))
            ctk.CTkLabel(ind_line, text=f"受损板块: {adv_show}", font=self.f_small_bold, text_color="#b91c1c").pack(side="left", padx=(0, 12))
            ctk.CTkLabel(ind_line, text=f"影响程度: {impact_show}", font=self.f_small, text_color="gray").pack(side="left")

            # AI 投研视点专属高亮底框
            if ai_comment:
                ai_box = ctk.CTkFrame(card, fg_color=("#f5f3ff", "#1e1b4b"), corner_radius=8)
                ai_box.pack(fill="x", padx=14, pady=(2, 10))
                ctk.CTkLabel(
                    ai_box,
                    text=f"AI 投研视点：{ai_comment} (仅供参考)",
                    font=self.f_ai_text,
                    text_color=("#6d28d9", "#c084fc"),
                    wraplength=730,
                    justify="left"
                ).pack(anchor="w", padx=12, pady=6)

        self.log(f"成功渲染 {len(news_list)} 条精选快讯卡片！")

    def _on_export(self):
        if not self.current_news_list:
            messagebox.showwarning("提示", "请先抓取快讯再导出！")
            return
        out_path = os.path.join(os.path.dirname(__file__), "财经热点汇总.csv")
        try:
            f = export_to_excel(self.current_news_list, output_path=out_path)
            self.log(f"表格已导出至: {f}")
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

        # 校验 1：确保已先抓取了资讯，拒绝盲目发送
        if not self.current_news_list:
            messagebox.showwarning(
                "提示",
                "当前尚未抓取任何快讯！\n\n请先点击左上方【抓取最新快讯】，在界面上预览确认内容后再执行推送。"
            )
            return

        # 校验 2：判断是否已执行过 AI 研报分析，给出明确确认选择
        receiver_list = [r.strip() for r in receiver.replace("，", ",").replace("；", ";").replace(";", ",").split(",") if r.strip()]
        recv_desc = f"{len(receiver_list)} 个收件邮箱" if len(receiver_list) > 1 else receiver_list[0] if receiver_list else receiver
        has_ai = any("ai_comment" in item for item in self.current_news_list)
        need_run_ai = False

        if not has_ai:
            if self.switch_llm.get() and self.ent_ai_key.get().strip():
                ans = messagebox.askyesnocancel(
                    "推送确认与 AI 研判选择",
                    f"当前已抓取 {len(self.current_news_list)} 条快讯，但尚未进行【AI 深度研报点评】。\n\n"
                    "• 点击【是 (Yes)】：立即调用 AI 生成行业利好/利空分析后一并推送\n"
                    "• 点击【否 (No)】：跳过 AI 分析，直接推送当前快讯表格\n"
                    "• 点击【取消 (Cancel)】：取消本次推送"
                )
                if ans is None:
                    return
                need_run_ai = ans
            else:
                if not messagebox.askyesno("推送确认", f"确定将当前的 {len(self.current_news_list)} 条快讯立即推送到 {recv_desc}？"):
                    return
        else:
            if not messagebox.askyesno("推送确认", f"确定将已包含 AI 行业研报视点的 {len(self.current_news_list)} 条精选快讯立即推送到 {recv_desc}？"):
                return

        self.btn_push.configure(state="disabled", text="正在发送...")
        self.log(f"开始执行推送流程，目标: {recv_desc} ...")

        def worker():
            try:
                data = list(self.current_news_list)

                # 阶段 1: 若需先执行 AI 研判
                if need_run_ai:
                    self.after(0, lambda: self.log("步骤 1/3: 正在调用大模型生成行业影响分析与情绪分级..."))
                    data = analyze_news_with_llm(
                        data,
                        api_key=self.ent_ai_key.get().strip(),
                        base_url=self.ent_ai_url.get().strip(),
                        model=self.combo_ai_model.get().strip(),
                        system_prompt=self.txt_prompt.get("1.0", "end").strip(),
                        reasoning_level=self._get_reasoning_level(),
                        max_concurrent=self._get_max_concurrent(),
                        max_analyze=12
                    )
                    self.current_news_list = data
                    self.after(0, self._render_cards, data)
                else:
                    self.after(0, lambda: self.log("步骤 1/3: 快讯数据与分析已就绪。"))

                # 阶段 2: 导出与组装
                self.after(0, lambda: self.log("步骤 2/3: 正在组装移动端 HTML 研报卡片与本地备份表格..."))
                csv_file = os.path.join(os.path.dirname(__file__), "财经热点汇总.csv")
                export_to_excel(data, output_path=csv_file)
                html_card = build_html_card(data)

                # 阶段 3: 连接邮箱服务器发送
                self.after(0, lambda: self.log(f"步骤 3/3: 正在连接 SMTP 服务器发送邮件至 {receiver} ..."))
                subject = f"财经早报与智能热点精选 ({datetime.now().strftime('%m月%d日 %H:%M')})"

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
                    self.after(0, lambda: messagebox.showinfo("发送成功", "研报已成功送达！若微信绑定了 QQ 邮箱提醒将立即收到带 AI 点评的微信卡片。"))
                else:
                    self.after(0, lambda: self.log("❌ 发送失败，请检查授权码或网络连接。"))
                    self.after(0, lambda: messagebox.showerror("发送失败", "邮件未能送达，请查看日志排查授权码或网络问题。"))
            except Exception as e:
                self.after(0, lambda: self.log(f"❌ 发送异常: {e}"))
                self.after(0, lambda: messagebox.showerror("发生异常", str(e)))
            finally:
                self.after(0, lambda: self.btn_push.configure(state="normal", text="推送到微信/邮箱"))

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
            self.sched_status_lbl.configure(text="状态: 运行中", text_color=APPLE_GREEN)

            times_to_run = ["08:30", "12:00", "16:00"]
            if self.sched_mode_var.get() == "custom":
                raw_times = self.ent_custom_times.get().strip()
                if raw_times:
                    times_to_run = [t.strip() for t in raw_times.replace("，", ",").split(",") if t.strip()]

            self.log(f"定时轮询已启动！推送时点: {', '.join(times_to_run)}")

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
            self.sched_status_lbl.configure(text="状态: 未运行", text_color="gray")
            self.log("定时推送服务已停止。")

def main():
    app = AppleStyleFinanceApp()
    app.mainloop()

if __name__ == "__main__":
    main()

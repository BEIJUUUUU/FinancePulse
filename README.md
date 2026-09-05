# FinancePulse (财经脉搏)

FinancePulse 是一款面向个人投资者与研究团队的高性能财经快讯聚合与智能研报系统。系统整合了多源实时快讯抓取、跨源相似度智能去重、大模型产业影响研判、Apple HIG 现代桌面客户端，以及基于标准 SMTP 协议的微信即时消息推送。

---

## 核心特性

- 现代桌面客户端：基于 CustomTkinter 遵循 Apple 人机交互指南 (HIG) 规范设计。内置 Windows 原生 Per-Monitor DPI 缩放感知、轻量化渲染架构、专属独立应用图标，自动适应系统深色与浅色外观。
- 免中介微信直推通道：采用标准 SMTP 协议直接联动微信官方内置的 QQ 邮箱提醒功能。无需依赖商业第三方中转平台，免除账号实名认证门槛与接口封禁风险。
- 多源实时快讯聚合：原生直连新浪财经 7x24 全球快讯、华尔街见闻实时直播及财联社，支持按需并发抓取 10 至 80 条以上的宏观政策、A 股、港美股及大宗商品要闻。
- 跨源算法相似度去重：基于字符序列匹配与二元字词重叠算法，毫秒级识别并合并不同媒体对同一突发事件的同质化报道，自动标记联合信源。
- 行业利好利空与影响分级研判：全面兼容 OpenAI 标准接口协议 (DeepSeek, Kimi, 智谱 GLM, 阿里通义千问, 本地 Ollama 等)。支持一键拉取服务商可用模型列表，输出精炼要点、行业利好/利空细分、市场影响程度分级与专业投研视点。
- 思考强度与自定义提示词：内置快速精炼 (Fast)、深度研判 (Balanced) 与长思维链推演 (Deep) 三级思考强度，支持自由编辑与重置投研分析 System Prompt。
- 全自动定时推送：预设交易日经典三时段 (早盘 08:30 / 午间 12:00 / 收盘 16:00)，支持自定义任意时点列表，实现后台全天候无人值守巡检。
- 结构化归档与移动端适配：推送时自动生成自适应排版的移动端 HTML 研报卡片，并自动将结构化数据备份至本地时间戳 CSV/Excel 文件。

---

## 目录结构

```text
FinancePulse/
├── gui.pyw                 # Windows 无黑框启动入口 (通过 pythonw 执行)
├── run_gui.bat             # 双击快速启动脚本
├── gui.py                  # 桌面客户端界面与交互逻辑
├── fetcher.py              # 多信源快讯实时抓取引擎
├── processor.py            # 跨源相似度去重与 HTML 研报渲染器
├── llm_analyzer.py         # 大模型产业分析引擎与可用模型拉取工具
├── email_sender.py         # 符合 RFC5322 规范的邮件与微信直推模块
├── main.py                 # 命令行与服务器后台静默运行入口
├── config.py               # 运行时配置驱动层
├── settings.example.json   # 配置文件模板 (真实 settings.json 受 gitignore 保护)
├── requirements.txt        # 依赖包清单
├── app_icon.ico            # 专属应用图标
├── .gitignore              # 凭据与本地数据排除规则
├── LICENSE                 # MIT 开源许可证
└── README.md               # 项目使用说明书
```

---

## 安装说明

### 1. 克隆代码仓库
```bash
git clone https://github.com/BEIJUUUUU/FinancePulse.git
cd FinancePulse
```

### 2. 安装必要依赖
```bash
pip install -r requirements.txt
```

---

## 使用方式

### 桌面客户端模式 (推荐)
在 Windows 环境下，直接双击 `gui.pyw` 或 `run_gui.bat` 启动。程序启动后不会伴随黑色控制台窗口。

1. 进入系统设置页面，配置发件人 QQ 邮箱与 SMTP 授权码。
2. 勾选所需抓取信源并选择快讯条数。
3. 输入大模型 API Key，点击获取可用模型完成配置。
4. 在资讯大厅中点击抓取最新快讯，可随时点击测试 AI 生效验证分析结果。
5. 点击推送到微信/邮箱立即发送，或启动后台定时轮询服务。

### 服务器 / 命令行模式
适用于 Linux 服务器或后台静默作业：

- 单次执行推送：
  ```bash
  python main.py
  ```
- 开启后台定时轮询：
  ```bash
  python main.py --cron
  ```

---

## 微信即时提醒配置指南

1. 获取 QQ 邮箱 SMTP 授权码：
   - 登录 QQ 邮箱网页端 (mail.qq.com)，进入 设置 > 账户。
   - 找到 POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务 区域。
   - 开启 POP3/SMTP 服务，按照提示完成短信验证，获取 16 位字母授权码。
2. 开启微信邮件提醒：
   - 打开手机微信，在搜索栏中检索 QQ邮箱提醒 插件并启用。
   - 绑定对应的 QQ 邮箱账号。
3. 填写配置并生效：
   - 在 FinancePulse 设置页面中填入发件人 QQ 邮箱与 16 位授权码。
   - 接收人邮箱直接填写该 QQ 邮箱 (或保持留空，默认发给自己)。自己发给自己可避免垃圾邮件拦截，微信将即时接收卡片通知。

---

## 大模型服务商支持矩阵

| 服务商 | Base URL | 默认推荐模型 | 认证机制 |
| :--- | :--- | :--- | :--- |
| DeepSeek (深度求索) | `https://api.deepseek.com` | `deepseek-v4-flash` / `deepseek-chat` | API Key |
| Kimi / Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` | API Key |
| 智谱 AI (GLM) | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` | API Key |
| 阿里通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-turbo` | API Key |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | API Key |
| 本地 Ollama | `http://localhost:11434/v1` | `qwen2.5:7b` | 免密本地运行 |

系统内置三级思考强度控制：
- 快速精炼 (Fast)：采样温度 0.1，紧扣客观事实，极简输出。
- 深度研判 (Balanced)：采样温度 0.3，兼顾宏观逻辑与产业链关联。
- 长链推演 (Deep)：采样温度 0.5，深入推演衍生影响与产业分化。

---

## 安全与隐私

- 本地配置文件 `settings.json` 及生成的表格数据文件已默认列入 `.gitignore`，不会被提交至公开版本库。
- 与大模型及邮件服务器的所有网络交互均采用 TLS/SSL 加密传输。

---

## 开源许可证

本项目基于 [MIT License](LICENSE) 许可协议开源。

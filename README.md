<div align="center">

# 📈 FinancePulse (财经脉搏)
### 现代化桌面财经早报 · 智能研报分析与微信推送助手

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![UI](https://img.shields.io/badge/Design-Apple%20HIG%20Fluent-purple.svg)](https://github.com/BEIJUUUUU/FinancePulse)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)](https://github.com/BEIJUUUUU/FinancePulse)

**零成本、零第三方实名限制、极速开箱即用的现代化金融早报助手**  
集成了 **多信源聚合采集**、**跨源相似度智能去重**、**大模型 (DeepSeek/Kimi/GLM) 投研深度点评**、**Apple 风格现代桌面 GUI** 与 **手机微信秒级卡片弹窗直推**。

</div>

---

## 🌟 核心特性 (Features)

- 🍎 **Apple 风格现代极简桌面端**：基于 `CustomTkinter` 遵循 Apple HIG 规范打造，大圆角、纯净卡片层次、单层侧边栏导航、系统深浅色自适应，彻底消除命令行黑框。
- 📱 **直通手机微信秒级弹窗**：无需购买昂贵的商业第三方接口，无封号与实名风险。利用微信官方内置的「QQ 邮箱提醒」插件，邮件送达即刻在手机微信触发卡片式服务通知。
- ⚡ **权威多信源毫秒级聚合**：原生直连新浪财经 7x24 全球快讯、华尔街见闻实时直播、财联社等权威源，秒级拉取 10~80+ 条实时全球宏观、A股与港美股热点。
- 🧠 **创新跨源相似度智能去重**：内置序列字面比对与二元字符特征词袋算法，瞬间识别并归并各大媒体对同一事件的冗余报道，并自动拼接多源标签。
- 🤖 **全兼容主流大模型 (LLM) 研报点评**：
  - 内置一键预设：**DeepSeek**、**Kimi (月之暗面)**、**智谱 GLM**、**阿里通义千问**、**OpenAI** 以及 **本地离线私有 Ollama**；
  - 自动提炼核心事实，生成一句话【AI 投研视点】并标注利好/利空情绪。
- ⏰ **自由定制自动化定时轮询**：支持【经典三时段（盘前 08:30 / 午盘 12:00 / 盘后 16:00）】与【任意自定义时点列表】，全天候后台静默值守。
- 📁 **多端精美表格呈现与本地归档**：微信端呈现自适应现代卡片表格，同时每次自动生成带时间戳的本地 `财经热点汇总.csv` 供下载与回溯。

---

## 📁 项目结构 (Project Structure)

```text
FinancePulse/
├── gui.pyw                 # 🌟 Windows 无黑框桌面客户端启动入口 (推荐双击运行)
├── run_gui.bat             # 🌟 一键批处理启动脚本
├── gui.py                  # Apple 风格桌面 GUI 源码 (CustomTkinter)
├── fetcher.py              # 多信源 (新浪7x24 / 华尔街见闻 / 财联社) 聚合采集引擎
├── processor.py            # 跨源相似度智能去重与 HTML 研报卡片生成器
├── llm_analyzer.py         # 大模型投研深度分析引擎 (全兼容各大主流厂商)
├── email_sender.py         # 严格遵循 RFC5322 规范的邮件与微信直推模块
├── main.py                 # 无头/服务器后台运行入口 (支持 --cron 定时)
├── config.py               # 配置加载与驱动层
├── settings.example.json   # 配置文件模板 (真实配置 settings.json 已受 gitignore 保护)
├── requirements.txt        # 依赖清单
├── .gitignore              # 严格隔离个人敏感凭据与本地数据
├── LICENSE                 # MIT 开源许可证
└── README.md               # 项目使用说明书
```

---

## 🚀 极速上手 (Quick Start)

### 1. 克隆本项目
```bash
git clone https://github.com/BEIJUUUUU/FinancePulse.git
cd FinancePulse
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```
> 如需启用额外的高阶数据源支持，可选安装：`pip install akshare pandas`

---

## 💻 使用方式 (Usage)

### 方式 A：双击运行桌面 GUI (最推荐，小白友好)
在 Windows 资源管理器中：
* **直接双击 `gui.pyw`**（或者双击 `run_gui.bat`）；
* 客户端秒级拉起，完全没有任何黑框终端！

### 方式 B：服务器 / 命令行静默运行
适合部署在 Linux / Windows 服务器进行无人值守推送：
* **执行单次推送**：
  ```bash
  python main.py
  ```
* **开启全天候定时服务**：
  ```bash
  python main.py --cron
  ```

---

## 🔑 3 步打通微信秒级推送 (WeChat Setup)

### 第一步：获取 QQ 邮箱的「16位 SMTP 授权码」
1. 电脑浏览器登录 [QQ 邮箱官网 (mail.qq.com)](https://mail.qq.com)；
2. 点击顶部 **「设置」** ➔ 切换至 **「账户」** 选项卡；
3. 向下滚动至 **「POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务」**；
4. 开启 **「POP3/SMTP服务」**，按提示用手机发送一条短信验证；
5. 验证通过后页面会弹出一串 **16 位英文授权码**（例如：`abcdefghijklmnop`），复制备用。

### 第二步：手机微信开启「QQ 邮箱提醒」
1. 打开手机微信，在顶部搜索栏搜索 **「QQ邮箱提醒」** 插件并进入；
2. 确保开启提醒并绑定你的 QQ 邮箱；
3. 只要程序发送邮件，手机微信就会像收到微信消息一样立即弹出卡片提醒！

### 第三步：在软件中保存设置
在客户端的 **【系统与 AI 配置】** 页面中：
* 发件人填入你的 QQ 邮箱；
* 填入 16 位授权码；
* **接收人邮箱直接填你自己的 QQ 邮箱（或留空即可）**：自己发给自己 100% 进收件箱，微信即时弹窗，绝不会被拦截！

---

## 🤖 大模型 (LLM) 接入支持

在设置中心选择预设厂商并填入 API Key：
* **DeepSeek (深度求索)**：官方 `https://api.deepseek.com`，模型 `deepseek-chat`
* **Kimi / Moonshot (月之暗面)**：`https://api.moonshot.cn/v1`，模型 `moonshot-v1-8k`
* **智谱 AI (GLM)**：`https://open.bigmodel.cn/api/paas/v4`，模型 `glm-4-flash`
* **阿里通义千问 (Qwen)**：`https://dashscope.aliyuncs.com/compatible-mode/v1`，模型 `qwen-turbo`
* **OpenAI (ChatGPT)**：`https://api.openai.com/v1`，模型 `gpt-4o-mini`
* **Ollama 本地私有大模型**：`http://localhost:11434/v1`，模型 `qwen2.5:7b`（纯本地离线，无需 API Key）

---

## 🛡️ 安全与隐私声明

- 本项目内置了完善的 `.gitignore` 规则，用户的密码凭据保存在本地的 `settings.json` 中，**该文件已被严格忽略，绝不会上传至公开仓库**。
- 请妥善保管个人的 16 位邮箱授权码与大模型 API Key。

---

## 📄 开源许可证 (License)

本项目基于 [MIT License](LICENSE) 协议开源。欢迎提交 Issue 与 Pull Request！

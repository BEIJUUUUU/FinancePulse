# FinancePulse

FinancePulse is a lightweight, high-performance financial news aggregator and intelligent research briefing system. It features multi-source real-time crawling, cross-source similarity deduplication, large language model (LLM) investment commentary, an Apple HIG-inspired desktop client, and native WeChat message dispatch via standard SMTP.

---

## Key Capabilities

- **Desktop Client Architecture**: Built with CustomTkinter following Apple Human Interface Guidelines (HIG). Provides native high-DPI scaling, smooth rendering, dedicated taskbar application identity, and automatic light/dark mode adaptation.
- **Zero-Intermediary WeChat Dispatch**: Utilizes standard SMTP protocol coupled with the official WeChat QQ Mail Notification plugin. Eliminates dependency on commercial third-party notification services, account verification hurdles, and risk of rate-limiting or suspensions.
- **Multi-Source Real-Time Ingestion**: Directly interfaces with major financial streams including Sina Finance 7x24, Wallstreetcn Live, and CLS, supporting on-demand acquisition of 10 to 80+ real-time macroeconomic and market events.
- **Algorithmic Cross-Source Deduplication**: Incorporates sequence matching and character n-gram token overlap algorithms to identify and merge concurrent coverage of identical market events across multiple providers.
- **LLM Research & Sentiment Synthesis**: Fully compatible with OpenAI-compliant endpoints (DeepSeek, Kimi, Zhipu GLM, Qwen, and local Ollama deployments). Generates concise key-fact summaries, investment sentiment tags (Bullish / Bearish / Neutral), and sector impact assessments, with adjustable reasoning intensity and fully customizable system prompts.
- **Automated Scheduling**: Supports both classic financial session intervals (pre-market 08:30, midday 12:00, post-market 16:00) and custom time specifications for unattended background operation.
- **Structured Data Export**: Automatically archives generated daily intelligence into timestamped CSV/Excel records while rendering responsive HTML cards for mobile clients.

---

## Project Structure

```text
FinancePulse/
├── gui.pyw                 # Windows windowless launcher (executes via pythonw)
├── run_gui.bat             # Quick batch script launcher
├── gui.py                  # Desktop application entry and UI logic
├── fetcher.py              # Multi-source financial stream ingestion engine
├── processor.py            # Similarity deduplication and HTML report generator
├── llm_analyzer.py         # LLM synthesis and reasoning engine
├── email_sender.py         # RFC5322-compliant SMTP dispatch engine
├── main.py                 # Headless CLI entry for server and cron deployments
├── config.py               # Runtime configuration loader
├── settings.example.json   # Template configuration file
├── requirements.txt        # Python dependency manifest
├── .gitignore              # Repository exclusion rules
├── LICENSE                 # MIT License
└── README.md               # Documentation
```

---

## Installation

### 1. Clone Repository
```bash
git clone https://github.com/BEIJUUUUU/FinancePulse.git
cd FinancePulse
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Usage

### Desktop Graphical Interface
On Windows, execute directly by launching `gui.pyw` or `run_gui.bat`. The application launches without spawning a terminal console window.

1. Navigate to the Configuration panel to provide sender email credentials and SMTP authorization tokens.
2. Select desired information sources and specify fetch quantity.
3. Fetch real-time market bulletins and trigger AI synthesis on demand.
4. Execute single-click dispatch to email and WeChat, or enable the background scheduler.

### Headless Server / CLI Mode
Suitable for deployment on remote servers or local scheduled tasks:

- Single run:
  ```bash
  python main.py
  ```
- Background scheduler:
  ```bash
  python main.py --cron
  ```

---

## Notification Setup (WeChat Delivery)

1. **Obtain SMTP Authorization Code**:
   - Access the QQ Mail web portal (`mail.qq.com`) and navigate to Settings > Accounts.
   - Locate the POP3/IMAP/SMTP service section and enable POP3/SMTP service.
   - Complete SMS verification to generate a 16-character alphanumeric authorization token.
2. **Enable WeChat Integration**:
   - Open WeChat, search for the official "QQ Mail Notification" (QQ邮箱提醒) feature, and enable it.
   - Bind the corresponding QQ email account.
3. **Configure FinancePulse**:
   - In FinancePulse Settings, enter your QQ email in the sender field.
   - Input the 16-character authorization token.
   - Set the recipient email to match the sender email (or leave blank to default to self-delivery).

---

## LLM Integration Reference

| Provider | Base URL | Default Model | Authentication |
| :--- | :--- | :--- | :--- |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` | API Key required |
| Kimi / Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` | API Key required |
| Zhipu AI | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` | API Key required |
| Alibaba Qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-turbo` | API Key required |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | API Key required |
| Ollama (Local) | `http://localhost:11434/v1` | `qwen2.5:7b` | None (Local instance) |

Reasoning intensity can be adjusted across three modes:
- **Fast**: Minimal temperature (0.1), highly focused on factual summary.
- **Balanced**: Standard temperature (0.3), balanced macroeconomic and market sentiment analysis.
- **Deep**: Extended reasoning chain (0.5), deeper supply-chain and derivative market impact evaluation.

---

## Security and Privacy

- Local configuration records (`settings.json`) and generated tabular datasets (`*.csv`, `*.xlsx`) are excluded by default via `.gitignore` to prevent credential exposure.
- All network communications with LLM endpoints and SMTP servers utilize TLS/SSL encryption.

---

## License

This software is released under the [MIT License](LICENSE).

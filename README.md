<div align="center">

# 📈 Daily Stock Analysis System

[![GitHub stars](https://img.shields.io/github/stars/ZhuLinsen/daily_stock_analysis?style=social)](https://github.com/ZhuLinsen/daily_stock_analysis/stargazers)
[![CI](https://github.com/ZhuLinsen/daily_stock_analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/ZhuLinsen/daily_stock_analysis/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Ready-2088FF?logo=github-actions&logoColor=white)](https://github.com/features/actions)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://hub.docker.com/r/zhulinsen/daily_stock_analysis)

<p align="center">
  <a href="https://trendshift.io/repositories/18527" target="_blank"><img src="https://trendshift.io/api/badge/repositories/18527" alt="ZhuLinsen%2Fdaily_stock_analysis | Trendshift" width="230" /></a>&nbsp;<a href="https://hellogithub.com/repository/ZhuLinsen/daily_stock_analysis" target="_blank"><img src="https://api.hellogithub.com/v1/widgets/recommend.svg?rid=6daa16e405ce46ed97b4a57706aeb29f&claim_uid=pfiJMqhR9uvDGlT&theme=neutral" alt="Featured｜HelloGitHub" width="230" /></a>
</p>

> 🤖 Intelligent stock analysis system for A-shares, Hong Kong stocks, and US stocks based on large AI models. Automatically analyzes and pushes a "Decision Dashboard" to WeChat Work, Feishu, Telegram, Discord, Slack, and Email daily.

[**Product Preview**](#-product-preview) · [**Features**](#-features) · [**Quick Start**](#-quick-start) · [**Push Examples**](#-push-examples) · [**Documentation Center**](docs/INDEX.md) · [**Full Guide**](docs/full-guide.md)

English | [Chinês Simplificado](docs/README_CN.md) | [Chinês Tradicional](docs/README_CHT.md)

</div>

## 💖 Sponsors
<div align="center">
  <p align="center">
    <a href="https://open.anspire.cn/?share_code=QFBC0FYC" target="_blank"><img src="./docs/assets/anspire.png" alt="Anspire Open One-stop Model and Search Service" width="300" height="141" style="width: 300px; height: 141px; object-fit: contain;"></a>
    <a href="https://serpapi.com/baidu-search-api?utm_source=github_daily_stock_analysis" target="_blank"><img src="./docs/assets/serpapi_banner_zh.png" alt="Easily scrape real-time financial news data from search engines - SerpApi" width="300" height="141" style="width: 300px; height: 141px; object-fit: contain;"></a>
  </p>
</div>

## 🖥️ Product Preview

<p align="center">
  <img src="docs/assets/readme_workspace_tour_20260510.gif" alt="DSA Web Workspace Demo" width="720">
</p>

## ✨ Features

| Capability | Coverage |
|------|------|
| AI Decision Report | Core conclusions, scoring, trends, buy/sell points, risk alerts, catalysts, operational checklists |
| Multi-market Data Aggregation | A-shares, Hong Kong stocks, US stocks, ETFs; Quotes, K-lines, technical indicators, money flow, chip distribution, news, announcements, and fundamentals |
| Web / Desktop Workspace | Manual analysis, task progress, historical reports, full Markdown, backtesting, holdings, configuration management, light/dark themes |
| Agent Strategy Stock Query | Multi-round questioning, supports 15 built-in strategies (e.g., Moving Average, Chan Theory, Elliott Wave, Trend, Hot Topics, Events, Growth, Expectations), covering Web/Bot/API |
| Smart Import & Autocomplete | Import via images, CSV/Excel, clipboard; Stock code/name/pinyin/alias autocomplete |
| Automation & Push Notifications | GitHub Actions, Docker, local cron tasks, FastAPI service, and WeChat Work/Feishu/Telegram/Discord/Slack/Email push |

> For feature details, field contracts, fundamental P0 timeout semantics, trading disciplines, datasource priorities, and Web/API behaviors, please see the [Full Configuration and Deployment Guide](docs/full-guide.md).

### Tech Stack and Data Sources

| Type | Supported |
|------|------|
| AI Models | [Anspire](https://open.anspire.cn/?share_code=QFBC0FYC), [AIHubMix](https://aihubmix.com/?aff=CfMq), Gemini, OpenAI Compatible, DeepSeek, Qwen, Claude, Ollama local models, etc. |
| Market Data | [TickFlow](https://tickflow.org/auth/register?ref=WDSGSPS5XC), AkShare, Tushare, Pytdx, Baostock, YFinance, Longbridge |
| News Search | [Anspire](https://open.anspire.cn/?share_code=QFBC0FYC), [SerpAPI](https://serpapi.com/baidu-search-api?utm_source=github_daily_stock_analysis), [Tavily](https://tavily.com/), [Bocha](https://open.bocha.cn/), [Brave](https://brave.com/search/api/), [MiniMax](https://platform.minimaxi.com/), SearXNG |
| Social Sentiment | [Stock Sentiment API](https://api.adanos.org/docs) (Reddit / X / Polymarket, US stocks only, optional) |

> For complete rules, see [Datasource Configuration](docs/full-guide.md#数据源配置).

## 🚀 Quick Start

### Method 1: GitHub Actions (Recommended)

> Deploy in 5 minutes, zero cost, no server required.

#### 1. Fork this Repository

Click the `Fork` button in the top right corner (and hit Star⭐ to support us).

#### 2. Configure Secrets

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

**AI Model Configuration (at least one required)**

Choose an AI provider and fill in the API Key first; if you need multi-model, image recognition, local models, or advanced routing, refer to the [LLM Configuration Guide](docs/LLM_CONFIG_GUIDE.md).

| Secret Name | Description | Required |
|------------|------|:----:|
| `ANSPIRE_API_KEYS` | [Anspire](https://open.anspire.cn/?share_code=QFBC0FYC) API Key, one key enables global popular models and web search simultaneously. Includes free tier. | **Recommended** |
| `AIHUBMIX_KEY` | [AIHubMix](https://aihubmix.com/?aff=CfMq) API Key, one key to switch between all models. Enjoy a 10% discount for this project. | **Recommended** |
| `GEMINI_API_KEY` | Google Gemini API Key | Optional |
| `ANTHROPIC_API_KEY` | Anthropic Claude API Key | Optional |
| `OPENAI_API_KEY` | OpenAI Compatible API Key (supports DeepSeek, Qwen, etc.) | Optional |
| `OPENAI_BASE_URL` / `OPENAI_MODEL` | Fill in when using OpenAI compatible services | Optional |

> Ollama is better suited for local/Docker deployment; GitHub Actions is recommended to use cloud APIs.

**Notification Channel Configuration (at least one required)**

| Secret Name | Description |
|------------|------|
| `WECHAT_WEBHOOK_URL` | WeChat Work Bot |
| `FEISHU_WEBHOOK_URL` | Feishu Bot |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Telegram |
| `DISCORD_WEBHOOK_URL` | Discord Webhook |
| `SLACK_BOT_TOKEN` + `SLACK_CHANNEL_ID` | Slack Bot |
| `EMAIL_SENDER` + `EMAIL_PASSWORD` | Email Push |

For more channels, signature verification, grouped emails, and Markdown-to-image configurations, see [Detailed Notification Channel Configuration](docs/full-guide.md#通知渠道详细配置).

**Stock Watchlist Configuration (Required)**

| Secret Name | Description | Required |
|------------|------|:----:|
| `STOCK_LIST` | Watchlist stock codes, e.g., `600519,hk00700,AAPL,TSLA` | ✅ |

**News Source Configuration (Recommended)**

News sources significantly impact sentiment, announcements, events, and catalyst quality. It's recommended to configure at least one search service.

| Secret Name | Description | Required |
|------------|------|:----:|
| `ANSPIRE_API_KEYS` | [Anspire AI Search](https://aisearch.anspire.cn/): Specially optimized for Chinese content; the same Key can be reused for the Anspire LLM | **Recommended** |
| `SERPAPI_API_KEYS` | [SerpAPI](https://serpapi.com/baidu-search-api?utm_source=github_daily_stock_analysis): Search engine results reinforcement, ideal for real-time financial news | **Recommended** |
| `TAVILY_API_KEYS` | [Tavily](https://tavily.com/): General news search API | Optional |
| `BOCHA_API_KEYS` | [Bocha Search](https://open.bocha.cn/): Chinese search optimization, supports AI summaries | Optional |
| `BRAVE_API_KEYS` | [Brave Search](https://brave.com/search/api/): Privacy-first, US stock info reinforcement | Optional |
| `MINIMAX_API_KEYS` | [MiniMax](https://platform.minimaxi.com/): Structured search results | Optional |
| `SEARXNG_BASE_URLS` | SearXNG self-hosted instance: No quota fallback, suitable for private deployment | Optional |

For more search sources, social sentiment, and fallback rules, see [Search Service Configuration](docs/full-guide.md#搜索服务配置).

#### 3. Enable Actions

Go to the `Actions` tab → `I understand my workflows, go ahead and enable them`

#### 4. Manual Testing

`Actions` → `Daily Stock Analysis` (Análise Diária de Ações) → `Run workflow` → `Run workflow`

#### Done

By default, it automatically executes every **workday at 18:00 (Beijing Time)**, or can be triggered manually. Non-trading days (including A-share/HK/US holidays) are skipped by default. For force-run, trading day checks, resumable executions, etc., see the [Full Guide](docs/full-guide.md#定时任务配置).

### Method 2: Local Run / Docker Deployment

```bash
# Clone the project
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git && cd daily_stock_analysis

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env && vim .env

# Run analysis
python main.py
```

Common Commands:

```bash
python main.py --debug
python main.py --dry-run
python main.py --stocks 600519,hk00700,AAPL
python main.py --market-review
python main.py --schedule
python main.py --serve-only
```

> For Docker deployment, cron tasks, and cloud server access, refer to the [Full Guide](docs/full-guide.md); for desktop client packaging, see [Desktop Packaging Guide](docs/desktop-package.md).

## 📱 Push Examples

### Decision Dashboard
```
🎯 2026-02-08 Decision Dashboard
Total 3 stocks analyzed | 🟢 Buy: 0 🟡 Wait & See: 2 🔴 Sell: 1

📊 Analysis Summary
⚪ Zhongwu High-tech (000657): Wait & See | Score 65 | Bullish
⚪ Yongding Corp (600105): Wait & See | Score 48 | Oscillating
🟡 Xinlai App. Mat. (300260): Sell | Score 35 | Bearish

⚪ Zhongwu High-tech (000657)
📰 Key Information Quick Glance
💭 Sentiment: Market focuses on its AI attributes and high performance growth, sentiment is slightly positive, but needs to digest short-term profit-taking and institutional outflow pressure.
📊 Performance Expectation: Based on sentiment info, the company's Q1-Q3 2025 net profit YoY grew significantly, fundamentals are strong, providing support for the stock price.

🚨 Risk Alerts:
Risk 1: Net institutional outflow of 363 million CNY on Feb 5, beware of short-term selling pressure.
Risk 2: Chip concentration is as high as 35.15%, indicating dispersed chips, potential high resistance to price increases.
Risk 3: Sentiment mentioned historical compliance records and restructuring risks, requires close monitoring.

✨ Catalysts:
Catalyst 1: The company is positioned by the market as a core HDI supplier for AI servers, benefiting from AI industry development.
Catalyst 2: Q1-Q3 2025 non-GAAP net profit surged 407.52% YoY, strong performance.

📢 Latest Dynamics: [Latest News] Sentiment shows the company is a leader in AI PCB micro-drills, deeply bound to global top PCB/substrate manufacturers. Institutional outflow of 363M CNY on Feb 5, monitor subsequent money flow.

---
Generated at: 18:00
```

### Market Review
```
🎯 2026-01-10 Market Review

📊 Major Indices
- Shanghai Composite: 3250.12 (🟢+0.85%)
- Shenzhen Component: 10521.36 (🟢+1.02%)
- ChiNext: 2156.78 (🟢+1.35%)

📈 Market Overview
Advancing: 3920 | Declining: 1349 | Limit Up: 155 | Limit Down: 3

🔥 Sector Performance
Leading: Internet Services, Culture & Media, Minor Metals
Laggards: Insurance, Aviation & Airports, PV Equipment
```

## ⚙️ Configuration Instructions

For full environment variables, model channels, notification channels, datasource priorities, trading disciplines, fundamental P0 semantics, and deployment instructions, refer to the [Full Configuration Guide](docs/full-guide.md).

## 🖥️ Web Interface

The Web workspace provides config management, task monitoring, manual analysis, historical reports, full Markdown reports, Agent stock querying, backtesting, holdings management, smart imports, and light/dark themes. Start methods:

```bash
python main.py --webui
python main.py --webui-only
```

Access `http://127.0.0.1:8000` to use it. For authentication, smart imports, search autocomplete, history report copying, and cloud server access details, see the [Local WebUI Management Interface](docs/full-guide.md#本地-webui-管理界面).

## 🤖 Agent Strategy Stock Query

After configuring any available AI API Key, you can use strategy stock querying on the Web `/chat` page. If you want to disable it explicitly, set `AGENT_MODE=false`.

- Supports built-in strategies like Moving Average Golden Cross, Chan Theory, Elliott Wave, Bullish Trend, Hot Themes, Event-Driven, Growth Quality, Expectation Repricing, etc.
- Supports real-time quotes, K-lines, technical indicators, news, and risk information invocation.
- Supports multi-round follow-up questions, session export, push to notification channels, and background execution.
- Supports custom strategy files and multi-agent orchestration (experimental).

> For specific Agent parameters, `skill` naming compatibility, multi-agent modes, and budget guardrails, see the [Full Guide](docs/full-guide.md#本地-webui-管理界面) and [LLM Configuration Guide](docs/LLM_CONFIG_GUIDE.md).

## 🧩 Related Projects

> DSA focuses on daily analysis reports. The following two projects cover stock picking, strategy verification, and strategy evolution, suitable for extended use. They are currently maintained independently, and we will prioritize exploring linkages with DSA for candidate stock importing, backtest verification, and report integration.

| Project | Positioning |
|------|------|
| [AlphaSift](https://github.com/ZhuLinsen/alphasift) | Multi-factor stock picking and market-wide scanning to extract candidate targets from the stock pool. |
| [AlphaEvo](https://github.com/ZhuLinsen/alphaevo) | Strategy backtesting and self-evolution, used to verify strategy rules and iteratively explore strategy parameters and combinations. |

## 📬 Contact & Cooperation

<table>
  <tr>
    <td width="92" valign="top"><strong>Cooperation Email</strong></td>
    <td valign="top">
      <a href="mailto:zhuls345@gmail.com">zhuls345@gmail.com</a><br>
      Project consultation, deployment support, and feature extension
    </td>
    <td align="center" rowspan="3" valign="middle" width="148">
      <a href="http://xhslink.com/m/tU520DWCKT" target="_blank"><img src="./docs/assets/xiaohongshu_tick.jpg" width="112" alt="Xiaohongshu QR Code"></a><br>
      <sub>Scan to follow Xiaohongshu</sub>
    </td>
  </tr>
  <tr>
    <td width="92" valign="top"><strong>Xiaohongshu</strong></td>
    <td valign="top"><a href="http://xhslink.com/m/tU520DWCKT">Welcome to follow on Xiaohongshu</a></td>
  </tr>
  <tr>
    <td width="92" valign="top"><strong>Issue Feedback</strong></td>
    <td valign="top"><a href="https://github.com/ZhuLinsen/daily_stock_analysis/issues">Submit an Issue</a></td>
  </tr>
</table>

## 📄 License

[MIT License](LICENSE) © 2026 ZhuLinsen

When customizing or citing, please indicate the source of this repository. Thank you for supporting the continuous maintenance of the project.

## ⚠️ Disclaimer

This project is for learning and research purposes only and does not constitute any investment advice. The stock market is risky, and investment requires caution. The author is not responsible for any losses incurred by using this project.

---
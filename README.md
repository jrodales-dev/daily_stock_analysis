# Daily Stock Analysis - API-First Platform 🚀

Bem-vindo à nova plataforma de **Inteligência Financeira API-First**, focada em análise diária de ações, suporte a backtesting, NLP e negociação algorítmica.

## Arquitetura e Fases Concluídas
Este sistema foi modernizado de um script monolítico local para um poderoso back-end dockerizado:
1. **Fase 1 (MVP)**: FastAPI com TimescaleDB, migrando do YFinance local para PostgreSQL assíncrono.
2. **Fase 2 (Dados e NLP)**: Coleta modular (Polygon, Alpaca, YFinance) + Pipeline de Análise de Sentimento (FinBERT).
3. **Fase 3 (Sinais e Backtest)**: Motor vetorizado de indicadores técnicos (Pandas) + Backtest Engine gerenciado via filas Redis/Celery.
4. **Fase 4 (Relatórios)**: Geração de Relatórios automatizados em PDF (WeasyPrint) + Alertas Discord/Telegram.
5. **Fase 5 (Gestão e Execução)**: Conector de corretora (Alpaca Broker), Gestão de Portfólio, Sizing de Risco e Disparo de Ordens.

---

## 🛠 Como Rodar (Setup)

### 1. Requisitos
- Docker Desktop
- Docker Compose

### 2. Variáveis de Ambiente
Crie um arquivo `.env` na raiz baseado no `.env.example`:
```env
# Database & Redis
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=dsa_db
REDIS_URL=redis://redis:6379/0

# Data APIs (Opcional - YFinance fallback automático)
POLYGON_API_KEY=sua_chave
FMP_API_KEY=sua_chave

# Execução (Broker)
ALPACA_API_KEY=sua_chave
ALPACA_SECRET_KEY=sua_chave

# Alertas
TELEGRAM_BOT_TOKEN=token
TELEGRAM_CHAT_ID=id
DISCORD_WEBHOOK_URL=url
```

### 3. Iniciar o Servidor
Para rodar toda a stack (API, Banco de Dados, Redis e Worker do Celery), execute:
```powershell
docker-compose up -d --build
```

O servidor da API estará disponível em: `http://localhost:8000/docs` (Swagger UI).

---

## 📡 Principais Endpoints da API

- **Mercado**
  - `GET /api/v1/market/ohlcv/{ticker}` - Histórico de preços.
- **Sinais e Inteligência**
  - `POST /api/v1/signals/generate` - Cruza MACD/RSI/SMA com sentimento FinBERT.
- **Backtesting (Assíncrono)**
  - `POST /api/v1/backtest/run` - Roda análise vetorial do passado e retorna um `task_id`.
  - `GET /api/v1/backtest/status/{task_id}` - Pega os resultados de Sharper Ratio, Win Rate, Max Drawdown.
- **Relatórios**
  - `POST /api/v1/reports/generate_daily` - Cria um PDF detalhado com análise técnica e notícias e dispara no Telegram.
- **Portfólio e Execução**
  - `GET /api/v1/portfolio/account` - Saldo e poder de compra na corretora.
  - `POST /api/v1/portfolio/order` - Envia ordens baseadas no risco e na volatilidade (ATR).

---
## Automação
Com as fundações prontas, você pode conectar sua UI Web em React ou usar o Celery Beat para agendar chamadas ao `/reports/generate_daily` e ao `/portfolio/order`.
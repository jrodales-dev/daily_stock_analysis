# Mapeamento de Telas do Sistema (Daily Stock Analysis)

Este diretório contém os screenshots das páginas do sistema, capturados diretamente da aplicação web em execução (`http://127.0.0.1:8000`). O objetivo deste mapeamento é alimentar a IA de design (Google Stitch) para facilitar a análise visual, redesign e elaboração de melhorias de interface.

---

## Índice de Páginas Mapeadas

| # | Nome da Tela | Rota | Arquivo de Screenshot | Descrição Geral |
|---|---|---|---|---|
| 1 | **Dashboard Principal** | `/` | [home_page.png](home_page.png) | Painel principal contendo o histórico de análises, principais insights da última ação selecionada, índice de Medo e Ganância (Sentimento de Mercado), pontos de estratégia e visualização rápida. |
| 2 | **Chat com IA** | `/chat` | [chat_page.png](chat_page.png) | Interface de diálogo interativo (Chatbot) com assistente de IA focado em análise de ativos, permitindo escolher estratégias específicas para a conversa e gerenciar históricos de sessões. |
| 3 | **Triagem de Ações** | `/screening` | [screening_page.png](screening_page.png) | Módulo integrado com o motor AlphaSift para filtrar ações candidatas de acordo com parâmetros e estratégias (Multifator, Impulso, Dupla Baixa, etc.). |
| 4 | **Portfólio & Risco** | `/portfolio` | [portfolio_page.png](portfolio_page.png) | Painel de controle de posições financeiras, importação de arquivos CSV de corretoras, lançamentos manuais, monitoramento de Drawdown e concentração de ativos. |
| 5 | **Backtest de Estratégias** | `/backtest` | [backtest_page.png](backtest_page.png) | Mecanismo de simulação histórica para verificar o nível de precisão das recomendações geradas pela IA em relação aos fechamentos reais de mercado. |
| 6 | **Centro de Alertas** | `/alerts` | [alerts_page.png](alerts_page.png) | Criação e gestão de regras de notificação (cruzamento de médias móveis, limites de RSI/MACD, limites de preço) e logs de tentativas de disparo. |
| 7 | **Configurações Gerais** | `/settings` | [settings_page.png](settings_page.png) | Painel centralizado para gerenciar provedores e modelos de LLM, chaves de API, agendamentos, importações inteligentes de imagens e outras variáveis do sistema. |
| 7.1 | Configurações Básicas | `/settings` (cat: 1) | [settings_basic.png](settings_basic.png) | Configuração de watchlist (`STOCK_LIST`) e importações inteligentes de imagens/tabelas da área de transferência. |
| 7.2 | Modelos de IA | `/settings` (cat: 2) | [settings_ai_models.png](settings_ai_models.png) | Gerenciamento de provedores de LLM (AIHubmix, DeepSeek, Gemini, OpenAI, etc.), keys sensíveis e temperature. |
| 7.3 | Fontes de Dados | `/settings` (cat: 3) | [settings_data_sources.png](settings_data_sources.png) | Prioridades e tokens de provedores de dados de mercado (Tushare, efinance, Akshare) e APIs de sentimentos. |
| 7.4 | Canais de Notificação | `/settings` (cat: 4) | [settings_notifications.png](settings_notifications.png) | Configurações e chaves de envio para Telegram, Discord, Slack, E-mail, WeChat e webhooks. |
| 7.5 | Configurações do Sistema | `/settings` (cat: 5) | [settings_system.png](settings_system.png) | Agendamentos, portas do servidor webui, log level e configurações de banco de dados SQLite. |
| 7.6 | Configurações do Agente | `/settings` (cat: 6) | [settings_agent.png](settings_agent.png) | Modo ReAct do Agente de Risco, orquestração de multi-agentes e compressão de contexto para economia de tokens. |
| 7.7 | Configurações de Backtest | `/settings` (cat: 7) | [settings_backtest.png](settings_backtest.png) | Ajuste da janela de validação de trading e idade mínima dos históricos para o simulador. |
| 8 | **Página não Encontrada (404)** | `/not-found` | [not_found_page.png](not_found_page.png) | Estado de erro amigável exibido para rotas inexistentes com botão de retorno fácil ao painel principal. |

---

## Estrutura Visual Comum (Design Tokens)

* **Layout Base**: Grid fluído com uma barra lateral de navegação fixa à esquerda (`w-[190px]`) e área de conteúdo flexível à direita.
* **Tema**: Dark Mode predominante (azul-escuro profundo de fundo `#0b1326`) com painéis e cards de bordas levemente arredondadas e translúcidas (efeito de vidro com blur).
* **Tipografia**: Utiliza `Inter` como fonte padrão, mantendo alta legibilidade em telas densas de informações financeiras.
* **Componentes Chave**:
  - `SidebarNav`: Barra lateral esquerda com logos e ícones unificados.
  - `DashboardStateBlock`: Cards informativos dinâmicos com contornos e sombras brilhantes coloridas com base em sentimentos de mercado.
  - `ConfirmDialog` / `Drawer`: Modais e painéis deslizantes limpos e focados no conteúdo.

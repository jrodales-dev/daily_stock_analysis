import type { ReportLanguage } from '../types/analysis';

export const normalizeReportLanguage = (value?: string | null): ReportLanguage => {
  if (value === 'en') return 'en';
  if (value === 'pt') return 'zh'; // UI strings use 'zh' key which already has PT translations
  return 'zh';
};

/** Maps Chinese/English operation advice values to Portuguese display text. */
const OPERATION_ADVICE_MAP: Record<string, string> = {
  // Chinese
  '强烈买入': 'Forte Compra',
  '买入': 'Comprar',
  '加仓': 'Comprar',
  '持有': 'Manter',
  '洗盘观察': 'Manter',
  '观察': 'Observar',
  '观望': 'Observar',
  '减仓': 'Reduzir',
  '卖出': 'Vender',
  '强烈卖出': 'Forte Venda',
  // English
  'strong buy': 'Forte Compra',
  'buy': 'Comprar',
  'accumulate': 'Comprar',
  'hold': 'Manter',
  'watch': 'Observar',
  'wait': 'Observar',
  'reduce': 'Reduzir',
  'sell': 'Vender',
  'strong sell': 'Forte Venda',
};

/** Maps Chinese/English trend prediction values to Portuguese display text. */
const TREND_PREDICTION_MAP: Record<string, string> = {
  // Chinese
  '强烈看多': 'Forte Alta',
  '看多': 'Alta',
  '多头排列': 'Alta',
  '盘整': 'Lateral',
  '震荡': 'Lateral',
  '看空': 'Baixa',
  '空头排列': 'Baixa',
  '强烈看空': 'Forte Baixa',
  '强势多头': 'Forte Alta',
  '弱势多头': 'Alta',
  '强势空头': 'Forte Baixa',
  '弱势空头': 'Baixa',
  // English
  'strong bullish': 'Forte Alta',
  'bullish': 'Alta',
  'uptrend': 'Alta',
  'sideways': 'Lateral',
  'neutral': 'Lateral',
  'range-bound': 'Lateral',
  'bearish': 'Baixa',
  'downtrend': 'Baixa',
  'strong bearish': 'Forte Baixa',
};

/**
 * Translate an operationAdvice value (potentially Chinese/English) to Portuguese.
 * Falls back to the raw value if no mapping is found.
 */
export const localizeOperationAdvice = (value?: string | null): string => {
  if (!value) return '';
  const trimmed = value.trim();
  // Try exact match first
  const exact = OPERATION_ADVICE_MAP[trimmed] || OPERATION_ADVICE_MAP[trimmed.toLowerCase()];
  if (exact) return exact;
  // Try matching the first segment (e.g. "卖出/观望" → match "卖出")
  for (const sep of ['/', '|', ',', '，', '、']) {
    if (trimmed.includes(sep)) {
      const first = trimmed.split(sep)[0].trim();
      const mapped = OPERATION_ADVICE_MAP[first] || OPERATION_ADVICE_MAP[first.toLowerCase()];
      if (mapped) return mapped;
    }
  }
  return trimmed;
};

/**
 * Translate a trendPrediction value (potentially Chinese/English) to Portuguese.
 * Falls back to the raw value if no mapping is found.
 */
export const localizeTrendPrediction = (value?: string | null): string => {
  if (!value) return '';
  const trimmed = value.trim();
  const exact = TREND_PREDICTION_MAP[trimmed] || TREND_PREDICTION_MAP[trimmed.toLowerCase()];
  if (exact) return exact;
  for (const sep of ['/', '|', ',', '，', '、']) {
    if (trimmed.includes(sep)) {
      const first = trimmed.split(sep)[0].trim();
      const mapped = TREND_PREDICTION_MAP[first] || TREND_PREDICTION_MAP[first.toLowerCase()];
      if (mapped) return mapped;
    }
  }
  return trimmed;
};

const REPORT_TEXT = {
  zh: {
    keyInsights: 'PRINCIPAIS INSIGHTS',
    noAnalysisSummary: 'Sem conclusão de análise',
    actionAdvice: 'Recomendação',
    noAdvice: 'Sem recomendação',
    trendPrediction: 'Tendência Prevista',
    noPrediction: 'Sem previsão',
    marketSentiment: 'Sentimento de Mercado',
    strategyPoints: 'PONTOS DE ESTRATÉGIA',
    sniperLevels: 'Níveis de Ação',
    idealBuy: 'Entrada Ideal',
    secondaryBuy: 'Entrada Secundária',
    stopLoss: 'Stop Loss',
    takeProfit: 'Take Profit',
    noValue: '—',
    newsFeed: 'NOTÍCIAS',
    relatedNews: 'Notícias Relacionadas',
    refresh: 'Atualizar',
    retry: 'Tentar Novamente',
    dismiss: 'Fechar',
    details: 'Ver Detalhes',
    loadingNews: 'Carregando notícias...',
    noNews: 'Sem notícias relacionadas',
    noNewsDescription: 'Atualize mais tarde para verificar as últimas novidades.',
    openLink: 'Abrir',
    transparency: 'TRANSPARÊNCIA',
    traceability: 'Rastreabilidade de Dados',
    rawResult: 'Resultado Bruto da Análise',
    analysisSnapshot: 'Snapshot da Análise',
    copy: 'Copiar',
    copied: 'Copiado!',
    recordId: 'ID do Registro',
    fullReport: 'Relatório Completo',
    loadingReport: 'Carregando relatório...',
    loadReportFailed: 'Falha ao carregar relatório',
    copyMarkdownSource: 'Copiar Markdown',
    copyPlainText: 'Copiar Texto',
    analysisModel: 'Modelo',
    fearGreedIndex: 'Índice Medo & Ganância',
    boardLinkage: 'SETOR',
    relatedBoards: 'Setores Relacionados',
    leadingBoard: 'Liderando',
    laggingBoard: 'Atrasado',
    neutralBoard: 'Neutro',
    reanalyze: 'Reanalisar',
  },
  en: {
    keyInsights: 'KEY INSIGHTS',
    noAnalysisSummary: 'No analysis summary yet',
    actionAdvice: 'Action Advice',
    noAdvice: 'No advice yet',
    trendPrediction: 'Trend Outlook',
    noPrediction: 'No forecast yet',
    marketSentiment: 'Market Sentiment',
    strategyPoints: 'STRATEGY POINTS',
    sniperLevels: 'Action Levels',
    idealBuy: 'Ideal Entry',
    secondaryBuy: 'Secondary Entry',
    stopLoss: 'Stop Loss',
    takeProfit: 'Take Profit',
    noValue: '—',
    newsFeed: 'NEWS FEED',
    relatedNews: 'Related News',
    refresh: 'Refresh',
    retry: 'Retry',
    dismiss: 'Close',
    details: 'View details',
    loadingNews: 'Loading news...',
    noNews: 'No related news',
    noNewsDescription: 'Refresh later to check for the latest updates.',
    openLink: 'Open',
    transparency: 'TRANSPARENCY',
    traceability: 'Data Traceability',
    rawResult: 'Raw Analysis Result',
    analysisSnapshot: 'Analysis Snapshot',
    copy: 'Copy',
    copied: 'Copied!',
    recordId: 'Record ID',
    fullReport: 'Full Analysis Report',
    loadingReport: 'Loading report...',
    loadReportFailed: 'Failed to load report',
    copyMarkdownSource: 'Copy Markdown Source',
    copyPlainText: 'Copy Plain Text',
    analysisModel: 'Model',
    fearGreedIndex: 'Fear & Greed Index',
    boardLinkage: 'BOARD LINKAGE',
    relatedBoards: 'Related Boards',
    leadingBoard: 'Leading',
    laggingBoard: 'Lagging',
    neutralBoard: 'Neutral',
    reanalyze: 'Reanalyze',
  },
} as const;

export const getReportText = (language?: string | null) => REPORT_TEXT[normalizeReportLanguage(language)];


import React, { useEffect, useState } from 'react';
import type {
  ReportDetails as ReportDetailsType,
  ReportMeta,
  ReportSummary as ReportSummaryType,
} from '../../types/analysis';
import { Badge, Card, ScoreGauge } from '../common';
import { formatDateTime } from '../../utils/format';
import { translateSector } from '../../utils/sectorTranslations';
import { getReportText, normalizeReportLanguage, localizeOperationAdvice, localizeTrendPrediction } from '../../utils/reportLanguage';
import { stocksApi, type StockQuote } from '../../api/stocks';

interface ReportOverviewProps {
  meta: ReportMeta;
  summary: ReportSummaryType;
  details?: ReportDetailsType;
  isHistory?: boolean;
}

type BoardStatus = 'leading' | 'lagging';

type BoardSignal = {
  status: BoardStatus;
  changePct?: number;
};

const normalizeBoardName = (value?: string): string => translateSector(value || '');

const coerceFiniteNumber = (value: unknown): number | undefined => {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : undefined;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim().replace(/%$/, '');
    if (!trimmed) {
      return undefined;
    }
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
};

const buildBoardSignalMap = (details?: ReportDetailsType): Map<string, BoardSignal> => {
  const signalMap = new Map<string, BoardSignal>();
  const topBoards = Array.isArray(details?.sectorRankings?.top) ? details.sectorRankings.top : [];
  const bottomBoards = Array.isArray(details?.sectorRankings?.bottom) ? details.sectorRankings.bottom : [];

  topBoards.forEach((item) => {
    const normalizedName = normalizeBoardName(item?.name);
    if (!normalizedName) {
      return;
    }
    signalMap.set(normalizedName, {
      status: 'leading',
      changePct: coerceFiniteNumber(item.changePct),
    });
  });

  bottomBoards.forEach((item) => {
    const normalizedName = normalizeBoardName(item?.name);
    if (!normalizedName) {
      return;
    }
    signalMap.set(normalizedName, {
      status: 'lagging',
      changePct: coerceFiniteNumber(item.changePct),
    });
  });

  return signalMap;
};

/**
 * Componente de Visão Geral
 */
export const ReportOverview: React.FC<ReportOverviewProps> = ({
  meta,
  summary,
  details,
}) => {
  const reportLanguage = normalizeReportLanguage(meta.reportLanguage);
  const text = getReportText(reportLanguage);
  const relatedBoards = (Array.isArray(details?.belongBoards) ? details.belongBoards : [])
    .filter((board) => normalizeBoardName(board?.name).length > 0);
  const boardSignals = buildBoardSignalMap(details);

  const [realtimeQuote, setRealtimeQuote] = useState<StockQuote | null>(null);
  const [isLive, setIsLive] = useState(false);

  useEffect(() => {
    if (!meta.stockCode) return;

    let mounted = true;
    
    const fetchQuote = async () => {
      try {
        const quote = await stocksApi.getQuote(meta.stockCode!);
        if (mounted) {
          setRealtimeQuote(quote);
          setIsLive(true);
        }
      } catch (err) {
        console.error('Failed to fetch real-time quote:', err);
        if (mounted) {
          setIsLive(false);
        }
      }
    };

    void fetchQuote();
    const intervalId = setInterval(fetchQuote, 15000);

    return () => {
      mounted = false;
      clearInterval(intervalId);
    };
  }, [meta.stockCode]);

  const displayPrice = realtimeQuote?.currentPrice ?? meta.currentPrice;
  const displayChangePct = realtimeQuote?.changePercent ?? meta.changePct;

  const getPriceChangeStyle = (changePct: number | undefined): React.CSSProperties | undefined => {
    if (changePct === undefined || changePct === null) {
      return undefined;
    }

    if (changePct > 0) {
      return { color: 'var(--home-price-up)' };
    }

    if (changePct < 0) {
      return { color: 'var(--home-price-down)' };
    }

    return undefined;
  };

  const formatChangePct = (changePct: number | undefined): string => {
    if (changePct === undefined || changePct === null) return '--';
    const sign = changePct > 0 ? '+' : '';
    return `${sign}${changePct.toFixed(2)}%`;
  };

  const getBoardStatusLabel = (status: BoardStatus): string => {
    if (status === 'leading') {
      return text.leadingBoard;
    }
    return text.laggingBoard;
  };

  const getBoardStatusVariant = (status: BoardStatus): 'success' | 'danger' => {
    if (status === 'leading') {
      return 'success';
    }
    return 'danger';
  };

  return (
    <div className="space-y-5">
      {/* Cabeçalho da ação e conclusão */}
      <Card variant="gradient" padding="md" className="home-report-hero w-full">
        <div className="flex items-start justify-between mb-5">
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h2 className="text-[28px] font-bold leading-tight text-foreground">
                {meta.stockName || meta.stockCode}
              </h2>
            </div>
            <div className="flex items-center gap-2 mt-1.5">
              <span className="home-accent-chip px-2 py-0.5 font-mono text-xs">
                {meta.stockCode}
              </span>
              <span className="text-xs text-muted-text flex items-center gap-1">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                {formatDateTime(meta.createdAt)}
              </span>
            </div>
          </div>

          {/* Preço e Variação */}
          {displayPrice != null && (
            <div className="flex flex-col items-end justify-start text-right pl-4">
              <span className="text-2xl font-bold font-mono" style={getPriceChangeStyle(displayChangePct)}>
                {displayPrice.toFixed(2)}
              </span>
              <div className="flex items-center gap-2 mt-0.5">
                {isLive && (
                  <span className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-full bg-success/10 border border-success/20">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-success"></span>
                    </span>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-success">Ao vivo</span>
                  </span>
                )}
                <span className="text-sm font-semibold font-mono" style={getPriceChangeStyle(displayChangePct)}>
                  {formatChangePct(displayChangePct)}
                </span>
              </div>
              {realtimeQuote?.source && (
                <div className="mt-1 text-[10px] text-muted-text uppercase tracking-wider">
                  Fonte: {realtimeQuote.source}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Conclusão Principal */}
        <div className="home-divider border-t pt-5">
          <span className="label-uppercase">{text.keyInsights}</span>
          <p className="mt-2 max-w-none whitespace-pre-wrap text-left text-[15px] leading-7 text-foreground">
            {summary.analysisSummary || text.noAnalysisSummary}
          </p>
        </div>
      </Card>

      {/* Indicadores e emoções / Associação (Empilhados horizontalmente) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 items-stretch">
        {/* Sentimento do Mercado */}
        <Card variant="bordered" padding="md" className="home-panel-card home-rail-card !overflow-visible flex flex-col justify-center">
          <div className="text-center">
              <h3 className="mb-5 text-sm font-medium tracking-wide text-foreground">{text.marketSentiment}</h3>
              <ScoreGauge score={summary.sentimentScore} size="lg" language={reportLanguage} />
            </div>
          </Card>

          <div className="flex flex-col gap-4 justify-center h-full">
            {/* Recomendação */}
            <Card
              variant="bordered"
              padding="sm"
              hoverable
              className="home-panel-card home-insight-card flex-1 flex flex-col"
              style={{ ['--home-insight-tone' as string]: 'var(--home-strategy-buy)' }}
            >
              <div className="flex flex-col h-full flex-1">
                <div className="flex items-center gap-2">
                  <div className="home-insight-icon w-8 h-8 rounded-lg bg-success/10 flex items-center justify-center flex-shrink-0">
                    <svg className="w-4 h-4 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                    </svg>
                  </div>
                  <h4 className="home-insight-title text-[11px] font-medium uppercase tracking-[0.16em]">{text.actionAdvice}</h4>
                </div>
                <div className="flex-1 flex items-center">
                  <p className="home-insight-body text-2xl font-bold leading-tight text-foreground pl-10">
                    {localizeOperationAdvice(summary.operationAdvice) || text.noAdvice}
                  </p>
                </div>
              </div>
            </Card>

            {/* Tendência Prevista */}
            <Card
              variant="bordered"
              padding="sm"
              hoverable
              className="home-panel-card home-insight-card flex-1 flex flex-col"
              style={{ ['--home-insight-tone' as string]: 'var(--home-strategy-take)' }}
            >
              <div className="flex flex-col h-full flex-1">
                <div className="flex items-center gap-2">
                  <div className="home-insight-icon w-8 h-8 rounded-lg bg-warning/10 flex items-center justify-center flex-shrink-0">
                    <svg className="w-4 h-4 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                    </svg>
                  </div>
                  <h4 className="home-insight-title text-[11px] font-medium uppercase tracking-[0.16em]">{text.trendPrediction}</h4>
                </div>
                <div className="flex-1 flex items-center">
                  <p className="home-insight-body text-2xl font-bold leading-tight text-foreground pl-10">
                    {localizeTrendPrediction(summary.trendPrediction) || text.noPrediction}
                  </p>
                </div>
              </div>
            </Card>
          </div>

          <div className="flex flex-col gap-4 justify-center h-full">
            {/* Setores Relacionados */}
            {relatedBoards.length > 0 && (
              <Card
                variant="bordered"
                padding="sm"
                hoverable
                className="home-panel-card home-insight-card text-left flex-1 flex flex-col justify-center"
                style={{ ['--home-insight-tone' as string]: 'hsl(var(--primary))' }}
              >
                <section aria-label={text.relatedBoards} className="flex items-start gap-3">
                  <div className="home-insight-icon w-8 h-8 rounded-lg bg-cyan/10 flex items-center justify-center flex-shrink-0">
                    <svg className="w-4 h-4 text-cyan" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                    </svg>
                  </div>
                  <div className="space-y-1.5 min-w-0 w-full">
                    <h4 className="home-insight-title text-[11px] font-medium uppercase tracking-[0.16em] text-cyan">{text.relatedBoards}</h4>
                    <div className="home-related-board-list flex flex-col gap-2.5 pt-1 pb-1 max-h-[140px] overflow-y-auto pr-2 custom-scrollbar">
                    {relatedBoards.map((board, index) => {
                      const boardName = normalizeBoardName(board.name);
                      const signal = boardSignals.get(boardName);
                      return (
                        <div
                          key={`${boardName}-${board.code || index}`}
                          className="flex flex-wrap items-center gap-1.5 text-sm"
                        >
                          <span className="home-accent-chip px-2 py-0.5 text-xs font-medium">
                            {boardName}
                          </span>

                          {signal && (
                            <Badge
                              variant={getBoardStatusVariant(signal.status)}
                              className="home-board-status-badge shadow-none"
                            >
                              {getBoardStatusLabel(signal.status)}
                            </Badge>
                          )}
                          {signal && signal.changePct !== undefined && signal.changePct !== null && (
                            <span
                              className="text-xs font-mono"
                              style={getPriceChangeStyle(signal.changePct)}
                            >
                              {formatChangePct(signal.changePct)}
                            </span>
                          )}
                        </div>
                      );
                    })}
                    </div>
                  </div>
                </section>
              </Card>
            )}

            {/* Indicadores Chave */}
            <Card
              variant="bordered"
              padding="sm"
              hoverable
              className="home-panel-card home-insight-card text-left flex-1 flex flex-col justify-center"
              style={{ ['--home-insight-tone' as string]: '#a855f7' }}
            >
              <section aria-label="Indicadores Chave" className="flex items-start gap-3">
                <div className="home-insight-icon w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: 'rgba(168, 85, 247, 0.1)' }}>
                  <svg className="w-4 h-4" style={{ color: '#a855f7' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
                <div className="space-y-1.5 min-w-0 w-full">
                  <h4 className="home-insight-title text-[11px] font-medium uppercase tracking-[0.16em] text-purple">Indicadores Chave</h4>
                  <div className="grid grid-cols-2 gap-2 pt-1 pb-1">
                    <div className="flex flex-col">
                      <span className="text-[10px] text-muted-text uppercase">Abertura</span>
                      <span className="text-xs font-mono">{realtimeQuote?.open?.toFixed(2) ?? '--'}</span>
                    </div>
                    <div className="flex flex-col">
                      <span className="text-[10px] text-muted-text uppercase">Alta</span>
                      <span className="text-xs font-mono">{realtimeQuote?.high?.toFixed(2) ?? '--'}</span>
                    </div>
                    <div className="flex flex-col">
                      <span className="text-[10px] text-muted-text uppercase">Baixa</span>
                      <span className="text-xs font-mono">{realtimeQuote?.low?.toFixed(2) ?? '--'}</span>
                    </div>
                    <div className="flex flex-col">
                      <span className="text-[10px] text-muted-text uppercase">Volume</span>
                      <span className="text-xs font-mono">
                        {realtimeQuote?.volume ? (realtimeQuote.volume / 1000000).toFixed(2) + 'M' : '--'}
                      </span>
                    </div>
                  </div>
                </div>
              </section>
            </Card>
          </div>
      </div>
    </div>
  );
};

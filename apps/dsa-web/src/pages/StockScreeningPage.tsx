import type React from 'react';
import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, CircleAlert, Play, Search, SlidersHorizontal } from 'lucide-react';
import {
  alphasiftApi,
  type AlphaSiftCandidate,
  type AlphaSiftScreenResponse,
  type AlphaSiftStrategy,
} from '../api/alphasift';
import { AppPage, Button, InlineAlert } from '../components/common';
import { MarketScreenerTab } from '../components/dashboard/MarketScreenerTab';
const MARKETS = [{ id: 'cn', label: 'Ações A' }];

/** Translates AlphaSift strategy names/descriptions/categories from Chinese to Portuguese. */
const STRATEGY_I18N: Record<string, { name?: string; description?: string; category?: string }> = {
  balanced_multi_factor: {
    name: 'Multifator Equilibrado',
    description: 'Estratégia universal de seleção integrando avaliação, capital, momentum e estabilidade',
    category: 'framework',
  },
  balanced_alpha: {
    name: 'Multifator Equilibrado',
    description: 'Estratégia universal de seleção integrando avaliação, capital, momentum e estabilidade',
    category: 'framework',
  },
  capital_heat: {
    name: 'Impulso de Capital',
    description: 'Seleção de curto prazo com capital ativo e volume-preço sincronizados, sem superaquecimento',
    category: 'momentum',
  },
  dual_low: {
    name: 'Dupla Baixa',
    description: 'Seleção de valor conservadora focada em baixa avaliação',
    category: 'valor',
  },
  trend_quality: {
    name: 'Qualidade da Tendência',
    description: 'Seleção de médio prazo combinando confirmação de tendência e qualidade fundamental',
    category: 'framework',
  },
  momentum_quality: {
    name: 'Qualidade da Tendência',
    description: 'Seleção de médio prazo combinando confirmação de tendência e qualidade fundamental',
    category: 'framework',
  },
  oversold_reversal: {
    name: 'Reversão de Sobrevenda',
    description: 'Seleção de reversão com queda controlada, liquidez preservada e valor de recuperação',
    category: 'reversão',
  },
  stable_value: {
    name: 'Valor Estável',
    description: 'Seleção estável com avaliação razoável, liquidez e volatilidade controlada',
    category: 'valor',
  },
  quality_value: {
    name: 'Valor Estável',
    description: 'Seleção estável com avaliação razoável, liquidez e volatilidade controlada',
    category: 'valor',
  },
  volume_shrink_pullback: {
    name: 'Recuo com Volume Reduzido',
    description: 'Oportunidade de entrada com recuo em volume reduzido e suporte de média móvel em tendência de alta',
    category: 'tendência',
  },
  shrink_pullback: {
    name: 'Recuo com Volume Reduzido',
    description: 'Oportunidade de entrada com recuo em volume reduzido e suporte de média móvel em tendência de alta',
    category: 'tendência',
  },
  volume_breakout: {
    name: 'Rompimento com Volume',
    description: 'Sinal de início de tendência com volume rompendo resistência chave',
    category: 'tendência',
  },
};

/** Translate a single strategy field using the i18n dictionary. */
const localizeStrategy = (item: { id: string; name?: string; title?: string; description?: string; category?: string; tag?: string; tags?: string[] }) => {
  const i18n = STRATEGY_I18N[item.id];
  return {
    name: i18n?.name || item.name || item.title || item.id,
    description: i18n?.description || item.description || item.id,
    category: i18n?.category || item.category || item.tag || item.tags?.[0] || item.id,
  };
};

const formatScore = (score: AlphaSiftCandidate['score']) => {
  if (score == null || Number.isNaN(Number(score))) {
    return '-';
  }
  return Number(score).toFixed(2);
};

const formatNumber = (value: unknown, digits = 2) => {
  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return '-';
  }
  return Number(value).toFixed(digits);
};

const formatAmount = (value: unknown) => {
  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return '-';
  }
  const amount = Number(value);
  if (Math.abs(amount) >= 1_000_000_000) {
    return `${(amount / 1_000_000_000).toFixed(2)}B`;
  }
  if (Math.abs(amount) >= 1_000_000) {
    return `${(amount / 1_000_000).toFixed(2)}M`;
  }
  if (Math.abs(amount) >= 1_000) {
    return `${(amount / 1_000).toFixed(2)}K`;
  }
  return amount.toFixed(2);
};

const formatPercent = (value: unknown) => {
  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return '-';
  }
  return `${(Number(value) * 100).toFixed(0)}%`;
};

const getCandidateReason = (item: AlphaSiftCandidate) => {
  if (item.reason) {
    return item.reason;
  }
  const summaries = item.postAnalysisSummaries || {};
  const summary = Object.values(summaries).find((value) => typeof value === 'string' && value.trim());
  if (typeof summary === 'string') {
    return summary;
  }
  return 'AlphaSift returned candidate, but provided no text summary. Please check the factors, risks, and raw fields below.';
};

const getSignal = (item: AlphaSiftCandidate) => {
  const rawSignal = item.raw.action ?? item.raw.signal ?? item.raw.recommendation;
  return typeof rawSignal === 'string' && rawSignal.trim() ? rawSignal : 'Observe';
};

const getFactorEntries = (item: AlphaSiftCandidate) =>
  Object.entries(item.factorScores || {})
    .filter(([, value]) => typeof value === 'number')
    .sort((a, b) => Number(b[1]) - Number(a[1]))
    .slice(0, 6);

const StockScreeningPage: React.FC = () => {
  const [enabled, setEnabled] = useState(false);
  const [market, setMarket] = useState('cn');
  const [strategy, setStrategy] = useState('dual_low');
  const [strategies, setStrategies] = useState<AlphaSiftStrategy[]>([]);
  const [maxResults, setMaxResults] = useState(3);
  const [candidates, setCandidates] = useState<AlphaSiftCandidate[]>([]);
  const [screenMeta, setScreenMeta] = useState<AlphaSiftScreenResponse | null>(null);
  const [expandedCode, setExpandedCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [enabling, setEnabling] = useState(false);
  const [loadingStrategies, setLoadingStrategies] = useState(false);
  const [error, setError] = useState('');
  const [strategyLoadError, setStrategyLoadError] = useState('');

  const selectedStrategy = useMemo(() => strategies.find((item) => item.id === strategy), [strategies, strategy]);
  const localizedStrategy = selectedStrategy ? localizeStrategy(selectedStrategy) : null;
  const selectedStrategyTitle = localizedStrategy?.name || 'Estratégia Personalizada';
  const selectedStrategyTag = localizedStrategy?.category || 'Personalizada';
  const displayedStrategy = selectedStrategy ? selectedStrategyTitle : `Estratégia Personalizada (${strategy})`;

  const clearScreeningResults = () => {
    setCandidates([]);
    setScreenMeta(null);
    setExpandedCode(null);
  };

  const loadStrategies = useCallback(async () => {
    setLoadingStrategies(true);
    try {
      setStrategyLoadError('');
      const result = await alphasiftApi.getStrategies();
      const loadedStrategies = result.strategies || [];
      setStrategies(loadedStrategies);
      if (loadedStrategies.length > 0) {
        setStrategy((currentStrategy) =>
          loadedStrategies.some((item) => item.id === currentStrategy) ? currentStrategy : loadedStrategies[0].id,
        );
      }
    } catch (err) {
      setStrategies([]);
      setStrategyLoadError(err instanceof Error ? err.message : 'Falha ao carregar lista de estratégias AlphaSift');
    } finally {
      setLoadingStrategies(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    alphasiftApi
      .getStatus()
      .then((status) => {
        if (!active) {
          return;
        }
        setEnabled(status.enabled);
        if (status.enabled) {
          void loadStrategies();
        }
      })
      .catch(() => {
        if (active) {
          setEnabled(false);
        }
      });
    return () => {
      active = false;
    };
  }, [loadStrategies]);

  const handleEnable = async () => {
    setEnabling(true);
    setError('');
    try {
      await alphasiftApi.enable();
      setEnabled(true);
      await loadStrategies();
    } catch (err) {
      try {
        const status = await alphasiftApi.getStatus();
        setEnabled(status.enabled);
      } catch {
        setEnabled(false);
      }
      setError(err instanceof Error ? err.message : 'Falha ao ativar AlphaSift');
    } finally {
      setEnabling(false);
    }
  };

  const handleStrategyChange = (nextStrategy: string) => {
    if (nextStrategy !== strategy) {
      clearScreeningResults();
    }
    setStrategy(nextStrategy);
  };

  const handleMarketChange = (nextMarket: string) => {
    if (nextMarket !== market) {
      clearScreeningResults();
    }
    setMarket(nextMarket);
  };

  const handleMaxResultsChange = (nextMaxResults: number) => {
    if (nextMaxResults !== maxResults) {
      clearScreeningResults();
    }
    setMaxResults(nextMaxResults);
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError('');
    setScreenMeta(null);
    try {
      const result = await alphasiftApi.screen({ market, strategy, maxResults });
      setScreenMeta(result);
      setCandidates(result.candidates);
      setExpandedCode(result.candidates[0]?.code ?? null);
    } catch (err) {
      setCandidates([]);
      setError(err instanceof Error ? err.message : 'Falha na triagem de ações');
    } finally {
      setLoading(false);
    }
  };

  const [activeTab, setActiveTab] = useState<'alphasift' | 'market'>('alphasift');

  return (
    <AppPage className="max-w-6xl space-y-6 pb-12 pt-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3">
          <span className="grid h-7 w-7 place-items-center rounded-full border-2 border-cyan text-cyan shadow-[0_0_24px_hsl(var(--primary)/0.18)]">
            <Search className="h-4 w-4" />
          </span>
          <div>
            <h1 className="text-2xl font-bold tracking-normal text-foreground">Triagem de Ações</h1>
            <p className="mt-1 text-sm text-secondary-text">Busque e filtre ações do mercado com base em diferentes estratégias.</p>
          </div>
        </div>

        <div className="flex bg-[var(--surface)] p-1 rounded-xl border border-[var(--border-subtle)]">
          <button
            className={`px-4 py-1.5 text-sm font-medium rounded-lg transition-colors ${activeTab === 'alphasift' ? 'bg-[var(--primary)] text-[var(--primary-foreground)] shadow-sm' : 'text-[var(--secondary-text)] hover:text-[var(--foreground)]'}`}
            onClick={() => setActiveTab('alphasift')}
          >
            AlphaSift IA
          </button>
          <button
            className={`px-4 py-1.5 text-sm font-medium rounded-lg transition-colors ${activeTab === 'market' ? 'bg-[var(--primary)] text-[var(--primary-foreground)] shadow-sm' : 'text-[var(--secondary-text)] hover:text-[var(--foreground)]'}`}
            onClick={() => setActiveTab('market')}
          >
            Screener Técnico
          </button>
        </div>
      </div>

      {activeTab === 'alphasift' ? (
        <Fragment>

      {!enabled ? (
        <InlineAlert
          variant="info"
          title="AlphaSift Não Ativado"
          message="Clique para definir ALPHASIFT_ENABLED=true e verificar a camada adaptadora AlphaSift; pacotes de release desktop possuem dependências integradas, enquanto implantações a partir do código-fonte requerem instalação prévia no ambiente Python do backend."
          action={
            <Button size="sm" isLoading={enabling} loadingText="Ativando..." onClick={() => void handleEnable()}>
              Ativar AlphaSift
            </Button>
          }
        />
      ) : null}

      <InlineAlert
        variant="warning"
        title="Aviso de Risco"
        message="Os resultados da triagem AlphaSift são apenas para pesquisa e referência e não constituem conselho de investimento. Negociar envolve risco; todas as decisões e lucros/prejuízos são de responsabilidade exclusiva do usuário."
      />

      {error ? <InlineAlert variant="danger" title="Falha na Invocação" message={error} /> : null}

      <section className="rounded-2xl border border-cyan/35 bg-card/95 p-4 shadow-soft-card">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-foreground">Selecionar Estratégia</h2>
            <p className="mt-1 text-xs text-secondary-text">As estratégias são do AlphaSift. O DSA apenas invoca a camada adaptadora estável.</p>
          </div>
          <span className="rounded-full border border-cyan/30 bg-cyan/10 px-3 py-1 text-xs font-semibold text-cyan">
            {selectedStrategyTag}
          </span>
        </div>

        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {loadingStrategies ? (
            <div className="rounded-xl border border-dashed border-border bg-surface/70 p-4 text-sm text-secondary-text">
              Carregando estratégias disponíveis...
            </div>
          ) : strategies.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-surface/70 p-4 text-sm text-secondary-text">
              {strategyLoadError || 'Lista de estratégias AlphaSift não carregada. Você pode inserir parâmetros de estratégia manualmente abaixo.'}
            </div>
          ) : (
              strategies.map((item) => {
                const selected = item.id === strategy;
                const localized = localizeStrategy(item);
                return (
                  <button
                    key={item.id}
                    className={`min-h-28 rounded-xl border p-4 text-left transition-all ${
                      selected
                        ? 'border-cyan bg-cyan/10 shadow-[0_0_0_1px_hsl(var(--primary)/0.15),0_16px_36px_hsl(var(--primary)/0.12)]'
                        : 'border-border/80 bg-surface/70 hover:border-cyan/45 hover:bg-hover/70'
                    }`}
                    type="button"
                    onClick={() => handleStrategyChange(item.id)}
                  >
                    <span className="text-base font-semibold text-foreground">{localized.name}</span>
                    <span className="mt-2 block text-sm leading-6 text-secondary-text">{localized.description}</span>
                    <span className="mt-3 inline-flex text-xs font-semibold text-cyan">
                      {localized.category}
                    </span>
                  </button>
                );
              })
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card/95 p-4 shadow-soft-card">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-foreground">
          <SlidersHorizontal className="h-4 w-4 text-cyan" />
          Configurações de Parâmetros
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr_180px_auto] lg:items-end">
          <label className="space-y-2 text-xs font-medium text-secondary-text">
            Mercado
            <select
              className="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground outline-none transition-colors focus:border-cyan"
              value={market}
              onChange={(event) => handleMarketChange(event.target.value)}
            >
              {MARKETS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2 text-xs font-medium text-secondary-text">
            Parâmetro de Estratégia
            <input
              className="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground outline-none transition-colors focus:border-cyan"
              value={strategy}
              onChange={(event) => handleStrategyChange(event.target.value)}
            />
          </label>

          <label className="space-y-2 text-xs font-medium text-secondary-text">
            Limite de Resultados
            <input
              className="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground outline-none transition-colors focus:border-cyan"
              type="number"
              min={1}
              max={100}
              value={maxResults}
              onChange={(event) => handleMaxResultsChange(Number(event.target.value))}
            />
          </label>

          <Button
            className="h-11 min-w-40"
            isLoading={loading}
            loadingText="Filtrando..."
            disabled={!enabled || loading}
            onClick={() => void handleSubmit()}
          >
            <Play className="h-4 w-4" />
            Executar Triagem
          </Button>
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card/95 p-4 shadow-soft-card">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <span
              className={`grid h-7 w-7 place-items-center rounded-full ${
                candidates.length > 0 ? 'text-success' : enabled ? 'text-cyan' : 'text-warning'
              }`}
            >
              {candidates.length > 0 ? <CheckCircle2 className="h-5 w-5" /> : <CircleAlert className="h-5 w-5" />}
            </span>
            <div>
              <h2 className="text-sm font-semibold text-foreground">
                {candidates.length > 0 ? 'Triagem Concluída' : enabled ? 'Aguardando Execução' : 'Aguardando Ativação'}
              </h2>
              <p className="mt-1 text-xs text-secondary-text">
                Estratégia Atual: {displayedStrategy} · {MARKETS.find((item) => item.id === market)?.label}
              </p>
            </div>
          </div>
          <div className="grid gap-1 text-xs text-secondary-text sm:text-right">
            <span>Execução ID: {screenMeta?.runId || '-'}</span>
            <span>
              Snapshot {screenMeta?.snapshotCount ?? '-'} · Pós-Filtro {screenMeta?.afterFilterCount ?? '-'} · Candidatos {screenMeta?.candidateCount ?? candidates.length}
            </span>
            <span>
              LLM: {screenMeta?.llmRanked ? 'Classificado' : screenMeta ? 'Não Classificado' : '-'}
              {screenMeta?.llmCoverage != null ? ` · Cobertura ${formatPercent(screenMeta.llmCoverage)}` : ''}
            </span>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card/95 p-4 shadow-soft-card">
        <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-foreground">Resultados da Triagem</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-secondary-text">
              Os candidatos retornados pelo AlphaSift serão exibidos aqui. Expanda para ver fatores, riscos, resumos pós-análise e campos brutos.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-2 text-xs text-secondary-text">
            <Search className="h-4 w-4 text-cyan" />
            {candidates.length} candidatos
          </div>
        </div>

        {candidates.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border bg-surface/70 px-5 py-10 text-center">
            <p className="text-sm font-medium text-foreground">Sem Resultados</p>
            <p className="mt-2 text-sm text-secondary-text">Ative o AlphaSift e clique em "Executar Triagem" para gerar uma lista de candidatos.</p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border">
            <table className="w-full min-w-[860px] border-collapse text-sm">
              <thead className="bg-surface text-left text-xs text-secondary-text">
                <tr>
                  <th className="w-14 px-4 py-3 font-semibold">#</th>
                  <th className="px-4 py-3 font-semibold">Símbolo</th>
                  <th className="px-4 py-3 font-semibold">Nome</th>
                  <th className="px-4 py-3 font-semibold">Setor</th>
                  <th className="px-4 py-3 font-semibold">Preço</th>
                  <th className="px-4 py-3 font-semibold">Variação (%)</th>
                  <th className="px-4 py-3 font-semibold">Pontuação</th>
                  <th className="px-4 py-3 font-semibold">LLM</th>
                  <th className="px-4 py-3 font-semibold">Risco</th>
                  <th className="px-4 py-3 font-semibold">Detalhes</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((item) => {
                  const expanded = expandedCode === item.code;
                  const factors = getFactorEntries(item);
                  return (
                    <Fragment key={`${item.rank}-${item.code}`}>
                      <tr className="border-t border-border align-top transition-colors hover:bg-hover/50">
                        <td className="px-4 py-3 text-secondary-text">{item.rank}</td>
                        <td className="px-4 py-3 font-mono font-semibold text-foreground">{item.code}</td>
                        <td className="px-4 py-3 font-semibold text-foreground">{item.name || '-'}</td>
                        <td className="px-4 py-3 text-secondary-text">{item.industry || '-'}</td>
                        <td className="px-4 py-3 text-secondary-text">{formatNumber(item.price)}</td>
                        <td className="px-4 py-3 text-secondary-text">{formatNumber(item.changePct)}%</td>
                        <td className="px-4 py-3 font-bold text-cyan">{formatScore(item.score)}</td>
                        <td className="px-4 py-3 text-secondary-text">{formatScore(item.llmScore)}</td>
                        <td className="px-4 py-3">
                          <span className="rounded-lg bg-success/10 px-2.5 py-1 text-xs font-semibold text-success">
                            {item.riskLevel || 'desconhecido'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <button
                            className="text-sm font-semibold text-cyan transition-colors hover:text-foreground"
                            type="button"
                            onClick={() => setExpandedCode(expanded ? null : item.code)}
                          >
                            {expanded ? 'Recolher' : 'Expandir'}
                          </button>
                        </td>
                      </tr>
                      {expanded ? (
                        <tr className="border-t border-border bg-surface/45">
                          <td colSpan={10} className="px-4 py-4">
                            <div className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
                              <div className="space-y-3">
                                <div>
                                  <p className="text-xs font-semibold text-secondary-text">Resumo</p>
                                  <p className="mt-1 text-sm leading-6 text-foreground">{getCandidateReason(item)}</p>
                                </div>
                                <div>
                                  <p className="text-xs font-semibold text-secondary-text">Sinal de Ação</p>
                                  <p className="mt-1 text-sm text-foreground">{getSignal(item)}</p>
                                </div>
                                <div>
                                  <p className="text-xs font-semibold text-secondary-text">Julgamento LLM</p>
                                  <p className="mt-1 text-sm leading-6 text-foreground">
                                    {item.llmThesis || item.reason || 'Sem julgamento LLM disponível'}
                                  </p>
                                  <p className="mt-1 text-xs text-secondary-text">
                                    Setor {item.llmSector || '-'} · Tema {item.llmTheme || '-'} · Confiança {formatPercent(item.llmConfidence)}
                                  </p>
                                </div>
                                <div>
                                  <p className="text-xs font-semibold text-secondary-text">Tags de Risco</p>
                                  <p className="mt-1 text-sm text-foreground">
                                    {[...(item.riskFlags || []), ...(item.llmRisks || [])].length
                                      ? [...(item.riskFlags || []), ...(item.llmRisks || [])].join(', ')
                                      : 'Nenhum'}
                                  </p>
                                </div>
                              </div>
                              <div className="space-y-3">
                                <div>
                                  <p className="text-xs font-semibold text-secondary-text">Fatores Principais</p>
                                  <div className="mt-2 grid grid-cols-2 gap-2">
                                    {factors.length > 0 ? (
                                      factors.map(([key, value]) => (
                                        <div key={key} className="rounded-lg border border-border bg-card px-3 py-2">
                                          <span className="block text-xs text-secondary-text">{key}</span>
                                          <span className="text-sm font-semibold text-foreground">{formatNumber(value)}</span>
                                        </div>
                                      ))
                                    ) : (
                                      <span className="text-sm text-secondary-text">Sem detalhes de fatores</span>
                                    )}
                                  </div>
                                </div>
                                <div>
                                  <p className="text-xs font-semibold text-secondary-text">Volume</p>
                                  <p className="mt-1 text-sm text-foreground">{formatAmount(item.amount)}</p>
                                </div>
                                <div>
                                  <p className="text-xs font-semibold text-secondary-text">Itens de Observação LLM</p>
                                  <p className="mt-1 text-sm text-foreground">
                                    {item.llmWatchItems?.length ? item.llmWatchItems.join(', ') : 'Nenhum'}
                                  </p>
                                </div>
                                <div>
                                  <p className="text-xs font-semibold text-secondary-text">Catalisadores</p>
                                  <p className="mt-1 text-sm text-foreground">
                                    {item.llmCatalysts?.length ? item.llmCatalysts.join(', ') : 'Nenhum'}
                                  </p>
                                </div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
      </Fragment>
      ) : (
        <MarketScreenerTab />
      )}
    </AppPage>
  );
};

export default StockScreeningPage;

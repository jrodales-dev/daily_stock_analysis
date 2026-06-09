import type React from 'react';
import { useState, useEffect, useRef } from 'react';
import { Play, Activity, TrendingUp, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import { backtestApi, type BacktestResultMetrics, type BacktestRequest } from '../api/backtest';
import { getParsedApiError } from '../api/error';
import { Card, PageHeader, Input, Select, Button } from '../components/common';

function formatMoney(val: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
}

function formatPct(val: number) {
  const sign = val > 0 ? '+' : '';
  return `${sign}${val.toFixed(2)}%`;
}

export const BacktestPage: React.FC = () => {
  useEffect(() => {
    document.title = 'Backtesting Engine - DSA';
  }, []);

  const [ticker, setTicker] = useState('AAPL');
  const [days, setDays] = useState(365);
  const [techWeight, setTechWeight] = useState(70);
  const [sentWeight, setSentWeight] = useState(30);
  const [mockSentiment, setMockSentiment] = useState('neutral');

  const [taskId, setTaskId] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [statusText, setStatusText] = useState('');
  const [result, setResult] = useState<BacktestResultMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pollInterval = useRef<number | ReturnType<typeof setInterval> | null>(null);

  const startPolling = (tid: string) => {
    if (pollInterval.current) clearInterval(pollInterval.current);
    pollInterval.current = setInterval(async () => {
      try {
        const res = await backtestApi.getStatus(tid);
        if (res.status === 'SUCCESS') {
          setIsRunning(false);
          setStatusText('Concluído!');
          clearInterval(pollInterval.current!);
          if (res.result && !('error' in res.result)) {
            setResult(res.result as BacktestResultMetrics);
          } else {
            setError((res.result as any)?.error || 'Erro desconhecido ao obter resultados');
          }
        } else if (res.status === 'FAILED') {
          setIsRunning(false);
          setStatusText('Falhou');
          clearInterval(pollInterval.current!);
          setError((res.result as any)?.error || 'A tarefa falhou');
        } else {
          setStatusText(`Executando... (${res.status})`);
        }
      } catch (err: any) {
        setIsRunning(false);
        setStatusText('Erro');
        clearInterval(pollInterval.current!);
        setError(getParsedApiError(err).message);
      }
    }, 2000);
  };

  useEffect(() => {
    return () => {
      if (pollInterval.current) clearInterval(pollInterval.current);
    };
  }, []);

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker.trim()) return;

    setIsRunning(true);
    setResult(null);
    setError(null);
    setTaskId(null);
    setStatusText('Iniciando...');

    try {
      const payload: BacktestRequest = {
        ticker: ticker.toUpperCase(),
        days: days,
        technicalWeight: techWeight / 100,
        sentimentWeight: sentWeight / 100,
        mockSentiment: mockSentiment,
      };
      const res = await backtestApi.run(payload);
      setTaskId(res.taskId);
      startPolling(res.taskId);
    } catch (err: any) {
      setIsRunning(false);
      setError(getParsedApiError(err).message);
      setStatusText('Falhou ao iniciar');
    }
  };

  return (
    <div className="min-h-screen space-y-6 p-4 md:p-6 lg:p-8 max-w-7xl mx-auto">
      <PageHeader
        title="Motor de Backtesting"
        description="Avalie a performance de estratégias (Técnica + Sentimento) no histórico de preços usando Celery e Pandas."
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Formulário */}
        <Card className="p-5 lg:col-span-1">
          <form onSubmit={handleRun} className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground mb-4">Configuração</h2>
            
            <div>
              <label className="block text-sm text-secondary-text mb-1">Ticker</label>
              <Input
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                placeholder="Ex: AAPL"
                disabled={isRunning}
                required
              />
            </div>

            <div>
              <label className="block text-sm text-secondary-text mb-1">Período (Dias Históricos)</label>
              <Input
                type="number"
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                min={50}
                disabled={isRunning}
                required
              />
              <p className="text-xs text-muted-text mt-1">Mínimo 50 dias para cálculo da SMA50.</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-secondary-text mb-1">Peso Técnico (%)</label>
                <Input
                  type="number"
                  value={techWeight}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    setTechWeight(v);
                    setSentWeight(100 - v);
                  }}
                  min={0}
                  max={100}
                  disabled={isRunning}
                />
              </div>
              <div>
                <label className="block text-sm text-secondary-text mb-1">Peso Sentimento (%)</label>
                <Input
                  type="number"
                  value={sentWeight}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    setSentWeight(v);
                    setTechWeight(100 - v);
                  }}
                  min={0}
                  max={100}
                  disabled={isRunning}
                />
              </div>
            </div>

            <div>
              <label className="block text-sm text-secondary-text mb-1">Sentimento Base (Mock)</label>
              <Select
                value={mockSentiment}
                onChange={setMockSentiment}
                options={[
                  { value: 'bullish', label: 'Bullish (+1.0)' },
                  { value: 'somewhat_bullish', label: 'Somewhat Bullish (+0.5)' },
                  { value: 'neutral', label: 'Neutral (0.0)' },
                  { value: 'somewhat_bearish', label: 'Somewhat Bearish (-0.5)' },
                  { value: 'bearish', label: 'Bearish (-1.0)' },
                ]}
                disabled={isRunning}
              />
              <p className="text-xs text-muted-text mt-1">Aplicado ao período histórico completo.</p>
            </div>

            <Button
              type="submit"
              variant="primary"
              className="w-full mt-4"
              disabled={isRunning}
            >
              {isRunning ? (
                <>
                  <Activity className="w-4 h-4 mr-2 animate-spin" />
                  {statusText}
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Rodar Backtest
                </>
              )}
            </Button>
          </form>

          {error && (
            <div className="mt-4 p-3 bg-danger/10 border border-danger/20 rounded-xl flex items-start gap-2">
              <AlertTriangle className="w-5 h-5 text-danger shrink-0 mt-0.5" />
              <p className="text-sm text-danger-text">{error}</p>
            </div>
          )}
        </Card>

        {/* Resultados */}
        <div className="lg:col-span-2 space-y-6">
          {!result && !isRunning && !error && (
            <Card className="h-full min-h-[300px] flex flex-col items-center justify-center p-8 border-dashed bg-card/40">
              <Activity className="w-12 h-12 text-muted-text mb-4 opacity-50" />
              <p className="text-secondary-text text-center">
                Configure os parâmetros ao lado e rode um backtest para ver a performance simulada da estratégia.
              </p>
            </Card>
          )}

          {isRunning && !result && (
            <Card className="h-full min-h-[300px] flex flex-col items-center justify-center p-8 bg-card/40">
              <div className="relative w-16 h-16 mb-6">
                <div className="absolute inset-0 border-4 border-primary/20 rounded-full"></div>
                <div className="absolute inset-0 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
              </div>
              <h3 className="text-lg font-medium text-foreground mb-2">Simulando Estratégia...</h3>
              <p className="text-sm text-secondary-text">Processando {days} dias de histórico para {ticker.toUpperCase()}</p>
              <p className="text-xs text-muted-text mt-4 font-mono">Task ID: {taskId}</p>
            </Card>
          )}

          {result && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <Card className="p-4 flex flex-col items-center justify-center text-center">
                  <p className="text-xs text-secondary-text uppercase tracking-wider mb-1">Retorno Total</p>
                  <p className={`text-2xl font-bold ${result.total_return_pct >= 0 ? 'text-success' : 'text-danger'}`}>
                    {formatPct(result.total_return_pct)}
                  </p>
                </Card>
                <Card className="p-4 flex flex-col items-center justify-center text-center">
                  <p className="text-xs text-secondary-text uppercase tracking-wider mb-1">Retorno Anualizado</p>
                  <p className={`text-2xl font-bold ${result.annualized_return_pct >= 0 ? 'text-success' : 'text-danger'}`}>
                    {formatPct(result.annualized_return_pct)}
                  </p>
                </Card>
                <Card className="p-4 flex flex-col items-center justify-center text-center">
                  <p className="text-xs text-secondary-text uppercase tracking-wider mb-1">Win Rate</p>
                  <p className="text-2xl font-bold text-foreground">
                    {result.win_rate_pct.toFixed(1)}%
                  </p>
                </Card>
                <Card className="p-4 flex flex-col items-center justify-center text-center">
                  <p className="text-xs text-secondary-text uppercase tracking-wider mb-1">Max Drawdown</p>
                  <p className="text-2xl font-bold text-danger">
                    {formatPct(result.max_drawdown_pct)}
                  </p>
                </Card>
              </div>

              <Card className="p-6 relative overflow-hidden">
                <div className="absolute top-0 right-0 p-32 bg-primary/5 blur-3xl rounded-full -translate-y-1/2 translate-x-1/3"></div>
                <h3 className="text-lg font-semibold text-foreground mb-4 relative z-10 flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-primary" />
                  Resumo da Simulação ({result.ticker})
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 relative z-10">
                  <div className="space-y-4">
                    <div className="flex justify-between items-center py-2 border-b border-white/5">
                      <span className="text-secondary-text">Capital Inicial</span>
                      <span className="font-mono">{formatMoney(result.initial_capital)}</span>
                    </div>
                    <div className="flex justify-between items-center py-2 border-b border-white/5">
                      <span className="text-secondary-text">Patrimônio Final</span>
                      <span className="font-mono font-medium text-foreground">{formatMoney(result.final_equity)}</span>
                    </div>
                    <div className="flex justify-between items-center py-2 border-b border-white/5">
                      <span className="text-secondary-text">Total de Trades</span>
                      <span className="font-mono">{result.total_trades}</span>
                    </div>
                  </div>
                  
                  <div className="space-y-4">
                    <div className="flex justify-between items-center py-2 border-b border-white/5">
                      <span className="text-secondary-text">Dias Analisados</span>
                      <span className="font-mono">{result.days_analyzed}</span>
                    </div>
                    <div className="flex justify-between items-center py-2 border-b border-white/5">
                      <span className="text-secondary-text">Sharpe Ratio</span>
                      <span className={`font-mono font-medium ${result.sharpe_ratio >= 1 ? 'text-success' : 'text-foreground'}`}>
                        {result.sharpe_ratio.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-2 border-b border-white/5">
                      <span className="text-secondary-text">Performance vs Buy & Hold</span>
                      <span className="font-mono flex items-center gap-1">
                        {result.total_return_pct > 0 ? (
                          <CheckCircle2 className="w-4 h-4 text-success" />
                        ) : (
                          <XCircle className="w-4 h-4 text-danger" />
                        )}
                        Pendente
                      </span>
                    </div>
                  </div>
                </div>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default BacktestPage;

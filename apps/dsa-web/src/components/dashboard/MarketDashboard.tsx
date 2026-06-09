import React, { useState } from 'react';
import { useOhlcv, useQuote } from '../../hooks/useMarketData';
import { useMarketWebSocket } from '../../hooks/useMarketWebSocket';
import { useMarketStore } from '../../store/marketStore';
import { LightweightChart } from '../charts/LightweightChart';
import { StatCard } from '../common';
import { Activity, TrendingUp, Clock, BarChart3 } from 'lucide-react';

interface MarketDashboardProps {
  defaultTicker?: string;
}

export const MarketDashboard: React.FC<MarketDashboardProps> = ({ defaultTicker = 'AAPL' }) => {
  const [ticker] = useState(defaultTicker);
  const [interval, setInterval] = useState('1D');

  // React Query for historical data
  const { data: ohlcvData, isLoading: isOhlcvLoading } = useOhlcv(ticker, interval);
  const { data: initialQuote, isLoading: isQuoteLoading } = useQuote(ticker);

  // Initialize WebSocket connection
  useMarketWebSocket();

  // Zustand state for real-time updates
  const { quotes, isConnected } = useMarketStore();

  const currentQuote = quotes[ticker] || initialQuote;

  if (isQuoteLoading && !currentQuote) {
    return <div className="p-8 text-center text-[var(--foreground)] animate-pulse">Carregando dados de mercado...</div>;
  }

  const isPositive = currentQuote?.change >= 0;

  return (
    <div className="flex flex-col gap-6 p-4 md:p-6 w-full animate-in fade-in duration-500">
      
      {/* KPI Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label={ticker}
          value={`$${currentQuote?.last?.toFixed(2) || '0.00'}`}
          hint={currentQuote?.change_percent != null ? `${currentQuote.change_percent >= 0 ? '+' : ''}${currentQuote.change_percent.toFixed(2)}% (Últimas 24h)` : undefined}
          icon={<Activity className="h-5 w-5 text-emerald-500" />}
        />
        <StatCard
          label="Volume"
          value={currentQuote?.volume?.toLocaleString() || '0'}
          icon={<BarChart3 className="h-5 w-5 text-blue-500" />}
        />
        <StatCard
          label="Bid / Ask"
          value={`$${currentQuote?.bid?.toFixed(2) || '0'} / $${currentQuote?.ask?.toFixed(2) || '0'}`}
          icon={<TrendingUp className="h-5 w-5 text-purple-500" />}
        />
        <StatCard
          label="Status WS"
          value={isConnected ? 'Conectado' : 'Desconectado'}
          icon={<Clock className={`h-5 w-5 ${isConnected ? 'text-emerald-500' : 'text-red-500'}`} />}
        />
      </div>

      {/* Chart Section */}
      <div className="w-full flex-1 min-h-[500px] border border-[var(--border-subtle)] rounded-xl bg-[var(--surface)] p-4 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <h3 className="font-semibold text-lg text-[var(--foreground)]">{ticker} Gráfico</h3>
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${isPositive ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'}`}>
              {isPositive ? '+' : ''}{currentQuote?.change_percent?.toFixed(2)}%
            </span>
          </div>
          
          <div className="flex gap-2">
            {['1D', '1W', '1M'].map(int => (
              <button
                key={int}
                onClick={() => setInterval(int)}
                className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                  interval === int 
                    ? 'bg-[var(--primary)] text-[var(--primary-foreground)]' 
                    : 'bg-[var(--hover)] text-[var(--secondary-text)] hover:text-[var(--foreground)]'
                }`}
              >
                {int}
              </button>
            ))}
          </div>
        </div>
        
        {isOhlcvLoading ? (
          <div className="w-full h-[400px] flex items-center justify-center text-[var(--secondary-text)]">
            Carregando gráfico...
          </div>
        ) : (
          <LightweightChart data={ohlcvData || []} type="candlestick" height={400} />
        )}
      </div>
    </div>
  );
};

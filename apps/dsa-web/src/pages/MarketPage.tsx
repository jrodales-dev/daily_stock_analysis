import React, { useEffect, useState } from 'react';
import { MarketDashboard } from '../components/dashboard/MarketDashboard';
import { StockDetails } from '../components/dashboard/StockDetails';
import { MarketNews } from '../components/dashboard/MarketNews';
import { PageHeader, Input } from '../components/common';

const MarketPage: React.FC = () => {
  const [ticker, setTicker] = useState('AAPL');

  useEffect(() => {
    document.title = 'Mercado - DSA Terminal';
  }, []);

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-[var(--background)]">
      <div className="flex-none px-4 py-4 md:px-6 flex items-center justify-between">
        <PageHeader 
          title="Terminal de Mercado" 
          description="Acompanhamento em tempo real e gráficos interativos."
        />
        <div className="w-64">
          <Input 
            placeholder="Buscar Ativo (ex: AAPL)" 
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            className="bg-[var(--surface)]"
          />
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-4 md:px-6 pb-6 flex flex-col gap-8">
        <MarketDashboard defaultTicker={ticker} />
        
        <div className="border-t border-[var(--border-subtle)] pt-8 grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-2">
            <h2 className="text-xl font-bold text-[var(--foreground)] mb-6">Análise Fundamentalista</h2>
            <StockDetails ticker={ticker} />
          </div>
          <div>
            <h2 className="text-xl font-bold text-[var(--foreground)] mb-6">Notícias Recentes</h2>
            <MarketNews ticker={ticker} />
          </div>
        </div>
      </div>
    </div>
  );
};

export default MarketPage;

import React from 'react';
import { useProfile, useFinancials, useMetrics } from '../../hooks/useFundamentals';
import { Card, StatCard } from '../common';
import { Building2, Users, Globe, Briefcase, TrendingUp, DollarSign, Percent } from 'lucide-react';

interface StockDetailsProps {
  ticker: string;
}

export const StockDetails: React.FC<StockDetailsProps> = ({ ticker }) => {
  const { data: profile, isLoading: isProfileLoading } = useProfile(ticker);
  const { data: financials, isLoading: isFinancialsLoading } = useFinancials(ticker);
  const { data: metrics } = useMetrics(ticker);

  if (isProfileLoading) {
    return <div className="animate-pulse p-4 text-[var(--secondary-text)]">Carregando perfil da empresa...</div>;
  }

  if (!profile) {
    return <div className="p-4 text-[var(--secondary-text)]">Dados da empresa não encontrados.</div>;
  }

  const formatLargeNum = (num: number) => {
    if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
    if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
    return `$${num.toLocaleString()}`;
  };

  return (
    <div className="flex flex-col gap-6 animate-in fade-in duration-500">
      
      {/* Profile Header */}
      <Card className="p-6">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold text-[var(--foreground)]">{profile.name} ({profile.symbol})</h2>
            <div className="flex flex-wrap items-center gap-4 mt-2 text-sm text-[var(--secondary-text)]">
              <span className="flex items-center gap-1"><Building2 className="w-4 h-4" /> {profile.industry}</span>
              <span className="flex items-center gap-1"><Briefcase className="w-4 h-4" /> {profile.sector}</span>
              <span className="flex items-center gap-1"><Users className="w-4 h-4" /> {profile.employees?.toLocaleString()} func.</span>
              <a href={profile.website} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[var(--primary)] hover:underline">
                <Globe className="w-4 h-4" /> Website
              </a>
            </div>
          </div>
        </div>
        <p className="mt-4 text-[var(--foreground)] leading-relaxed text-sm">
          {profile.description}
        </p>
      </Card>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard 
          label="Market Cap" 
          value={formatLargeNum(profile.market_cap)} 
          icon={<DollarSign className="w-5 h-5 text-emerald-500" />} 
        />
        <StatCard 
          label="P/E Ratio" 
          value={profile.pe_ratio?.toFixed(2) || 'N/A'} 
          icon={<TrendingUp className="w-5 h-5 text-blue-500" />} 
        />
        <StatCard 
          label="Div. Yield" 
          value={`${(profile.dividend_yield * 100).toFixed(2)}%`} 
          icon={<Percent className="w-5 h-5 text-purple-500" />} 
        />
        <StatCard 
          label="ROIC" 
          value={metrics?.roic ? `${(metrics.roic * 100).toFixed(2)}%` : 'N/A'} 
          icon={<TrendingUp className="w-5 h-5 text-amber-500" />} 
        />
      </div>

      {/* Financials Table */}
      <Card className="p-0 overflow-hidden border border-[var(--border-subtle)]">
        <div className="px-6 py-4 border-b border-[var(--border-subtle)]">
          <h3 className="font-semibold text-lg text-[var(--foreground)]">Performance Financeira Anual</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-[var(--surface)] text-[var(--secondary-text)]">
              <tr>
                <th className="px-6 py-3 font-medium">Ano</th>
                <th className="px-6 py-3 font-medium">Receita</th>
                <th className="px-6 py-3 font-medium">Lucro Líquido</th>
                <th className="px-6 py-3 font-medium">EPS</th>
                <th className="px-6 py-3 font-medium">Margem Oper.</th>
                <th className="px-6 py-3 font-medium">FCF</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)] text-[var(--foreground)]">
              {isFinancialsLoading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-4 text-center text-[var(--secondary-text)]">Carregando histórico...</td>
                </tr>
              ) : financials && financials.length > 0 ? (
                financials.map((fin) => (
                  <tr key={fin.year} className="hover:bg-[var(--hover)] transition-colors">
                    <td className="px-6 py-4 font-medium">{fin.year}</td>
                    <td className="px-6 py-4">{formatLargeNum(fin.revenue)}</td>
                    <td className="px-6 py-4">{formatLargeNum(fin.net_income)}</td>
                    <td className="px-6 py-4">${fin.eps?.toFixed(2)}</td>
                    <td className="px-6 py-4">{(fin.operating_margin * 100).toFixed(1)}%</td>
                    <td className="px-6 py-4">{formatLargeNum(fin.fcf)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="px-6 py-4 text-center text-[var(--secondary-text)]">Nenhum histórico financeiro encontrado.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
      
    </div>
  );
};

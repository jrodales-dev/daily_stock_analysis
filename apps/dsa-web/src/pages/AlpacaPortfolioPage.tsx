import type React from 'react';
import { useEffect, useMemo } from 'react';
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
  Pie,
  PieChart,
  Cell
} from 'recharts';
import { useAlpacaAccount, useAlpacaPositions, useAlpacaPerformance } from '../hooks/useAlpaca';
import { PageHeader, Card, EmptyState, ApiErrorAlert } from '../components/common';
import { PageLoadingFallback } from '../components/layout/RouteBoundary';
import { getParsedApiError } from '../api/error';

const PIE_COLORS = ['#00d4ff', '#00ff88', '#ffaa00', '#ff7a45', '#7f8cff', '#ff4466'];

function formatMoney(value: string | number | undefined | null): string {
  if (value == null) return '$0.00';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(num || 0);
}

function formatPct(value: string | number | undefined | null): string {
  if (value == null) return '0.00%';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  const sign = num > 0 ? '+' : '';
  return `${sign}${(num * 100).toFixed(2)}%`;
}

export const AlpacaPortfolioPage: React.FC = () => {
  useEffect(() => {
    document.title = 'Portfólio Alpaca - DSA';
  }, []);

  const {
    data: account,
    isLoading: isAccountLoading,
    error: accountError
  } = useAlpacaAccount();

  const {
    data: positions,
    isLoading: isPositionsLoading,
  } = useAlpacaPositions();

  const {
    data: performance,
    isLoading: isPerformanceLoading,
  } = useAlpacaPerformance('1M', '1D');

  const isLoading = isAccountLoading || isPositionsLoading || isPerformanceLoading;

  const chartData = useMemo(() => {
    if (!performance) return [];
    return performance.timestamp.map((ts, index) => ({
      date: new Date(ts * 1000).toLocaleDateString(),
      equity: performance.equity[index],
    }));
  }, [performance]);

  const pieData = useMemo(() => {
    if (!positions) return [];
    return positions.map(p => ({
      name: p.symbol,
      value: parseFloat(p.market_value)
    })).filter(p => p.value > 0);
  }, [positions]);

  if (isLoading) {
    return <PageLoadingFallback />;
  }

  if (accountError) {
    return (
      <div className="p-6">
        <PageHeader title="Portfólio Alpaca" />
        <ApiErrorAlert error={getParsedApiError(accountError)} className="mt-4" />
      </div>
    );
  }

  return (
    <div className="min-h-screen space-y-6 p-4 md:p-6 lg:p-8 max-w-7xl mx-auto">
      <PageHeader
        title="Portfólio Alpaca"
        description="Acompanhe o desempenho de sua conta e posições em tempo real na Alpaca"
      />

      {/* Account KPI */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-5 flex flex-col justify-center">
          <p className="text-sm text-secondary-text mb-1">Equity (USD)</p>
          <p className="text-3xl font-bold text-foreground">
            {formatMoney(account?.portfolio_value || 0)}
          </p>
        </Card>
        <Card className="p-5 flex flex-col justify-center">
          <p className="text-sm text-secondary-text mb-1">Poder de Compra (USD)</p>
          <p className="text-3xl font-bold text-foreground">
            {formatMoney(account?.buying_power || 0)}
          </p>
        </Card>
        <Card className="p-5 flex flex-col justify-center">
          <p className="text-sm text-secondary-text mb-1">Caixa Disponível (USD)</p>
          <p className="text-3xl font-bold text-foreground">
            {formatMoney(account?.cash || 0)}
          </p>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Performance Chart */}
        <Card className="p-5 lg:col-span-2 min-h-[400px] flex flex-col">
          <h2 className="text-lg font-semibold text-foreground mb-4">Evolução do Portfólio (1M)</h2>
          {chartData.length > 0 ? (
            <div className="flex-1 w-full relative">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00d4ff" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#00d4ff" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
                  <XAxis
                    dataKey="date"
                    stroke="#888888"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    minTickGap={30}
                  />
                  <YAxis
                    stroke="#888888"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => `$${value}`}
                    domain={['auto', 'auto']}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1a1a1a', border: 'none', borderRadius: '8px', color: '#fff' }}
                    itemStyle={{ color: '#00d4ff' }}
                    formatter={(value: any) => [formatMoney(value), 'Equity']}
                  />
                  <Area
                    type="monotone"
                    dataKey="equity"
                    stroke="#00d4ff"
                    fillOpacity={1}
                    fill="url(#colorEquity)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <p className="text-secondary-text">Nenhum dado de performance disponível.</p>
            </div>
          )}
        </Card>

        {/* Positions Pie Chart */}
        <Card className="p-5 min-h-[400px] flex flex-col">
          <h2 className="text-lg font-semibold text-foreground mb-4">Alocação Atual</h2>
          {pieData.length > 0 ? (
            <div className="flex-1 w-full relative">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Tooltip
                    formatter={(value: any) => formatMoney(value)}
                    contentStyle={{ backgroundColor: '#1a1a1a', border: 'none', borderRadius: '8px' }}
                  />
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={2}
                    dataKey="value"
                    stroke="none"
                  >
                    {pieData.map((_entry, index) => (
                      <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="mt-4 flex flex-wrap justify-center gap-3">
                {pieData.map((entry, idx) => (
                  <div key={entry.name} className="flex items-center gap-1.5 text-xs">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: PIE_COLORS[idx % PIE_COLORS.length] }} />
                    <span className="text-secondary-text">{entry.name}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <p className="text-secondary-text">Sem posições abertas.</p>
            </div>
          )}
        </Card>
      </div>

      {/* Positions Table */}
      <Card className="p-5">
        <h2 className="text-lg font-semibold text-foreground mb-4">Posições Abertas</h2>
        {!positions || positions.length === 0 ? (
          <EmptyState
            title="Nenhuma posição"
            description="Você não possui ações na sua conta Alpaca no momento."
            className="py-10"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="border-b border-white/10 text-secondary-text">
                <tr>
                  <th className="pb-3 font-medium">Ativo</th>
                  <th className="pb-3 font-medium text-right">Qtd</th>
                  <th className="pb-3 font-medium text-right">Valor de Mercado</th>
                  <th className="pb-3 font-medium text-right">P/L ($)</th>
                  <th className="pb-3 font-medium text-right">P/L (%)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {positions.map((pos) => {
                  const pl = parseFloat(pos.unrealized_pl);
                  const isPositive = pl >= 0;
                  return (
                    <tr key={pos.symbol} className="hover:bg-white/[0.02] transition-colors">
                      <td className="py-3 font-medium text-foreground">{pos.symbol}</td>
                      <td className="py-3 text-right">{pos.qty}</td>
                      <td className="py-3 text-right">{formatMoney(pos.market_value)}</td>
                      <td className={`py-3 text-right font-medium ${isPositive ? 'text-green-500' : 'text-red-500'}`}>
                        {formatMoney(pos.unrealized_pl)}
                      </td>
                      <td className={`py-3 text-right font-medium ${isPositive ? 'text-green-500' : 'text-red-500'}`}>
                        {formatPct(pos.unrealized_plpc)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
};

export default AlpacaPortfolioPage;

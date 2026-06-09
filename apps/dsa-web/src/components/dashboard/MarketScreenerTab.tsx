import React, { useState } from 'react';
import { useScreener } from '../../hooks/useMarketData';
import { Button, Input, Select, Card } from '../common';
import { Plus, Trash2, Search, Filter } from 'lucide-react';
import type { ScreenerFilter } from '../../api/market';

const AVAILABLE_FIELDS = [
  { id: 'pe_ratio', label: 'P/E Ratio (Preço/Lucro)' },
  { id: 'market_cap', label: 'Market Cap' },
  { id: 'dividend_yield', label: 'Dividend Yield' },
  { id: 'volume', label: 'Volume Diário' },
  { id: 'rsi_14', label: 'RSI (14)' },
  { id: 'macd', label: 'MACD' },
];

const OPERATORS = [
  { id: 'gt', label: 'Maior que (>)' },
  { id: 'gte', label: 'Maior ou igual (>=)' },
  { id: 'lt', label: 'Menor que (<)' },
  { id: 'lte', label: 'Menor ou igual (<=)' },
  { id: 'eq', label: 'Igual (=)' },
];

export const MarketScreenerTab: React.FC = () => {
  const [filters, setFilters] = useState<ScreenerFilter[]>([
    { field: 'pe_ratio', operator: 'lt', value: '20' }
  ]);
  
  const { mutate: runScreener, data: results, isPending: isLoading, error } = useScreener();

  const handleAddFilter = () => {
    setFilters([...filters, { field: 'pe_ratio', operator: 'lt', value: '' }]);
  };

  const handleRemoveFilter = (index: number) => {
    setFilters(filters.filter((_, i) => i !== index));
  };

  const handleUpdateFilter = (index: number, key: keyof ScreenerFilter, value: string) => {
    const newFilters = [...filters];
    newFilters[index] = { ...newFilters[index], [key]: value };
    setFilters(newFilters);
  };

  const handleSearch = () => {
    runScreener(filters);
  };

  const formatValue = (field: string, value: any) => {
    if (value === undefined || value === null) return '-';
    if (field === 'market_cap' || field === 'volume') {
      if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
      if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
      return value.toLocaleString();
    }
    if (field === 'dividend_yield') return `${(value * 100).toFixed(2)}%`;
    return typeof value === 'number' ? value.toFixed(2) : value;
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Filter className="w-5 h-5 text-[var(--primary)]" />
          <h2 className="text-lg font-semibold text-[var(--foreground)]">Filtros de Triagem</h2>
        </div>
        
        <div className="space-y-4">
          {filters.map((filter, index) => (
            <div key={index} className="flex flex-col sm:flex-row items-center gap-3">
              <div className="w-full sm:w-1/3">
                <Select
                  value={filter.field}
                  onChange={(val) => handleUpdateFilter(index, 'field', val)}
                  options={AVAILABLE_FIELDS.map(f => ({ value: f.id, label: f.label }))}
                />
              </div>
              <div className="w-full sm:w-1/4">
                <Select
                  value={filter.operator}
                  onChange={(val) => handleUpdateFilter(index, 'operator', val)}
                  options={OPERATORS.map(o => ({ value: o.id, label: o.label }))}
                />
              </div>
              <div className="w-full sm:w-1/3">
                <Input
                  type="number"
                  placeholder="Valor"
                  value={filter.value}
                  onChange={(e) => handleUpdateFilter(index, 'value', e.target.value)}
                />
              </div>
              <Button 
                variant="outline" 
                className="w-full sm:w-auto text-red-500 border-red-500/20 hover:bg-red-500/10 shrink-0"
                onClick={() => handleRemoveFilter(index)}
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          ))}
        </div>

        <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <Button variant="outline" onClick={handleAddFilter} className="w-full sm:w-auto">
            <Plus className="w-4 h-4 mr-2" /> Adicionar Filtro
          </Button>
          <Button onClick={handleSearch} isLoading={isLoading} className="w-full sm:w-auto min-w-[150px]">
            <Search className="w-4 h-4 mr-2" /> 
            {isLoading ? 'Buscando...' : 'Pesquisar'}
          </Button>
        </div>
        
        {error && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 text-red-500 rounded-md text-sm">
            Erro ao buscar: {error instanceof Error ? error.message : 'Falha na comunicação com a API'}
          </div>
        )}
      </Card>

      <Card className="p-0 overflow-hidden">
        <div className="px-6 py-4 border-b border-[var(--border-subtle)] flex items-center justify-between">
          <h3 className="font-semibold text-lg text-[var(--foreground)]">Resultados</h3>
          <span className="text-sm text-[var(--secondary-text)] bg-[var(--surface)] px-3 py-1 rounded-full border border-[var(--border-subtle)]">
            {results?.length || 0} encontrados
          </span>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-[var(--surface)] text-[var(--secondary-text)] border-b border-[var(--border-subtle)]">
              <tr>
                <th className="px-6 py-3 font-medium">Símbolo</th>
                <th className="px-6 py-3 font-medium">Nome</th>
                <th className="px-6 py-3 font-medium">Setor</th>
                {AVAILABLE_FIELDS.map(field => (
                  <th key={field.id} className="px-6 py-3 font-medium">{field.label}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)] text-[var(--foreground)]">
              {results && results.length > 0 ? (
                results.map((result, idx) => (
                  <tr key={idx} className="hover:bg-[var(--hover)] transition-colors">
                    <td className="px-6 py-4 font-bold text-[var(--primary)]">{result.symbol}</td>
                    <td className="px-6 py-4 font-medium">{result.name || '-'}</td>
                    <td className="px-6 py-4 text-[var(--secondary-text)]">{result.sector || '-'}</td>
                    {AVAILABLE_FIELDS.map(field => (
                      <td key={field.id} className="px-6 py-4">
                        {formatValue(field.id, result[field.id])}
                      </td>
                    ))}
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={3 + AVAILABLE_FIELDS.length} className="px-6 py-8 text-center text-[var(--secondary-text)]">
                    {isLoading ? 'Carregando resultados...' : 'Nenhum resultado encontrado. Ajuste os filtros e pesquise.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
      
    </div>
  );
};

import { apiClient } from './client';

export interface OhlcvData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface QuoteData {
  symbol: string;
  last: number;
  bid: number;
  ask: number;
  volume: number;
  change: number;
  change_percent: number;
  timestamp: string;
}

export interface ScreenerFilter {
  field: string;
  operator: 'gt' | 'lt' | 'eq' | 'gte' | 'lte';
  value: number | string;
}

export const marketApi = {
  getOhlcv: async (
    ticker: string,
    interval: string = '1D',
    start_date?: string,
    end_date?: string
  ): Promise<OhlcvData[]> => {
    const params = new URLSearchParams({ ticker, interval });
    if (start_date) params.append('start_date', start_date);
    if (end_date) params.append('end_date', end_date);
    
    const { data } = await apiClient.get<OhlcvData[]>(`/market/ohlcv?${params.toString()}`);
    return data;
  },

  getQuote: async (ticker: string): Promise<QuoteData> => {
    const { data } = await apiClient.get<QuoteData>(`/market/quote?ticker=${ticker}`);
    return data;
  },

  screener: async (filters: ScreenerFilter[]): Promise<any[]> => {
    const { data } = await apiClient.post<any[]>('/market/screener', { filters });
    return data;
  }
};

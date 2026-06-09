import { useQuery, useMutation } from '@tanstack/react-query';
import { marketApi } from '../api/market';
import type { ScreenerFilter } from '../api/market';

export const useOhlcv = (
  ticker: string, 
  interval: string = '1D', 
  startDate?: string, 
  endDate?: string,
  options?: { enabled?: boolean }
) => {
  return useQuery({
    queryKey: ['market', 'ohlcv', ticker, interval, startDate, endDate],
    queryFn: () => marketApi.getOhlcv(ticker, interval, startDate, endDate),
    enabled: options?.enabled !== false && !!ticker,
    staleTime: 60 * 1000, // 1 minute
  });
};

export const useQuote = (ticker: string, options?: { enabled?: boolean }) => {
  return useQuery({
    queryKey: ['market', 'quote', ticker],
    queryFn: () => marketApi.getQuote(ticker),
    enabled: options?.enabled !== false && !!ticker,
    staleTime: 10 * 1000, // 10 seconds
    refetchInterval: 10 * 1000, // auto refetch every 10s if not using WS
  });
};

export const useScreener = () => {
  return useMutation({
    mutationFn: (filters: ScreenerFilter[]) => marketApi.screener(filters),
  });
};

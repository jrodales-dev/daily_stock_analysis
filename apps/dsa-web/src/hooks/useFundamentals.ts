import { useQuery } from '@tanstack/react-query';
import { fundamentalsApi } from '../api/fundamentals';

export const useProfile = (ticker: string, options?: { enabled?: boolean }) => {
  return useQuery({
    queryKey: ['fundamentals', 'profile', ticker],
    queryFn: () => fundamentalsApi.getProfile(ticker),
    enabled: options?.enabled !== false && !!ticker,
    staleTime: 24 * 60 * 60 * 1000, // 24 hours
  });
};

export const useFinancials = (ticker: string, type: 'annual' | 'quarterly' = 'annual', options?: { enabled?: boolean }) => {
  return useQuery({
    queryKey: ['fundamentals', 'financials', ticker, type],
    queryFn: () => fundamentalsApi.getFinancials(ticker, type),
    enabled: options?.enabled !== false && !!ticker,
    staleTime: 24 * 60 * 60 * 1000, // 24 hours
  });
};

export const useMetrics = (ticker: string, options?: { enabled?: boolean }) => {
  return useQuery({
    queryKey: ['fundamentals', 'metrics', ticker],
    queryFn: () => fundamentalsApi.getMetrics(ticker),
    enabled: options?.enabled !== false && !!ticker,
    staleTime: 60 * 60 * 1000, // 1 hour
  });
};

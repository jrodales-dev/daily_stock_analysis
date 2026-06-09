import { useQuery } from '@tanstack/react-query';
import { alpacaApi } from '../api/alpaca';

export function useAlpacaAccount() {
  return useQuery({
    queryKey: ['alpaca', 'account'],
    queryFn: alpacaApi.getAccount,
    refetchInterval: 30000, // Refresh every 30s
  });
}

export function useAlpacaPositions() {
  return useQuery({
    queryKey: ['alpaca', 'positions'],
    queryFn: alpacaApi.getPositions,
    refetchInterval: 30000,
  });
}

export function useAlpacaPerformance(period = '1M', timeframe = '1D') {
  return useQuery({
    queryKey: ['alpaca', 'performance', period, timeframe],
    queryFn: () => alpacaApi.getPerformance(period, timeframe),
    staleTime: 60 * 60 * 1000, // 1 hour
  });
}

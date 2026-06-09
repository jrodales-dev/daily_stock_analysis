import { useQuery } from '@tanstack/react-query';
import { newsApi } from '../api/news';

export const useNews = (ticker?: string, limit: number = 20, options?: { enabled?: boolean }) => {
  return useQuery({
    queryKey: ['news', ticker, limit],
    queryFn: () => newsApi.getLatestNews(ticker, limit),
    enabled: options?.enabled !== false,
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchInterval: 5 * 60 * 1000,
  });
};

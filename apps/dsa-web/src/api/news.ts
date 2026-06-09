import { apiClient } from './client';

export interface NewsItem {
  id: string;
  title: string;
  source: string;
  published_at: string;
  url: string;
  summary: string;
  sentiment_score?: number;
  sentiment_label?: 'positive' | 'negative' | 'neutral';
  related_tickers?: string[];
}

export const newsApi = {
  getLatestNews: async (ticker?: string, limit: number = 20): Promise<NewsItem[]> => {
    const params = new URLSearchParams();
    if (ticker) params.append('ticker', ticker);
    params.append('limit', limit.toString());
    
    const { data } = await apiClient.get<NewsItem[]>(`/news?${params.toString()}`);
    return data;
  }
};

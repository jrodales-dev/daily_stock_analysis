import apiClient from './index';

export type ExtractItem = {
  code?: string | null;
  name?: string | null;
  confidence: string;
};

export type ExtractFromImageResponse = {
  codes: string[];
  items?: ExtractItem[];
  rawText?: string;
};

export type StockQuote = {
  stockCode: string;
  stockName?: string;
  currentPrice: number;
  change?: number;
  changePercent?: number;
  open?: number;
  high?: number;
  low?: number;
  prevClose?: number;
  volume?: number;
  amount?: number;
  updateTime?: string;
  source?: string;
};

export const stocksApi = {
  async extractFromImage(file: File): Promise<ExtractFromImageResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const headers: { [key: string]: string | undefined } = { 'Content-Type': undefined };
    const response = await apiClient.post(
      '/api/v1/stocks/extract-from-image',
      formData,
      {
        headers,
        timeout: 60000, // Vision API can be slow; 60s
      },
    );

    const data = response.data as { codes?: string[]; items?: ExtractItem[]; raw_text?: string };
    return {
      codes: data.codes ?? [],
      items: data.items,
      rawText: data.raw_text,
    };
  },

  async parseImport(file?: File, text?: string): Promise<ExtractFromImageResponse> {
    if (file) {
      const formData = new FormData();
      formData.append('file', file);
      const headers: { [key: string]: string | undefined } = { 'Content-Type': undefined };
      const response = await apiClient.post('/api/v1/stocks/parse-import', formData, { headers });
      const data = response.data as { codes?: string[]; items?: ExtractItem[] };
      return { codes: data.codes ?? [], items: data.items };
    }
    if (text) {
      const response = await apiClient.post('/api/v1/stocks/parse-import', { text });
      const data = response.data as { codes?: string[]; items?: ExtractItem[] };
      return { codes: data.codes ?? [], items: data.items };
    }
    throw new Error('Por favor, forneça um arquivo ou cole um texto');
  },

  async getQuote(stockCode: string): Promise<StockQuote> {
    const response = await apiClient.get(`/api/v1/stocks/${encodeURIComponent(stockCode)}/quote`);
    // Convert snake_case from backend to camelCase
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const data = response.data as any;
    return {
      stockCode: data.stock_code,
      stockName: data.stock_name,
      currentPrice: data.current_price,
      change: data.change,
      changePercent: data.change_percent,
      open: data.open,
      high: data.high,
      low: data.low,
      prevClose: data.prev_close,
      volume: data.volume,
      amount: data.amount,
      updateTime: data.update_time,
      source: data.source,
    };
  },
};

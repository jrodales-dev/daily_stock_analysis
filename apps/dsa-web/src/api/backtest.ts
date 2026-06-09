import apiClient from './index';

export interface BacktestRequest {
  ticker: string;
  days?: number;
  technicalWeight?: number;
  sentimentWeight?: number;
  mockSentiment?: string;
}

export interface BacktestRunResponse {
  taskId: string;
  status: string;
  message: string;
}

export interface BacktestResultMetrics {
  initial_capital: number;
  final_equity: number;
  total_return_pct: number;
  annualized_return_pct: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  win_rate_pct: number;
  total_trades: number;
  days_analyzed: number;
  ticker?: string;
}

export interface BacktestStatusResponse {
  task_id: string;
  status: string;
  result?: BacktestResultMetrics | { error: string };
}

export const backtestApi = {
  run: async (params: BacktestRequest): Promise<BacktestRunResponse> => {
    const payload = {
      ticker: params.ticker,
      days: params.days || 365,
      technical_weight: params.technicalWeight ?? 0.7,
      sentiment_weight: params.sentimentWeight ?? 0.3,
      mock_sentiment: params.mockSentiment || 'neutral',
    };
    const response = await apiClient.post<{ task_id: string; status: string; message: string }>(
      '/api/v1/backtest/run',
      payload
    );
    return {
      taskId: response.data.task_id,
      status: response.data.status,
      message: response.data.message,
    };
  },

  getStatus: async (taskId: string): Promise<BacktestStatusResponse> => {
    const response = await apiClient.get<BacktestStatusResponse>(`/api/v1/backtest/status/${taskId}`);
    return response.data;
  },
};

import apiClient from './index';

export interface AlpacaAccount {
  portfolio_value: string;
  buying_power: string;
  cash: string;
  currency: string;
}

export interface AlpacaPosition {
  symbol: string;
  qty: string;
  market_value: string;
  unrealized_pl: string;
  unrealized_plpc: string;
}

export interface AlpacaPerformance {
  timestamp: number[];
  equity: number[];
  profit_loss: number[];
  profit_loss_pct: number[];
  base_value: number;
  timeframe: string;
}

export const alpacaApi = {
  async getAccount(): Promise<AlpacaAccount> {
    const response = await apiClient.get<AlpacaAccount>('/api/v1/portfolio/account');
    return response.data;
  },

  async getPositions(): Promise<AlpacaPosition[]> {
    const response = await apiClient.get<AlpacaPosition[]>('/api/v1/portfolio/positions');
    return response.data;
  },

  async getPerformance(period = '1M', timeframe = '1D'): Promise<AlpacaPerformance> {
    const response = await apiClient.get<AlpacaPerformance>('/api/v1/portfolio/performance', {
      params: { period, timeframe }
    });
    return response.data;
  }
};

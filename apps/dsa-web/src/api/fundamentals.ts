import { apiClient } from './client';

export interface CompanyProfile {
  symbol: string;
  name: string;
  sector: string;
  industry: string;
  description: string;
  website: string;
  employees: number;
  market_cap: number;
  pe_ratio: number;
  dividend_yield: number;
}

export interface FinancialMetric {
  year: number;
  revenue: number;
  net_income: number;
  eps: number;
  operating_margin: number;
  fcf: number; // Free cash flow
}

export const fundamentalsApi = {
  getProfile: async (ticker: string): Promise<CompanyProfile> => {
    const { data } = await apiClient.get<CompanyProfile>(`/fundamentals/profile?ticker=${ticker}`);
    return data;
  },

  getFinancials: async (ticker: string, type: 'annual' | 'quarterly' = 'annual'): Promise<FinancialMetric[]> => {
    const { data } = await apiClient.get<FinancialMetric[]>(`/fundamentals/financials?ticker=${ticker}&type=${type}`);
    return data;
  },
  
  getMetrics: async (ticker: string): Promise<Record<string, number>> => {
    const { data } = await apiClient.get<Record<string, number>>(`/fundamentals/metrics?ticker=${ticker}`);
    return data;
  }
};

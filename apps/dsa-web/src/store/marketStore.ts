import { create } from 'zustand';
import type { QuoteData } from '../api/market';

interface MarketState {
  quotes: Record<string, QuoteData>;
  isConnected: boolean;
  activeSubscriptions: string[];
  setQuote: (ticker: string, data: QuoteData) => void;
  setConnectionStatus: (status: boolean) => void;
  addSubscription: (ticker: string) => void;
  removeSubscription: (ticker: string) => void;
}

export const useMarketStore = create<MarketState>((set) => ({
  quotes: {},
  isConnected: false,
  activeSubscriptions: [],
  
  setQuote: (ticker, data) => 
    set((state) => ({ 
      quotes: { ...state.quotes, [ticker]: data } 
    })),
    
  setConnectionStatus: (status) => 
    set({ isConnected: status }),
    
  addSubscription: (ticker) =>
    set((state) => ({
      activeSubscriptions: state.activeSubscriptions.includes(ticker) 
        ? state.activeSubscriptions 
        : [...state.activeSubscriptions, ticker]
    })),
    
  removeSubscription: (ticker) =>
    set((state) => ({
      activeSubscriptions: state.activeSubscriptions.filter(t => t !== ticker)
    })),
}));

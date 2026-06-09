import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface UserPreferences {
  defaultChartInterval: '1m' | '5m' | '15m' | '1h' | '1d';
  defaultChartPeriod: '1d' | '5d' | '1m' | '3m' | '1y' | 'max';
  notificationsEnabled: boolean;
}

interface UserState {
  preferences: UserPreferences;
  watchlists: Record<string, string[]>;
  updatePreferences: (prefs: Partial<UserPreferences>) => void;
  createWatchlist: (name: string, tickers?: string[]) => void;
  deleteWatchlist: (name: string) => void;
  addTickerToWatchlist: (watchlist: string, ticker: string) => void;
  removeTickerFromWatchlist: (watchlist: string, ticker: string) => void;
}

export const useUserStore = create<UserState>()(
  persist(
    (set) => ({
      preferences: {
        defaultChartInterval: '1d',
        defaultChartPeriod: '1y',
        notificationsEnabled: true,
      },
      watchlists: {
        'Favoritos': ['AAPL', 'MSFT', 'NVDA', 'TSLA']
      },
      updatePreferences: (prefs) => 
        set((state) => ({ preferences: { ...state.preferences, ...prefs } })),
      createWatchlist: (name, tickers = []) => 
        set((state) => ({ watchlists: { ...state.watchlists, [name]: tickers } })),
      deleteWatchlist: (name) => 
        set((state) => {
          const newWatchlists = { ...state.watchlists };
          delete newWatchlists[name];
          return { watchlists: newWatchlists };
        }),
      addTickerToWatchlist: (watchlist, ticker) => 
        set((state) => {
          const list = state.watchlists[watchlist] || [];
          if (list.includes(ticker)) return state;
          return { watchlists: { ...state.watchlists, [watchlist]: [...list, ticker] } };
        }),
      removeTickerFromWatchlist: (watchlist, ticker) => 
        set((state) => {
          const list = state.watchlists[watchlist] || [];
          return { 
            watchlists: { 
              ...state.watchlists, 
              [watchlist]: list.filter(t => t !== ticker) 
            } 
          };
        })
    }),
    {
      name: 'dsa-user-storage',
    }
  )
);

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UiState {
  theme: 'light' | 'dark' | 'system';
  sidebarOpen: boolean;
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      theme: 'system',
      sidebarOpen: true,
      setTheme: (theme) => set({ theme }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
    }),
    {
      name: 'dsa-ui-storage',
    }
  )
);

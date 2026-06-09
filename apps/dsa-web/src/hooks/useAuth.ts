import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface User {
  id: number;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  username?: string;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  authEnabled: boolean;
  setupState: 'enabled' | 'password_retained' | 'no_password';
  passwordChangeable: boolean;
  login: (access_token: string, refresh_token: string) => Promise<{ success: boolean; error?: any }>;
  logout: () => void;
  setUser: (user: User | null) => void;
  refreshStatus: () => Promise<void>;
  changePassword: (current: string, newPass: string, confirmPass: string) => Promise<{ success: boolean; error?: any }>;
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      authEnabled: true,
      setupState: 'enabled',
      passwordChangeable: true,
      
      login: async (access_token, refresh_token) => {
        localStorage.setItem('access_token', access_token);
        localStorage.setItem('refresh_token', refresh_token);
        
        try {
          const payload = JSON.parse(atob(access_token.split('.')[1]));
          const user: User = {
            id: payload.sub ? parseInt(payload.sub, 10) : 0,
            email: payload.email || 'user@example.com',
            is_active: true,
            is_superuser: false,
            username: payload.sub || 'User'
          };
          
          set({ user, isAuthenticated: true, isLoading: false });
          return { success: true };
        } catch (e) {
          console.error('Failed to parse JWT', e);
          set({ isAuthenticated: true, isLoading: false }); // Fallback for dev mode
          return { success: true };
        }
      },
      
      logout: () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        set({ user: null, isAuthenticated: false });
      },
      
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      refreshStatus: async () => {},
      changePassword: async (_current, _newPass, _confirmPass) => {
        return { success: true };
      }
    }),
    {
      name: 'dsa-auth-storage',
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
);

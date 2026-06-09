import type React from 'react';
import { lazy, useEffect } from 'react';
import { BrowserRouter as Router, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { Shell } from './components/common';
import {
  PageLoadingFallback,
  RouteOutletBoundary,
  StandaloneRouteBoundary,
} from './components/layout/RouteBoundary';
import { useAuth } from './hooks';
import { useAgentChatStore } from './stores/agentChatStore';
import './App.css';

const HomePage = lazy(() => import('./pages/HomePage'));
const MarketPage = lazy(() => import('./pages/MarketPage'));
const BacktestPage = lazy(() => import('./pages/BacktestPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const RegisterPage = lazy(() => import('./pages/RegisterPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const ChatPage = lazy(() => import('./pages/ChatPage'));
const AlpacaPortfolioPage = lazy(() => import('./pages/AlpacaPortfolioPage'));
const PortfolioPage = lazy(() => import('./pages/PortfolioPage'));
const AlertsPage = lazy(() => import('./pages/AlertsPage'));
const StockScreeningPage = lazy(() => import('./pages/StockScreeningPage'));

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

const AppContent: React.FC = () => {
  const location = useLocation();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    useAgentChatStore.getState().setCurrentRoute(location.pathname);
  }, [location.pathname]);

  if (isLoading) {
    return <PageLoadingFallback />;
  }

  // Auth guard
  const publicRoutes = ['/login', '/register'];
  const isPublicRoute = publicRoutes.includes(location.pathname);

  if (!isAuthenticated && !isPublicRoute) {
    const redirect = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }

  if (isAuthenticated && isPublicRoute) {
    return <Navigate to="/" replace />;
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={
          <StandaloneRouteBoundary>
            <LoginPage />
          </StandaloneRouteBoundary>
        }
      />
      <Route
        path="/register"
        element={
          <StandaloneRouteBoundary>
            <RegisterPage />
          </StandaloneRouteBoundary>
        }
      />
      
      <Route
        element={(
          <Shell>
            <RouteOutletBoundary />
          </Shell>
        )}
      >
        <Route path="/" element={<HomePage />} />
        <Route path="/market" element={<MarketPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/portfolio" element={<AlpacaPortfolioPage />} />
        <Route path="/portfolio-legacy" element={<PortfolioPage />} />
        <Route path="/screening" element={<StockScreeningPage />} />
        <Route path="/backtest" element={<BacktestPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
};

import { AuthProvider } from './contexts/AuthContext';

const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Router>
          <AppContent />
        </Router>
      </AuthProvider>
      <Toaster position="top-right" theme="system" richColors />
    </QueryClientProvider>
  );
};

export default App;

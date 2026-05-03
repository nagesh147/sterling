import React, { useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Dashboard } from './pages/Dashboard';
import { ErrorBoundary } from './components/ErrorBoundary';
import { useTheme } from './store/useStore';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 10_000,
    },
  },
});

function ThemedApp() {
  const theme = useTheme();

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  return <Dashboard />;
}

export function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemedApp />
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

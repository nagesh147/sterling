import { useEffect } from 'react';
import { QueryClient, QueryClientProvider, keepPreviousData } from '@tanstack/react-query';
import { Dashboard } from './pages/Dashboard';
import { ErrorBoundary } from './components/ErrorBoundary';
import { useTheme } from './store/useStore';
import { useViewportScale } from './hooks/useViewportScale';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 10_000,
      // Background polling/refetches must not blank the UI. Without these,
      // every refetchInterval tick (and every window-focus refetch) drops the
      // panel's data to `undefined`, so the whole page flashes its loading/empty
      // state and snaps back — indistinguishable from a full page reload.
      placeholderData: keepPreviousData, // keep last data visible while refetching
      refetchOnWindowFocus: false,       // don't refetch-storm every query on focus
    },
  },
});

function ThemedApp() {
  const theme = useTheme();
  // Keeps the layout on its design width whatever the monitor hands us.
  useViewportScale();

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.style.colorScheme = theme === 'light' ? 'light' : 'dark';
  }, [theme]);

  // Single root view. Dashboard internally toggles between basic/pro layouts
  // via the `appMode` Zustand selector (see useStore.useAppMode).
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

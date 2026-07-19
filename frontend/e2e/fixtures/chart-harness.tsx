import React from 'react';
import { createRoot } from 'react-dom/client';
import { keepPreviousData, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { InstrumentPane } from '../../src/components/kite/InstrumentPane';

const client = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      placeholderData: keepPreviousData,
    },
  },
});

document.body.style.margin = '0';
document.body.style.background = '#f5f5f5';

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <div style={{ width: '1180px', height: '760px', padding: '16px', boxSizing: 'border-box' }}>
        <InstrumentPane symbol="NSE:AAA" />
      </div>
    </QueryClientProvider>
  </React.StrictMode>,
);

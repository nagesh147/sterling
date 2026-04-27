import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import type { RunOnceResponse } from '../types';

export function useRunOnce() {
  const qc = useQueryClient();
  return useMutation<RunOnceResponse, Error, string>({
    mutationFn: (underlying: string) =>
      api.post<RunOnceResponse>(
        `/api/v1/directional/run-once?underlying=${underlying}`
      ),
    onSuccess: (data) => {
      // Refresh eval history and session stats after a run
      qc.invalidateQueries({ queryKey: ['eval-history', data.underlying] });
      qc.invalidateQueries({ queryKey: ['session-stats'] });
      // If arrow fired, refresh arrow history
      const sig = data.signal as Record<string, unknown> | undefined;
      if (sig?.green_arrow || sig?.red_arrow) {
        qc.invalidateQueries({ queryKey: ['arrows', data.underlying] });
        qc.invalidateQueries({ queryKey: ['arrows-all'] });
      }
    },
  });
}

import { useMutation } from '@tanstack/react-query';
import { api } from '../utils/api';
import type { RunOnceResponse } from '../types';

export function useRunOnce() {
  return useMutation<RunOnceResponse, Error, string>({
    mutationFn: (underlying: string) =>
      api.post<RunOnceResponse>(
        `/api/v1/directional/run-once?underlying=${underlying}`
      ),
  });
}

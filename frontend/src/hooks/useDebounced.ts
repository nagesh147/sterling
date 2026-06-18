import { useEffect, useState } from 'react';

/**
 * Debounce a value so rapidly-changing input (e.g. a search box) only propagates
 * after the user pauses for `ms`. Critical for the instrument search: without it,
 * every keystroke fires a new /instruments request, each of which is a heavy
 * full-dump filter on the backend.
 */
export function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

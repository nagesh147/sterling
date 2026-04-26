const BASE = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000';

export async function downloadCSV(path: string, filename: string) {
  const resp = await fetch(`${BASE}${path}`);
  if (!resp.ok) throw new Error(`Download failed: ${resp.statusText}`);
  const text = await resp.text();
  const blob = new Blob([text], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const CRYPTO_TAB_VISIBILITY_KEY = 'sterling_show_crypto_tab';
export const CRYPTO_TAB_VISIBILITY_EVENT = 'sterling_show_crypto_tab_change';

export function readCryptoTabVisible(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return window.localStorage.getItem(CRYPTO_TAB_VISIBILITY_KEY) === 'true';
  } catch {
    return false;
  }
}

export function setCryptoTabVisible(visible: boolean): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(CRYPTO_TAB_VISIBILITY_KEY, String(visible));
  } catch {
    // Storage can be unavailable in private/restricted contexts; still update listeners.
  }
  window.dispatchEvent(new CustomEvent(CRYPTO_TAB_VISIBILITY_EVENT, { detail: visible }));
}

/**
 * Injects the theme token stylesheet.
 *
 * The tokens live in TypeScript rather than a .css file because the light and
 * dark value of each one belong side by side — split across two files they
 * drift, and a token that exists in only one theme is invisible until someone
 * switches.
 */
import { themeCss } from './theme';

const ELEMENT_ID = 'sterling-theme-tokens';

export function installThemeStylesheet(): void {
  if (typeof document === 'undefined') return;
  if (document.getElementById(ELEMENT_ID)) return;
  const style = document.createElement('style');
  style.id = ELEMENT_ID;
  style.textContent = themeCss();
  // First child of <head> so any stylesheet can still override a token, and so
  // the variables exist before the first rule that reads one.
  document.head.prepend(style);
}

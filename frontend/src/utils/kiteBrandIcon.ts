export type KiteBrandIcon = 'phoenix' | 'terminal';

export const KITE_BRAND_ICON_OPTIONS: Array<{
  value: KiteBrandIcon;
  label: string;
  description: string;
  href: string;
}> = [
  {
    value: 'phoenix',
    label: 'Phoenix',
    description: 'Clean 🐦‍🔥 icon only — transparent, no square or white background.',
    href: '/favicon.svg?v=6',
  },
  {
    value: 'terminal',
    label: 'Terminal',
    description: 'Sterling terminal prompt icon.',
    href: '/favicon-terminal.svg?v=1',
  },
];

export function normalizeKiteBrandIcon(value: unknown): KiteBrandIcon {
  return value === 'terminal' ? 'terminal' : 'phoenix';
}

export function getKiteBrandIconOption(value: unknown) {
  const icon = normalizeKiteBrandIcon(value);
  return KITE_BRAND_ICON_OPTIONS.find((o) => o.value === icon) ?? KITE_BRAND_ICON_OPTIONS[0];
}

function upsertLink(rel: string, href: string, type?: string): void {
  const selector = `link[rel="${rel}"]`;
  let link = document.head.querySelector<HTMLLinkElement>(selector);
  if (!link) {
    link = document.createElement('link');
    link.rel = rel;
    document.head.appendChild(link);
  }
  link.setAttribute('href', href);
  if (type) link.type = type;
  else link.removeAttribute('type');
}

export function applyKiteBrandIcon(value: unknown): void {
  if (typeof document === 'undefined') return;
  const icon = getKiteBrandIconOption(value);

  upsertLink('icon', icon.href, 'image/svg+xml');
  upsertLink('shortcut icon', icon.href, 'image/svg+xml');
  upsertLink('apple-touch-icon', icon.href);

  const og = document.head.querySelector<HTMLMetaElement>('meta[property="og:image"]');
  if (og) og.setAttribute('content', icon.href);
}

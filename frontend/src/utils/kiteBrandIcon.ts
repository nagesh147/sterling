const EMOJI_BRAND_ICONS = [
  { value: 'phoenix', label: 'Phoenix', emoji: '🐦‍🔥', description: 'Clean phoenix icon — transparent, no square, no white background.' },
  { value: 'kite', label: 'Kite', emoji: '🪁', description: 'Kite-style market icon.' },
  { value: 'chart', label: 'Chart', emoji: '📈', description: 'Bullish chart icon.' },
  { value: 'candles', label: 'Candles', emoji: '🕯️', description: 'Candlestick trading icon.' },
  { value: 'target', label: 'Target', emoji: '🎯', description: 'Strategy target icon.' },
  { value: 'rocket', label: 'Rocket', emoji: '🚀', description: 'Momentum / breakout icon.' },
  { value: 'bolt', label: 'Bolt', emoji: '⚡', description: 'Fast execution icon.' },
  { value: 'fire', label: 'Fire', emoji: '🔥', description: 'Hot market icon.' },
  { value: 'diamond', label: 'Diamond', emoji: '💎', description: 'Premium / conviction icon.' },
  { value: 'compass', label: 'Compass', emoji: '🧭', description: 'Direction and navigation icon.' },
  { value: 'radar', label: 'Radar', emoji: '📡', description: 'Market scan icon.' },
  { value: 'satellite', label: 'Satellite', emoji: '🛰️', description: 'Live signal monitor icon.' },
  { value: 'shield', label: 'Shield', emoji: '🛡️', description: 'Risk guard icon.' },
  { value: 'trophy', label: 'Trophy', emoji: '🏆', description: 'Performance icon.' },
  { value: 'bank', label: 'Bank', emoji: '🏦', description: 'Finance / broker icon.' },
  { value: 'money', label: 'Money', emoji: '💹', description: 'Market movement icon.' },
  { value: 'gem', label: 'Gem', emoji: '🔷', description: 'Clean blue gem icon.' },
  { value: 'sparkles', label: 'Sparkles', emoji: '✨', description: 'Polished UI icon.' },
  { value: 'owl', label: 'Owl', emoji: '🦉', description: 'Watchful market icon.' },
  { value: 'eagle', label: 'Eagle', emoji: '🦅', description: 'Sharp-eye trading icon.' },
  { value: 'lion', label: 'Lion', emoji: '🦁', description: 'Bold trader icon.' },
  { value: 'tiger', label: 'Tiger', emoji: '🐯', description: 'Aggressive market icon.' },
  { value: 'unicorn', label: 'Unicorn', emoji: '🦄', description: 'Unique setup icon.' },
  { value: 'brain', label: 'Brain', emoji: '🧠', description: 'AI / strategy intelligence icon.' },
  { value: 'gear', label: 'Gear', emoji: '⚙️', description: 'Automation settings icon.' },
  { value: 'crystal', label: 'Crystal', emoji: '🔮', description: 'Forecast / signal icon.' },
  { value: 'star', label: 'Star', emoji: '⭐', description: 'Favorite icon.' },
  { value: 'crown', label: 'Crown', emoji: '👑', description: 'Sterling premium icon.' },
] as const;

export type KiteBrandIcon = typeof EMOJI_BRAND_ICONS[number]['value'] | 'terminal';

export type KiteBrandIconOption = {
  value: KiteBrandIcon;
  label: string;
  description: string;
  href: string;
  emoji?: string;
};

function emojiIconDataUri(emoji: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img"><text x="32" y="55" text-anchor="middle" font-size="58" font-family="Apple Color Emoji, Segoe UI Emoji, Noto Color Emoji, sans-serif">${emoji}</text></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

export const KITE_BRAND_ICON_OPTIONS: KiteBrandIconOption[] = [
  ...EMOJI_BRAND_ICONS.map((icon) => ({
    ...icon,
    href: icon.value === 'phoenix' ? '/favicon.svg?v=7' : emojiIconDataUri(icon.emoji),
  })),
  {
    value: 'terminal',
    label: 'Terminal',
    description: 'Sterling terminal prompt icon.',
    href: '/favicon-terminal.svg?v=1',
  },
];

export function normalizeKiteBrandIcon(value: unknown): KiteBrandIcon {
  return KITE_BRAND_ICON_OPTIONS.some((o) => o.value === value) ? value as KiteBrandIcon : 'phoenix';
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

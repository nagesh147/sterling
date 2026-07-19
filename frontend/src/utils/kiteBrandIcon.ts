const EMOJI_BRAND_ICONS = [
  { value: 'phoenix', label: 'Phoenix', emoji: '🐦‍🔥', description: '' },
  { value: 'kite', label: 'Kite', emoji: '🪁', description: '' },
  { value: 'chart', label: 'Chart', emoji: '📈', description: '' },
  { value: 'candles', label: 'Candles', emoji: '🕯️', description: '' },
  { value: 'target', label: 'Target', emoji: '🎯', description: '' },
  { value: 'rocket', label: 'Rocket', emoji: '🚀', description: '' },
  { value: 'bolt', label: 'Bolt', emoji: '⚡', description: '' },
  { value: 'fire', label: 'Fire', emoji: '🔥', description: '' },
  { value: 'diamond', label: 'Diamond', emoji: '💎', description: '' },
  { value: 'compass', label: 'Compass', emoji: '🧭', description: '' },
  { value: 'radar', label: 'Radar', emoji: '📡', description: '' },
  { value: 'satellite', label: 'Satellite', emoji: '🛰️', description: '' },
  { value: 'shield', label: 'Shield', emoji: '🛡️', description: '' },
  { value: 'trophy', label: 'Trophy', emoji: '🏆', description: '' },
  { value: 'bank', label: 'Bank', emoji: '🏦', description: '' },
  { value: 'money', label: 'Money', emoji: '💹', description: '' },
  { value: 'gem', label: 'Gem', emoji: '🔷', description: '' },
  { value: 'sparkles', label: 'Sparkles', emoji: '✨', description: '' },
  { value: 'owl', label: 'Owl', emoji: '🦉', description: '' },
  { value: 'eagle', label: 'Eagle', emoji: '🦅', description: '' },
  { value: 'lion', label: 'Lion', emoji: '🦁', description: '' },
  { value: 'tiger', label: 'Tiger', emoji: '🐯', description: '' },
  { value: 'unicorn', label: 'Unicorn', emoji: '🦄', description: '' },
  { value: 'brain', label: 'Brain', emoji: '🧠', description: '' },
  { value: 'gear', label: 'Gear', emoji: '⚙️', description: '' },
  { value: 'crystal', label: 'Crystal', emoji: '🔮', description: '' },
  { value: 'star', label: 'Star', emoji: '⭐', description: '' },
  { value: 'crown', label: 'Crown', emoji: '👑', description: '' },
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
    description: '',
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
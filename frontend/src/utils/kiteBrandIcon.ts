export type KiteBrandIconSize = 'small' | 'medium' | 'large' | 'xlarge';

export const KITE_BRAND_ICON_SIZES: Array<{ value: KiteBrandIconSize; label: string }> = [
  { value: 'small', label: 'Small' },
  { value: 'medium', label: 'Medium' },
  { value: 'large', label: 'Large' },
  { value: 'xlarge', label: 'Extra Large' },
];

const ICON_SIZE_META: Record<KiteBrandIconSize, { fontSize: number; y: number }> = {
  small: { fontSize: 42, y: 49 },
  medium: { fontSize: 52, y: 53 },
  large: { fontSize: 60, y: 56 },
  xlarge: { fontSize: 66, y: 58 },
};

const EMOJI_BRAND_ICONS = [
  // Sterling
  { value: 'phoenix', label: 'Phoenix', emoji: '🐦‍🔥', category: 'Sterling' },
  { value: 'crown', label: 'Crown', emoji: '👑', category: 'Sterling' },
  { value: 'gem', label: 'Gem', emoji: '🔷', category: 'Sterling' },
  { value: 'diamond', label: 'Diamond', emoji: '💎', category: 'Sterling' },
  { value: 'sparkles', label: 'Sparkles', emoji: '✨', category: 'Sterling' },
  { value: 'star', label: 'Star', emoji: '⭐', category: 'Sterling' },

  // Markets
  { value: 'chart-up', label: 'Chart Up', emoji: '📈', category: 'Markets' },
  { value: 'chart-down', label: 'Chart Down', emoji: '📉', category: 'Markets' },
  { value: 'money-chart', label: 'Money Chart', emoji: '💹', category: 'Markets' },
  { value: 'candles', label: 'Candles', emoji: '🕯️', category: 'Markets' },
  { value: 'bank', label: 'Bank', emoji: '🏦', category: 'Markets' },
  { value: 'exchange', label: 'Exchange', emoji: '💱', category: 'Markets' },
  { value: 'briefcase', label: 'Briefcase', emoji: '💼', category: 'Markets' },
  { value: 'receipt', label: 'Receipt', emoji: '🧾', category: 'Markets' },
  { value: 'coin', label: 'Coin', emoji: '🪙', category: 'Markets' },
  { value: 'rupee', label: 'Rupee', emoji: '₹', category: 'Markets' },

  // Momentum
  { value: 'rocket', label: 'Rocket', emoji: '🚀', category: 'Momentum' },
  { value: 'bolt', label: 'Bolt', emoji: '⚡', category: 'Momentum' },
  { value: 'fire', label: 'Fire', emoji: '🔥', category: 'Momentum' },
  { value: 'boom', label: 'Boom', emoji: '💥', category: 'Momentum' },
  { value: 'comet', label: 'Comet', emoji: '☄️', category: 'Momentum' },
  { value: 'tornado', label: 'Tornado', emoji: '🌪️', category: 'Momentum' },
  { value: 'cyclone', label: 'Cyclone', emoji: '🌀', category: 'Momentum' },
  { value: 'runner', label: 'Runner', emoji: '🏃', category: 'Momentum' },

  // Strategy
  { value: 'target', label: 'Target', emoji: '🎯', category: 'Strategy' },
  { value: 'compass', label: 'Compass', emoji: '🧭', category: 'Strategy' },
  { value: 'radar', label: 'Radar', emoji: '📡', category: 'Strategy' },
  { value: 'satellite', label: 'Satellite', emoji: '🛰️', category: 'Strategy' },
  { value: 'telescope', label: 'Telescope', emoji: '🔭', category: 'Strategy' },
  { value: 'microscope', label: 'Microscope', emoji: '🔬', category: 'Strategy' },
  { value: 'brain', label: 'Brain', emoji: '🧠', category: 'Strategy' },
  { value: 'crystal', label: 'Crystal', emoji: '🔮', category: 'Strategy' },
  { value: 'magnet', label: 'Magnet', emoji: '🧲', category: 'Strategy' },
  { value: 'kite', label: 'Kite', emoji: '🪁', category: 'Strategy' },

  // Risk
  { value: 'shield', label: 'Shield', emoji: '🛡️', category: 'Risk' },
  { value: 'lock', label: 'Lock', emoji: '🔒', category: 'Risk' },
  { value: 'key', label: 'Key', emoji: '🔑', category: 'Risk' },
  { value: 'anchor', label: 'Anchor', emoji: '⚓', category: 'Risk' },
  { value: 'helmet', label: 'Helmet', emoji: '⛑️', category: 'Risk' },
  { value: 'warning', label: 'Warning', emoji: '⚠️', category: 'Risk' },
  { value: 'stop', label: 'Stop', emoji: '🛑', category: 'Risk' },
  { value: 'lifebuoy', label: 'Lifebuoy', emoji: '🛟', category: 'Risk' },

  // Winners
  { value: 'trophy', label: 'Trophy', emoji: '🏆', category: 'Winners' },
  { value: 'medal', label: 'Medal', emoji: '🏅', category: 'Winners' },
  { value: 'first', label: 'First', emoji: '🥇', category: 'Winners' },
  { value: 'gold', label: 'Gold', emoji: '🟡', category: 'Winners' },
  { value: 'party', label: 'Party', emoji: '🎉', category: 'Winners' },
  { value: 'confetti', label: 'Confetti', emoji: '🎊', category: 'Winners' },
  { value: 'clap', label: 'Clap', emoji: '👏', category: 'Winners' },
  { value: 'muscle', label: 'Muscle', emoji: '💪', category: 'Winners' },

  // Animals
  { value: 'eagle', label: 'Eagle', emoji: '🦅', category: 'Animals' },
  { value: 'owl', label: 'Owl', emoji: '🦉', category: 'Animals' },
  { value: 'lion', label: 'Lion', emoji: '🦁', category: 'Animals' },
  { value: 'tiger', label: 'Tiger', emoji: '🐯', category: 'Animals' },
  { value: 'bull', label: 'Bull', emoji: '🐂', category: 'Animals' },
  { value: 'bear', label: 'Bear', emoji: '🐻', category: 'Animals' },
  { value: 'wolf', label: 'Wolf', emoji: '🐺', category: 'Animals' },
  { value: 'unicorn', label: 'Unicorn', emoji: '🦄', category: 'Animals' },
  { value: 'dragon', label: 'Dragon', emoji: '🐉', category: 'Animals' },
  { value: 'falcon', label: 'Falcon', emoji: '🦅', category: 'Animals' },

  // Symbols
  { value: 'green-dot', label: 'Green Dot', emoji: '🟢', category: 'Symbols' },
  { value: 'red-dot', label: 'Red Dot', emoji: '🔴', category: 'Symbols' },
  { value: 'blue-dot', label: 'Blue Dot', emoji: '🔵', category: 'Symbols' },
  { value: 'purple-dot', label: 'Purple Dot', emoji: '🟣', category: 'Symbols' },
  { value: 'orange-dot', label: 'Orange Dot', emoji: '🟠', category: 'Symbols' },
  { value: 'check', label: 'Check', emoji: '✅', category: 'Symbols' },
  { value: 'up', label: 'Up', emoji: '⬆️', category: 'Symbols' },
  { value: 'down', label: 'Down', emoji: '⬇️', category: 'Symbols' },
  { value: 'plus', label: 'Plus', emoji: '➕', category: 'Symbols' },
  { value: 'infinity', label: 'Infinity', emoji: '♾️', category: 'Symbols' },

  // Tools
  { value: 'gear', label: 'Gear', emoji: '⚙️', category: 'Tools' },
  { value: 'wrench', label: 'Wrench', emoji: '🔧', category: 'Tools' },
  { value: 'hammer', label: 'Hammer', emoji: '🔨', category: 'Tools' },
  { value: 'joystick', label: 'Joystick', emoji: '🕹️', category: 'Tools' },
  { value: 'keyboard', label: 'Keyboard', emoji: '⌨️', category: 'Tools' },
  { value: 'laptop', label: 'Laptop', emoji: '💻', category: 'Tools' },
  { value: 'mobile', label: 'Mobile', emoji: '📱', category: 'Tools' },
  { value: 'robot', label: 'Robot', emoji: '🤖', category: 'Tools' },
] as const;

export type KiteBrandIcon = typeof EMOJI_BRAND_ICONS[number]['value'] | 'terminal';
export type KiteBrandIconCategory = typeof EMOJI_BRAND_ICONS[number]['category'] | 'Sterling';

export type KiteBrandIconOption = {
  value: KiteBrandIcon;
  label: string;
  href: string;
  emoji?: string;
  category: KiteBrandIconCategory;
};

function normalizeKiteBrandIconSize(value: unknown): KiteBrandIconSize {
  return value === 'small' || value === 'large' || value === 'xlarge' ? value : 'medium';
}

export { normalizeKiteBrandIconSize };

function emojiIconDataUri(emoji: string, size: KiteBrandIconSize = 'medium'): string {
  const meta = ICON_SIZE_META[normalizeKiteBrandIconSize(size)];
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img"><text x="32" y="${meta.y}" text-anchor="middle" font-size="${meta.fontSize}" font-family="Apple Color Emoji, Segoe UI Emoji, Noto Color Emoji, sans-serif">${emoji}</text></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

export const KITE_BRAND_ICON_OPTIONS: KiteBrandIconOption[] = [
  ...EMOJI_BRAND_ICONS.map((icon) => ({
    ...icon,
    href: emojiIconDataUri(icon.emoji, 'medium'),
  })),
  {
    value: 'terminal',
    label: 'Terminal',
    href: '/favicon-terminal.svg?v=1',
    category: 'Sterling',
  },
];

const CATEGORY_ORDER: KiteBrandIconCategory[] = ['Sterling', 'Markets', 'Momentum', 'Strategy', 'Risk', 'Winners', 'Animals', 'Symbols', 'Tools'];

export const KITE_BRAND_ICON_GROUPS = CATEGORY_ORDER.map((category) => ({
  category,
  options: KITE_BRAND_ICON_OPTIONS.filter((o) => o.category === category),
})).filter((g) => g.options.length > 0);

export function normalizeKiteBrandIcon(value: unknown): KiteBrandIcon {
  return KITE_BRAND_ICON_OPTIONS.some((o) => o.value === value) ? value as KiteBrandIcon : 'phoenix';
}

export function getKiteBrandIconOption(value: unknown) {
  const icon = normalizeKiteBrandIcon(value);
  return KITE_BRAND_ICON_OPTIONS.find((o) => o.value === icon) ?? KITE_BRAND_ICON_OPTIONS[0];
}

export function getKiteBrandIconHref(value: unknown, size: unknown = 'medium'): string {
  const icon = getKiteBrandIconOption(value);
  if (icon.emoji) return emojiIconDataUri(icon.emoji, normalizeKiteBrandIconSize(size));
  return icon.href;
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

export function applyKiteBrandIcon(value: unknown, size: unknown = 'medium'): void {
  if (typeof document === 'undefined') return;
  const href = getKiteBrandIconHref(value, size);

  upsertLink('icon', href, 'image/svg+xml');
  upsertLink('shortcut icon', href, 'image/svg+xml');
  upsertLink('apple-touch-icon', href);

  const og = document.head.querySelector<HTMLMetaElement>('meta[property="og:image"]');
  if (og) og.setAttribute('content', href);
}
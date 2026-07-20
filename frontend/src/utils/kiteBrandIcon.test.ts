import { describe, expect, it } from 'vitest';

import {
  getKiteBrandIconHref,
  getKiteBrandIconOption,
  KITE_BRAND_ICON_GROUPS,
  KITE_BRAND_ICON_OPTIONS,
  normalizeKiteBrandIcon,
} from './kiteBrandIcon';

describe('kiteBrandIcon', () => {
  it('includes the custom Phoenix emblem in the Sterling icon list', () => {
    const option = KITE_BRAND_ICON_OPTIONS.find((item) => item.value === 'phoenix-emblem');

    expect(option).toEqual({
      value: 'phoenix-emblem',
      label: 'Phoenix Emblem',
      href: '/favicon-phoenix-emblem.svg?v=1',
      category: 'Sterling',
    });
    expect(KITE_BRAND_ICON_GROUPS[0]?.category).toBe('Sterling');
    expect(KITE_BRAND_ICON_GROUPS[0]?.options[0]?.value).toBe('phoenix-emblem');
  });

  it('normalizes and resolves the Phoenix emblem as a valid app icon', () => {
    expect(normalizeKiteBrandIcon('phoenix-emblem')).toBe('phoenix-emblem');
    expect(getKiteBrandIconOption('phoenix-emblem').label).toBe('Phoenix Emblem');
    expect(getKiteBrandIconHref('phoenix-emblem', 'xlarge')).toBe('/favicon-phoenix-emblem.svg?v=1');
  });
});

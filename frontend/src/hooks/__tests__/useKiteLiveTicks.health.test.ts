/**
 * The tick socket's own bookkeeping.
 *
 * Two things here, both learned from a live incident where "no values are
 * updating" turned out to be the backend's Kite stream having died while every
 * price quietly fell back to the 30-second REST poll. The delivery path was
 * fine; nothing anywhere said the feed was gone.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';

describe('the stale-socket race', () => {
  it('a closed socket does not clobber the one that replaced it', () => {
    // `_disconnect()` calls `_ws.close()`, which resolves asynchronously. If a
    // reconnect has installed a new socket by the time the old `onclose` fires,
    // the unguarded handler set `_ws = null` on top of the NEW socket — leaving
    // the tracked reference empty while an orphaned socket held the only live
    // connection, and the next connect opening a third. It shows up as flaky
    // staleness, not as a clean disconnect, which is what makes it hard to see.
    //
    // Asserted on the source: the guard is one line and its absence is silent,
    // whereas driving two overlapping sockets through jsdom tests the mock.
    const src = readSource();
    const onclose = codeOnly(
      src.slice(src.indexOf('socket.onclose'), src.indexOf('socket.onerror')),
    );
    expect(onclose).toContain('if (_ws !== socket) return;');
    // The guard must come BEFORE the null, or it protects nothing. Compared on
    // code with comments stripped: the comment explaining this bug quotes
    // `_ws = null` itself, and matching prose made the first version of this
    // assertion fail against correct code.
    expect(onclose.indexOf('if (_ws !== socket) return;'))
      .toBeLessThan(onclose.indexOf('_ws = null'));
  });
});

describe('feed health', () => {
  beforeEach(() => { vi.resetModules(); });

  it('reports no age before any frame has arrived', async () => {
    const m = await import('../useKiteLiveTicks');
    m.__resetTickFeedHealth();
    expect(m.tickFeedAgeMs(), 'null, not 0 — never-arrived is not just-arrived')
      .toBeNull();
  });

  it('reports the socket as closed when there is none', async () => {
    const m = await import('../useKiteLiveTicks');
    expect(m.tickSocketOpen()).toBe(false);
  });

  it('stamps the frame time even when no price changed', () => {
    // An unchanged frame still proves the feed is alive. Stamping only on change
    // would make a quiet market indistinguishable from a dead stream — which is
    // the exact confusion this exists to remove.
    const src = readSource();
    const handler = codeOnly(
      src.slice(src.indexOf('socket.onmessage'), src.indexOf('socket.onclose')),
    );
    expect(handler.indexOf('_lastFrameAt = Date.now();'))
      .toBeLessThan(handler.indexOf('if (changed) _notify();'));
  });

  it('accepts string instrument tokens on the wire', () => {
    const src = readSource();
    const handler = codeOnly(
      src.slice(src.indexOf('socket.onmessage'), src.indexOf('socket.onclose')),
    );
    expect(handler).toContain('Number(tick?.instrument_token)');
  });
});

/**
 * Read the hook's source; see the note in the race test above.
 *
 * `?raw` is no good for this: vitest stubs those for CSS and, for a .ts module,
 * would import the module itself rather than its text. There is no @types/node
 * in this tsconfig, hence the narrow suppression — `readFileSync` is the only
 * thing needed from it. Paths are relative to the working directory, which
 * vitest sets to the package root.
 */
// @ts-expect-error - no @types/node; see above.
import { readFileSync } from 'node:fs';

function readSource(): string {
  for (const p of ['src/hooks/useKiteLiveTicks.ts', 'frontend/src/hooks/useKiteLiveTicks.ts']) {
    try { return readFileSync(p, 'utf8') as string; } catch { /* try the next root */ }
  }
  throw new Error('useKiteLiveTicks.ts not found from the test working directory');
}

/** The same text with `//` comment lines removed, so prose cannot match. */
function codeOnly(src: string): string {
  return src
    .split('\n')
    .filter((line) => !line.trim().startsWith('//') && !line.trim().startsWith('*'))
    .join('\n');
}

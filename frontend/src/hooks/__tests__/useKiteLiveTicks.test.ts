import { describe, expect, it } from 'vitest';
import { resolveKiteStreamWsUrl } from '../useKiteLiveTicks';

describe('resolveKiteStreamWsUrl', () => {
  it('uses the current HTTP origin when the production API base is empty', () => {
    expect(resolveKiteStreamWsUrl('', { protocol: 'http:', host: 'sterling.local' } as Location))
      .toBe('ws://sterling.local/api/v1/stream/ws');
  });

  it('uses wss on an HTTPS deployment', () => {
    expect(resolveKiteStreamWsUrl('', { protocol: 'https:', host: 'trade.example.com' } as Location))
      .toBe('wss://trade.example.com/api/v1/stream/ws');
  });

  it('converts an explicit HTTP API host to a websocket host', () => {
    expect(resolveKiteStreamWsUrl('http://localhost:8000'))
      .toBe('ws://localhost:8000/api/v1/stream/ws');
  });

  it('preserves a relative reverse-proxy prefix', () => {
    expect(resolveKiteStreamWsUrl('/backend', { protocol: 'https:', host: 'trade.example.com' } as Location))
      .toBe('wss://trade.example.com/backend/api/v1/stream/ws');
  });
});

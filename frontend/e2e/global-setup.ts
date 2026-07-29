import type { FullConfig } from '@playwright/test';
import { request } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const AUTH_DIR = path.join(__dirname, '.auth');
const STATE_FILE = path.join(AUTH_DIR, 'kite.json');

async function ensureRealKiteAccountAvailable() {
  const baseURL = process.env.E2E_API_URL || 'http://localhost:8000';
  const headers = { 'X-User-Id': 'default' };

  const api = await request.newContext({ baseURL });

  const accountsResp = await api.get('/api/v1/kite/accounts', { headers });
  if (accountsResp.ok()) {
    const accounts: any = await accountsResp.json();
    const active = (accounts.accounts || []).find((a: any) => accounts.active_id === a.id);
    const real = (accounts.accounts || []).find((a: any) => !a.is_paper);
    if (active && !active.is_paper) {
      console.log('[global-setup] Active real Kite account available for default user');
    } else if (real) {
      const activateRes = await api.post(`/api/v1/kite/accounts/${real.id}/activate`, { headers });
      if (activateRes.ok()) {
        console.log('[global-setup] Activated existing real Kite account for default user');
      } else {
        console.warn('[global-setup] Existing real Kite account could not be activated');
      }
    } else if (active) {
      console.warn('[global-setup] Active Kite account is paper; e2e will not create dummy credentials');
    } else {
      console.warn('[global-setup] No active Kite account; e2e will not create dummy credentials');
    }
  } else {
    console.warn('[global-setup] Could not list Kite accounts; e2e will not create dummy credentials');
  }

  await api.dispose();
}

async function globalSetup(config: FullConfig) {
  // Ensure auth dir
  if (!fs.existsSync(AUTH_DIR)) {
    fs.mkdirSync(AUTH_DIR, { recursive: true });
  }

  // Never create or activate dummy Kite credentials here. Kite E2E must run
  // against an existing operator-configured real account or skip/handle 409s.
  await ensureRealKiteAccountAvailable();

  // Optionally pre-warm a browser context + save storageState for frontend persisted bits
  // (localStorage prefs, last tab, etc.). Not strictly required because our main auth is header-based,
  // but useful for "Kite connected" badges and avoiding first-time guards in some tests.
  // We create a minimal state by visiting the KITE surface.
  const { webServer } = config.projects[0]?.use || {};
  // We don't start page here (globalSetup is node), instead rely on first test + extraHTTPHeaders.
  // If you want full browser-seeded state, use a dedicated auth.setup.ts project.

  // Touch an empty state so projects that declare storageState don't fail on first run
  if (!fs.existsSync(STATE_FILE)) {
    fs.writeFileSync(STATE_FILE, JSON.stringify({ cookies: [], origins: [] }, null, 2));
  }

  console.log('[global-setup] Complete. X-User-Id=default.');
}

export default globalSetup;

import type { FullConfig } from '@playwright/test';
import { request } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const AUTH_DIR = path.join(__dirname, '.auth');
const STATE_FILE = path.join(AUTH_DIR, 'kite.json');

async function ensurePaperKiteAccount() {
  const baseURL = process.env.E2E_API_URL || 'http://localhost:8000';
  const headers = { 'X-User-Id': 'default' };

  const api = await request.newContext({ baseURL });

  // 1. List current kite accounts for the test user
  let accountsResp = await api.get('/api/v1/kite/accounts', { headers });
  let accounts: any = { accounts: [] };
  if (accountsResp.ok()) {
    accounts = await accountsResp.json();
  }

  const hasActivePaper = (accounts.accounts || []).some(
    (a: any) => a.is_paper && accounts.active_id === a.id
  );

  if (hasActivePaper) {
    console.log('[global-setup] Paper Kite account already active for default user');
    await api.dispose();
    return;
  }

  // 2. Create a paper account (DUMMY keys are accepted for paper mode)
  const createBody = {
    label: 'E2E-Paper-Kite',
    api_key: 'DUMMYKEYFORTESTS1234',
    api_secret: 'DUMMYSECRETFORTESTS1234',
    is_paper: true,
  };

  const createRes = await api.post('/api/v1/kite/accounts', {
    headers,
    data: createBody,
  });

  let accountId: string | undefined;
  if (createRes.ok()) {
    const created = await createRes.json();
    accountId = created.id;
    console.log('[global-setup] Created paper Kite account', accountId);
  } else {
    // May already exist under another label — list again and pick a paper one
    accountsResp = await api.get('/api/v1/kite/accounts', { headers });
    if (accountsResp.ok()) {
      accounts = await accountsResp.json();
      const paper = (accounts.accounts || []).find((a: any) => a.is_paper);
      accountId = paper?.id;
    }
  }

  if (accountId) {
    // 3. Activate it so engine / status see an active paper account
    const activateRes = await api.post(`/api/v1/kite/accounts/${accountId}/activate`, {
      headers,
    });
    if (activateRes.ok()) {
      console.log('[global-setup] Activated paper Kite account for e2e');
    }
  } else {
    console.warn('[global-setup] Could not ensure paper Kite account (continuing; some kite flows may 409)');
  }

  // Optional: test the account (paper will report nicely)
  if (accountId) {
    await api.post(`/api/v1/kite/accounts/${accountId}/test`, { headers }).catch(() => {});
  }

  await api.dispose();
}

async function globalSetup(config: FullConfig) {
  // Ensure auth dir
  if (!fs.existsSync(AUTH_DIR)) {
    fs.mkdirSync(AUTH_DIR, { recursive: true });
  }

  // Seed server-side paper kite account + activation for "default" user.
  // This solves get_current_user + "no active kite account" errors for engine/kite e2e flows.
  await ensurePaperKiteAccount();

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

  console.log('[global-setup] Complete. X-User-Id=default + paper kite ensured.');
}

export default globalSetup;

export interface TrueDataCredential {
  id: string;
  user_id: string;
  label: string;
  username_hint: string;
  has_credentials: boolean;
  connected: boolean;
  is_active: boolean;
  realtime_port: number;
  last_login_at_ms?: number;
  created_at_ms: number;
  updated_at_ms: number;
}

export interface TrueDataCredentialCreate {
  label?: string;
  username: string;
  password: string;
  realtime_port?: number;
}

export interface TrueDataCredentialUpdate {
  label?: string;
  username?: string;
  password?: string;
  realtime_port?: number;
}

export interface TrueDataStatus {
  connected: boolean;
  is_active: boolean;
  account_id?: string;
  username_hint?: string;
  message: string;
}

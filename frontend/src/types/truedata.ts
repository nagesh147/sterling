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

export type MarketDataSource = 'truedata' | 'zerodhakite';

export interface TrueDataSettings {
  data_source: MarketDataSource;
}

export type DiagnosticStatus = 'PASS' | 'FAIL' | 'WARNING' | 'IDLE' | 'TESTING' | 'PARTIAL';

export interface DiagnosticFieldCheck {
  name: string;
  status: DiagnosticStatus;
  value: string | number;
  description: string;
}

export interface DiagnosticCategoryResult {
  id: string;
  name: string;
  icon: string;
  status: DiagnosticStatus;
  latency_ms: number;
  source_origin: 'live_truedata' | 'sterling_lake' | 'synthetic_fallback' | 'analytical_engine' | 'microstructure_engine';
  symbol_tested: string;
  summary: string;
  metrics: Record<string, any>;
  field_checks: DiagnosticFieldCheck[];
  raw_sample: Record<string, any>;
  error_message?: string | null;
  troubleshooting_tip?: string | null;
}

export interface DiagnosticSuiteResult {
  timestamp: string;
  overall_status: 'PASS' | 'PARTIAL' | 'FAIL' | 'WARNING';
  total_tests: number;
  passed_count: number;
  warning_count: number;
  failed_count: number;
  total_duration_ms: number;
  authenticated: boolean;
  username_hint?: string | null;
  categories: DiagnosticCategoryResult[];
}


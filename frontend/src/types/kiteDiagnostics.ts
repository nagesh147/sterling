export type KiteDiagnosticStatus = 'PASS' | 'FAIL' | 'WARNING' | 'IDLE' | 'PARTIAL';

export interface KiteDiagnosticFieldCheck {
  name: string;
  status: KiteDiagnosticStatus;
  value: string | number;
  description: string;
}

export interface KiteDiagnosticCategoryResult {
  id: string;
  name: string;
  icon: string;
  status: KiteDiagnosticStatus;
  latency_ms: number;
  source_origin: string;
  symbol_tested: string;
  summary: string;
  metrics: Record<string, any>;
  field_checks: KiteDiagnosticFieldCheck[];
  raw_sample: Record<string, any>;
  error_message?: string | null;
  troubleshooting_tip?: string | null;
}

export interface KiteDiagnosticSuiteResult {
  timestamp: string;
  overall_status: KiteDiagnosticStatus;
  total_tests: number;
  passed_count: number;
  warning_count: number;
  failed_count: number;
  total_duration_ms: number;
  authenticated: boolean;
  account_label?: string | null;
  kite_user_id?: string | null;
  is_paper: boolean;
  categories: KiteDiagnosticCategoryResult[];
}

export interface KiteDiagnosticsSummary {
  authenticated: boolean;
  account_label?: string | null;
  kite_user_id?: string | null;
  is_paper: boolean;
  has_credentials: boolean;
}

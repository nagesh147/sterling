import { create } from 'zustand';

const STORAGE_KEY = 'sterling_underlying';
const THEME_KEY = 'sterling_theme';
const THEME_DEFAULT_MIGRATION_KEY = 'sterling_theme_default_migrated_v1';
const MODE_KEY = 'sterling_app_mode';

type Theme = 'dark' | 'grey' | 'light';

const DEFAULT_THEME: Theme = 'light';
const THEME_CYCLE: Theme[] = ['light', 'dark', 'grey'];

function isTheme(value: string | null): value is Theme
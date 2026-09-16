export const UI_PREFERENCES_STORAGE_KEY = 'artemis.ui.preferences.v1';
export const UI_PREFERENCES_VERSION = 1 as const;
export type UiLanguage = 'en' | 'vi';
export type UiTheme = 'light' | 'dark';
export interface UiPreferences { version: typeof UI_PREFERENCES_VERSION; language: UiLanguage; theme: UiTheme }
export const DEFAULT_UI_PREFERENCES: UiPreferences = { version: 1, language: 'en', theme: 'light' };
export const UI_PREFERENCES_BOOTSTRAP = "(()=>{try{const p=JSON.parse(localStorage.getItem('artemis.ui.preferences.v1')||'null');if(p&&p.version===1){document.documentElement.dataset.theme=p.theme==='dark'?'dark':'light';document.documentElement.lang=p.language==='vi'?'vi':'en'}}catch{}})()";

export function validateUiPreferences(value: unknown): UiPreferences {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return { ...DEFAULT_UI_PREFERENCES };
  const candidate = value as Record<string, unknown>;
  if (candidate.version !== UI_PREFERENCES_VERSION) return { ...DEFAULT_UI_PREFERENCES };
  return { version: UI_PREFERENCES_VERSION, language: candidate.language === 'vi' || candidate.language === 'en' ? candidate.language : 'en', theme: candidate.theme === 'dark' || candidate.theme === 'light' ? candidate.theme : 'light' };
}

export function parseUiPreferences(serialized: string | null): UiPreferences {
  if (serialized === null) return { ...DEFAULT_UI_PREFERENCES };
  try { return validateUiPreferences(JSON.parse(serialized)); } catch { return { ...DEFAULT_UI_PREFERENCES }; }
}

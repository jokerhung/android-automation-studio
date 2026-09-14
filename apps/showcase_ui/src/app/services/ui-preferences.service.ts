import { DOCUMENT } from '@angular/common';
import { Inject, Injectable, InjectionToken, OnDestroy, computed, signal } from '@angular/core';

export const UI_PREFERENCES_STORAGE_KEY = 'artemis.ui.preferences.v1';
export const UI_PREFERENCES_VERSION = 1 as const;
export type UiLanguage = 'en' | 'vi';
export type UiTheme = 'light' | 'dark';

export interface UiPreferences {
  version: typeof UI_PREFERENCES_VERSION;
  language: UiLanguage;
  theme: UiTheme;
}

export interface PreferenceUpdateResult {
  preferences: UiPreferences;
  persisted: boolean;
}

export const DEFAULT_UI_PREFERENCES: UiPreferences = {
  version: UI_PREFERENCES_VERSION,
  language: 'en',
  theme: 'light'
};

export const UI_PREFERENCES_WINDOW = new InjectionToken<Window | null>('UI_PREFERENCES_WINDOW', {
  providedIn: 'root',
  factory: () => typeof window === 'undefined' ? null : window
});

export function validateUiPreferences(value: unknown): UiPreferences {
  if (!value || typeof value !== 'object') return { ...DEFAULT_UI_PREFERENCES };
  const candidate = value as Record<string, unknown>;
  if (candidate['version'] !== UI_PREFERENCES_VERSION) return { ...DEFAULT_UI_PREFERENCES };
  return {
    version: UI_PREFERENCES_VERSION,
    language: candidate['language'] === 'vi' || candidate['language'] === 'en'
      ? candidate['language'] : DEFAULT_UI_PREFERENCES.language,
    theme: candidate['theme'] === 'dark' || candidate['theme'] === 'light'
      ? candidate['theme'] : DEFAULT_UI_PREFERENCES.theme
  };
}

export function parseUiPreferences(serialized: string | null): UiPreferences {
  if (serialized === null) return { ...DEFAULT_UI_PREFERENCES };
  try { return validateUiPreferences(JSON.parse(serialized)); }
  catch { return { ...DEFAULT_UI_PREFERENCES }; }
}

@Injectable({ providedIn: 'root' })
export class UiPreferencesService implements OnDestroy {
  private readonly state = signal<UiPreferences>({ ...DEFAULT_UI_PREFERENCES });
  private readonly storageListener = (event: StorageEvent): void => {
    if (event.key !== UI_PREFERENCES_STORAGE_KEY) return;
    this.apply(parseUiPreferences(event.newValue));
  };

  readonly preferences = this.state.asReadonly();
  readonly language = computed(() => this.state().language);
  readonly theme = computed(() => this.state().theme);

  constructor(
    @Inject(DOCUMENT) private readonly document: Document,
    @Inject(UI_PREFERENCES_WINDOW) private readonly browserWindow: Window | null
  ) {
    this.apply(this.readStored());
    this.browserWindow?.addEventListener('storage', this.storageListener);
  }

  setLanguage(language: UiLanguage): PreferenceUpdateResult {
    return this.update({ language });
  }

  setTheme(theme: UiTheme): PreferenceUpdateResult {
    return this.update({ theme });
  }

  ngOnDestroy(): void {
    this.browserWindow?.removeEventListener('storage', this.storageListener);
  }

  private update(patch: Partial<Pick<UiPreferences, 'language' | 'theme'>>): PreferenceUpdateResult {
    const base = this.readStored(this.state());
    const preferences = validateUiPreferences({ ...base, ...patch, version: UI_PREFERENCES_VERSION });
    this.apply(preferences);
    let persisted = false;
    try {
      if (this.browserWindow) {
        this.browserWindow.localStorage.setItem(UI_PREFERENCES_STORAGE_KEY, JSON.stringify(preferences));
        persisted = true;
      }
    } catch {
      // The in-memory preference remains active when storage is unavailable.
    }
    return { preferences, persisted };
  }

  private readStored(fallback: UiPreferences = DEFAULT_UI_PREFERENCES): UiPreferences {
    try {
      if (!this.browserWindow) return { ...fallback };
      return parseUiPreferences(this.browserWindow.localStorage.getItem(UI_PREFERENCES_STORAGE_KEY));
    } catch {
      return { ...fallback };
    }
  }

  private apply(preferences: UiPreferences): void {
    this.state.set(preferences);
    const root = this.document.documentElement;
    root.lang = preferences.language;
    root.dataset['theme'] = preferences.theme;
  }
}

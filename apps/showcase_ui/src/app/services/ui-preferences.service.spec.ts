import { TestBed } from '@angular/core/testing';
import {
  DEFAULT_UI_PREFERENCES,
  UI_PREFERENCES_STORAGE_KEY,
  UI_PREFERENCES_WINDOW,
  UiPreferencesService,
  parseUiPreferences
} from './ui-preferences.service';

class MemoryStorage implements Storage {
  private values = new Map<string, string>();
  get length(): number { return this.values.size; }
  clear(): void { this.values.clear(); }
  getItem(key: string): string | null { return this.values.get(key) ?? null; }
  key(index: number): string | null { return [...this.values.keys()][index] ?? null; }
  removeItem(key: string): void { this.values.delete(key); }
  setItem(key: string, value: string): void { this.values.set(key, value); }
}

class FakeWindow {
  readonly localStorage: Storage = new MemoryStorage();
  private listeners = new Set<(event: StorageEvent) => void>();
  addEventListener(type: string, listener: EventListenerOrEventListenerObject): void {
    if (type === 'storage') this.listeners.add(listener as (event: StorageEvent) => void);
  }
  removeEventListener(type: string, listener: EventListenerOrEventListenerObject): void {
    if (type === 'storage') this.listeners.delete(listener as (event: StorageEvent) => void);
  }
  dispatchStorage(key: string, newValue: string | null): void {
    this.listeners.forEach(listener => listener({ key, newValue } as StorageEvent));
  }
}

describe('UiPreferencesService', () => {
  let fakeWindow: FakeWindow;

  function createService(windowValue: Window | null = fakeWindow as unknown as Window): UiPreferencesService {
    TestBed.configureTestingModule({ providers: [
      UiPreferencesService,
      { provide: UI_PREFERENCES_WINDOW, useValue: windowValue }
    ] });
    return TestBed.inject(UiPreferencesService);
  }

  beforeEach(() => {
    TestBed.resetTestingModule();
    fakeWindow = new FakeWindow();
    document.documentElement.lang = 'en';
    document.documentElement.dataset['theme'] = 'light';
  });

  it('validates malformed, wrong-version, and partial stored values', () => {
    expect(parseUiPreferences('{bad')).toEqual(DEFAULT_UI_PREFERENCES);
    expect(parseUiPreferences(JSON.stringify({ version: 2, language: 'vi', theme: 'dark' }))).toEqual(DEFAULT_UI_PREFERENCES);
    expect(parseUiPreferences(JSON.stringify({ version: 1, language: 'vi', theme: 'neon' }))).toEqual({ version: 1, language: 'vi', theme: 'light' });
  });

  it('loads valid preferences and applies root language and theme', () => {
    fakeWindow.localStorage.setItem(UI_PREFERENCES_STORAGE_KEY, JSON.stringify({ version: 1, language: 'vi', theme: 'dark' }));
    const service = createService();
    expect(service.preferences()).toEqual({ version: 1, language: 'vi', theme: 'dark' });
    expect(document.documentElement.lang).toBe('vi');
    expect(document.documentElement.dataset['theme']).toBe('dark');
  });

  it('merges a write with the latest storage value', () => {
    const service = createService();
    fakeWindow.localStorage.setItem(UI_PREFERENCES_STORAGE_KEY, JSON.stringify({ version: 1, language: 'en', theme: 'dark' }));
    const result = service.setLanguage('vi');
    expect(result.persisted).toBeTrue();
    expect(JSON.parse(fakeWindow.localStorage.getItem(UI_PREFERENCES_STORAGE_KEY)!)).toEqual({ version: 1, language: 'vi', theme: 'dark' });
  });

  it('applies storage events without writing them back', () => {
    const service = createService();
    const setSpy = spyOn(fakeWindow.localStorage, 'setItem').and.callThrough();
    fakeWindow.dispatchStorage(UI_PREFERENCES_STORAGE_KEY, JSON.stringify({ version: 1, language: 'vi', theme: 'dark' }));
    expect(service.preferences()).toEqual({ version: 1, language: 'vi', theme: 'dark' });
    expect(setSpy).not.toHaveBeenCalled();
  });

  it('ignores unrelated storage events and resets defaults when the preference key is removed', () => {
    const service = createService();
    fakeWindow.dispatchStorage('other.key', JSON.stringify({ version: 1, language: 'vi', theme: 'dark' }));
    expect(service.preferences()).toEqual(DEFAULT_UI_PREFERENCES);

    fakeWindow.dispatchStorage(UI_PREFERENCES_STORAGE_KEY, JSON.stringify({ version: 1, language: 'vi', theme: 'dark' }));
    fakeWindow.dispatchStorage(UI_PREFERENCES_STORAGE_KEY, null);
    expect(service.preferences()).toEqual(DEFAULT_UI_PREFERENCES);
    expect(document.documentElement.lang).toBe('en');
    expect(document.documentElement.dataset['theme']).toBe('light');
  });

  it('keeps changes in memory and reports failure when storage throws', () => {
    const service = createService();
    spyOn(fakeWindow.localStorage, 'getItem').and.throwError('blocked');
    spyOn(fakeWindow.localStorage, 'setItem').and.throwError('blocked');
    const result = service.setTheme('dark');
    expect(result.persisted).toBeFalse();
    expect(service.theme()).toBe('dark');
    expect(document.documentElement.dataset['theme']).toBe('dark');
  });

  it('works without a window and reports non-persistence', () => {
    const service = createService(null);
    const result = service.setLanguage('vi');
    expect(result.persisted).toBeFalse();
    expect(service.language()).toBe('vi');
    expect(document.documentElement.lang).toBe('vi');
  });
});

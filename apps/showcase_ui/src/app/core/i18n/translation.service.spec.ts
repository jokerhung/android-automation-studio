import { TestBed } from '@angular/core/testing';
import { EN_CATALOG } from './en';
import { VI_CATALOG } from './vi';
import { interpolate, t, TranslationService } from './translation.service';
import { UiPreferencesService } from '../../services/ui-preferences.service';

describe('runtime translation catalogs', () => {
  const placeholders = (value: string) => [...value.matchAll(/\{\{\s*([^{}\s]+)\s*\}\}/g)].map(match => match[1]).sort();
  it('keeps EN and VI keys in parity', () => {
    expect(Object.keys(VI_CATALOG).sort()).toEqual(Object.keys(EN_CATALOG).sort());
  });
  it('keeps placeholders in parity', () => {
    for (const key of Object.keys(EN_CATALOG) as (keyof typeof EN_CATALOG)[]) expect(placeholders(VI_CATALOG[key])).withContext(key).toEqual(placeholders(EN_CATALOG[key]));
  });
  it('interpolates values and preserves missing placeholders', () => {
    expect(interpolate('Hello {{name}} / {{missing}}', { name: 'Lan' })).toBe('Hello Lan / {{missing}}');
  });
  it('falls back to English and then the key', () => {
    expect(t({}, 'nav.home')).toBe('Home');
    expect(t({}, 'unknown.key')).toBe('unknown.key');
  });
});

describe('TranslationService', () => {
  let preferences: jasmine.SpyObj<UiPreferencesService>;
  beforeEach(() => {
    let language: 'en' | 'vi' = 'en';
    preferences = jasmine.createSpyObj('UiPreferencesService', ['setLanguage'], { language: () => language });
    TestBed.configureTestingModule({ providers: [TranslationService, { provide: UiPreferencesService, useValue: preferences }] });
  });
  it('delegates locale changes to reactive preferences', () => {
    const service = TestBed.inject(TranslationService);
    service.setLocale('vi');
    expect(preferences.setLanguage).toHaveBeenCalledWith('vi');
  });
});

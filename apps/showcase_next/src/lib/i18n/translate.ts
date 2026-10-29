import { en, type TranslationKey, vi } from './catalogs';
import type { UiLanguage } from '@/lib/preferences/preferences';
export function translate(language: UiLanguage, key: TranslationKey, values: Record<string, string | number | null | undefined> = {}): string {
  const template = (language === 'vi' ? vi[key] : undefined) ?? en[key] ?? key;
  return Object.entries(values).reduce((text, [name, value]) => text.replaceAll(`{{${name}}}`, value == null ? '' : String(value)), template);
}

import { Injectable, computed, inject } from '@angular/core';
import { UiLanguage, UiPreferencesService } from '../../services/ui-preferences.service';
import { EN_CATALOG, TranslationKey } from './en';
import { VI_CATALOG } from './vi';
export type Locale = UiLanguage;
export type TranslationParams = Record<string, string | number | null | undefined>;
export function interpolate(message: string, params: TranslationParams = {}): string { return message.replace(/\{\{\s*([^{}\s]+)\s*\}\}/g, (match, name) => Object.prototype.hasOwnProperty.call(params, name) ? String(params[name] ?? '') : match); }
@Injectable({providedIn:'root'}) export class TranslationService {
 private readonly preferences = inject(UiPreferencesService);
 readonly locale = computed(() => this.preferences.language());
 readonly isVietnamese = computed(() => this.locale() === 'vi');
 setLocale(locale: Locale): void { this.preferences.setLanguage(locale); }
 toggle(): void { this.setLocale(this.locale()==='en'?'vi':'en'); }
 translate(key: TranslationKey | string, params: TranslationParams = {}): string { const catalog=this.locale()==='vi'?VI_CATALOG:EN_CATALOG; const message=(catalog as Record<string,string>)[key] ?? (EN_CATALOG as Record<string,string>)[key] ?? key; return interpolate(message,params); }
}
export const t = (catalog: Record<string,string>, key: string, params?: TranslationParams, fallback: Record<string,string> = EN_CATALOG): string => interpolate(catalog[key] ?? fallback[key] ?? key, params);

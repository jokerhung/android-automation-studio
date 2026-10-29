import type { TranslationKey } from '@/lib/i18n/catalogs';
export const SETTINGS_TABS=[['general','settings.general'],['models','settings.models'],['email','settings.email'],['android','settings.android'],['system','settings.system']] as const satisfies ReadonlyArray<readonly [string,TranslationKey]>;
export type SettingsTab=typeof SETTINGS_TABS[number][0];
export function resolveSettingsTab(value:string|null):SettingsTab{return SETTINGS_TABS.some(([tab])=>tab===value)?value as SettingsTab:'general'}
export function settingsTabHref(tab:SettingsTab):string{return tab==='general'?'/settings/':`/settings/?tab=${tab}`}

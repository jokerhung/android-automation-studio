'use client';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { DEFAULT_UI_PREFERENCES, parseUiPreferences, UI_PREFERENCES_STORAGE_KEY, UI_PREFERENCES_VERSION, type UiLanguage, type UiPreferences, type UiTheme } from '@/lib/preferences/preferences';
import { translate } from '@/lib/i18n/translate';
import type { TranslationKey } from '@/lib/i18n/catalogs';
import { WorkspaceProvider } from '@/features/workspace/provider';

type ContextValue = { preferences: UiPreferences; setLanguage(language: UiLanguage): void; setTheme(theme: UiTheme): void; t(key: TranslationKey, values?: Record<string,string|number|null|undefined>): string };
const PreferencesContext=createContext<ContextValue|null>(null);
function apply(preferences: UiPreferences) { document.documentElement.lang=preferences.language; document.documentElement.dataset.theme=preferences.theme; }
export function AppProviders({children}:{children:ReactNode}) {
  const [preferences,setPreferences]=useState<UiPreferences>(DEFAULT_UI_PREFERENCES);
  useEffect(()=>{ let current=DEFAULT_UI_PREFERENCES; try { current=parseUiPreferences(localStorage.getItem(UI_PREFERENCES_STORAGE_KEY)); } catch { /* memory fallback */ } setPreferences(current); apply(current);
    const sync=(event:StorageEvent)=>{ if(event.key===UI_PREFERENCES_STORAGE_KEY){ const next=parseUiPreferences(event.newValue); setPreferences(next); apply(next); } }; window.addEventListener('storage',sync); return()=>window.removeEventListener('storage',sync); },[]);
  const update=useCallback((patch:Partial<Pick<UiPreferences,'language'|'theme'>>)=>setPreferences(current=>{ let latest=current; try { const stored=localStorage.getItem(UI_PREFERENCES_STORAGE_KEY); if(stored!==null) latest=parseUiPreferences(stored); } catch { /* merge against memory when storage is blocked */ } const next={...latest,...patch,version:UI_PREFERENCES_VERSION}; apply(next); try { localStorage.setItem(UI_PREFERENCES_STORAGE_KEY,JSON.stringify(next)); } catch { /* keep memory state */ } return next; }),[]);
  const value=useMemo<ContextValue>(()=>({preferences,setLanguage:language=>update({language}),setTheme:theme=>update({theme}),t:(key,values)=>translate(preferences.language,key,values)}),[preferences,update]);
  return <PreferencesContext.Provider value={value}><WorkspaceProvider>{children}</WorkspaceProvider></PreferencesContext.Provider>;
}
export function useAppPreferences(): ContextValue { const value=useContext(PreferencesContext); if(!value) throw new Error('useAppPreferences must be used under AppProviders'); return value; }

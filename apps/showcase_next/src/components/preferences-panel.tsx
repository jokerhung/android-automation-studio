'use client';
import { Sun, Moon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { useAppPreferences } from '@/app/providers';
import type { UiLanguage, UiTheme } from '@/lib/preferences/preferences';
export function PreferencesPanel(){
 const {preferences,setLanguage,setTheme,t}=useAppPreferences();
 return <Card className="settingsCard">
   <header className="appearanceHeading"><h2>{t('appearance.title')}</h2><p>{t('appearance.description')}</p></header>
   <div className="settingRow"><div><h3>{t('settings.language')}</h3><p>{t('appearance.languageDescription')}</p></div>
     <select aria-label={t('settings.language')} value={preferences.language} onChange={e=>setLanguage(e.target.value as UiLanguage)}><option value="en">English</option><option value="vi">Tiếng Việt</option></select>
   </div>
   <div className="settingRow"><div><h3>{t('settings.theme')}</h3><p>{t('appearance.themeDescription')}</p></div>
     <div className="themeChoices" role="group" aria-label={t('settings.theme')}>
       {(['light','dark'] as UiTheme[]).map(theme=><Button variant="outline" key={theme} type="button" aria-pressed={preferences.theme===theme} className={preferences.theme===theme?'selected':''} onClick={()=>setTheme(theme)}>{theme==='light'?<Sun size={16}/>:<Moon size={16}/>} {t(theme==='light'?'settings.light':'settings.dark')}</Button>)}
     </div>
   </div>
 </Card>;
}

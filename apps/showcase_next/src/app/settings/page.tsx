'use client';
import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { SlidersHorizontal, Sparkles, Mail, Smartphone, Monitor } from 'lucide-react';
import { PageShell } from '@/components/page-shell';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { useAppPreferences } from '@/app/providers';
import { GeneralSettings, ModelSettingsPanel } from '@/features/settings/general-model-panels';
import { EmailSettingsPanel } from '@/features/settings/email-panel';
import { AndroidSettingsPanel, SystemSettingsPanel } from '@/features/settings/android-system-panels';
import { SETTINGS_TABS, resolveSettingsTab, settingsTabHref, type SettingsTab } from '@/features/settings/tabs';
const icons={general:SlidersHorizontal,models:Sparkles,email:Mail,android:Smartphone,system:Monitor};
function SettingsContent(){
 const params=useSearchParams(); const active=resolveSettingsTab(params.get('tab')); const {t}=useAppPreferences();
 const panels={general:<GeneralSettings/>,models:<ModelSettingsPanel/>,email:<EmailSettingsPanel/>,android:<AndroidSettingsPanel/>,system:<SystemSettingsPanel/>};
 return <Tabs orientation="vertical" value={active} onValueChange={value=>window.history.replaceState(null,'',settingsTabHref(value as SettingsTab))} className="settingsLayout">
   <TabsList className="settingsTabs" aria-label={t('settings.title')}>{SETTINGS_TABS.map(([tab,label])=>{const Icon=icons[tab];return <TabsTrigger key={tab} value={tab}><Icon size={18}/>{t(label)}</TabsTrigger>})}</TabsList>
   <div className="settingsDetail">{SETTINGS_TABS.map(([tab])=><TabsContent forceMount hidden={active!==tab} key={tab} value={tab} className="settingsPanel">{panels[tab]}</TabsContent>)}</div>
 </Tabs>;
}
export default function Settings(){return <PageShell eyebrow="settings.eyebrow" title="settings.title" body="settings.body"><Suspense fallback={<div className="card"/>}><SettingsContent/></Suspense></PageShell>}

'use client';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { X } from 'lucide-react';
import type { TranslationKey } from '@/lib/i18n/catalogs';
import { useAppPreferences } from '@/app/providers';
import { Button } from '@/components/ui/button';
export function PageShell({eyebrow,title,body,children}:{eyebrow:TranslationKey;title:TranslationKey;body:TranslationKey;children:ReactNode}) {
  const {t}=useAppPreferences();
  const kind = title.startsWith('home.') ? 'home' : title.startsWith('settings.') ? 'settings' : 'schedule';
  return <main className={`page ${kind}Page`}>
    <section className="hero"><div>
      {kind === 'schedule' && <span className="eyebrow">{t(eyebrow)}</span>}
      <h1>{t(title)}</h1>
      {kind === 'schedule' && <p>{t(body)}</p>}
    </div>{kind === 'settings' && <Button asChild variant="ghost" size="icon" className="settingsClose"><Link href="/" aria-label={t('common.home')}><X size={18}/></Link></Button>}</section>
    {children}
  </main>;
}
export function EmptyState({title,body,icon='◇'}:{title:TranslationKey;body:TranslationKey;icon?:string}){const {t}=useAppPreferences();return <section className="empty card"><span className="emptyIcon" aria-hidden>{icon}</span><h2>{t(title)}</h2><p>{t(body)}</p></section>}

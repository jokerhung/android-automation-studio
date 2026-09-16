'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Home, PanelsTopLeft, CalendarClock, Settings } from 'lucide-react';
import { useAppPreferences } from '@/app/providers';
import { Button } from '@/components/ui/button';
const items = [['/', 'nav.home', Home], ['/workspace/', 'nav.workspace', PanelsTopLeft], ['/task-schedule/', 'nav.schedule', CalendarClock], ['/settings/', 'nav.settings', Settings]] as const;
export function Navigation() {
  const pathname = usePathname(); const { t } = useAppPreferences();
  return <header className="topbar"><nav className="nav" aria-label={t('nav.main')}>
    {items.map(([href, key, Icon]) => {
      const active = href === '/' ? pathname === '/' : pathname.startsWith(href.replace(/\/$/, ''));
      return <Button asChild variant="ghost" key={href} className={`navLink${active ? ' active' : ''}`}>
        <Link href={href} aria-current={active ? 'page' : undefined}><Icon size={16} aria-hidden="true"/><span>{t(key)}</span></Link>
      </Button>;
    })}
  </nav></header>;
}

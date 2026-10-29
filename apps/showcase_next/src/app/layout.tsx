import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { AppProviders } from './providers';
import { Navigation } from '@/components/navigation';
import { UI_PREFERENCES_BOOTSTRAP } from '@/lib/preferences/preferences';
import '@fontsource/inter/latin-400.css';
import '@fontsource/inter/latin-500.css';
import '@fontsource/inter/latin-600.css';
import '@fontsource/inter/vietnamese-400.css';
import '@fontsource/inter/vietnamese-500.css';
import '@fontsource/inter/vietnamese-600.css';
import '@fontsource/outfit/latin-600.css';
import './shadcn.css';
import './angular-tokens.css';
import './globals.css';
import './angular-parity.css';

export const metadata: Metadata={title:{default:'AAS',template:'%s · AAS'},description:'AAS Android agent operations console'};
export default function RootLayout({children}:{children:ReactNode}){return <html lang="en" data-theme="light" suppressHydrationWarning><head><script id="artemis-preferences-bootstrap" dangerouslySetInnerHTML={{__html:UI_PREFERENCES_BOOTSTRAP}}/></head><body><AppProviders><Navigation/>{children}</AppProviders></body></html>}

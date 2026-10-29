import type { Metadata } from 'next';
import { Suspense } from 'react';
import { WorkspaceClient } from '@/features/workspace/components/workspace-client';

export const metadata: Metadata = { title: 'Workspace' };
export default function WorkspacePage() { return <Suspense fallback={<main className="workspace-page"><p>Loading workspace…</p></main>}><WorkspaceClient/></Suspense>; }

import type { Metadata } from 'next';
import { LegacyCheck } from '@/features/legacy-check/legacy-check';

export const metadata: Metadata = { title: 'Legacy Check' };

export default function CheckPage() {
  return <LegacyCheck />;
}

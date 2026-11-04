import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SessionDetailsPanel } from '@/features/workspace/components/workspace-panels';
import type { SessionDetails } from '@/features/workspace/types';

const loadSessionDetails = vi.hoisted(() => vi.fn());
vi.mock('@/app/providers', async () => {
  const { translate } = await import('@/lib/i18n/translate');
  return { useAppPreferences: () => ({ preferences: { language: 'en' }, t: (key: Parameters<typeof translate>[1]) => translate('en', key) }) };
});
vi.mock('@/features/workspace/provider', async () => {
  const { initialWorkspaceState } = await import('@/features/workspace/reducer');
  return { useWorkspace: () => ({ state: initialWorkspaceState, loadSessionDetails }) };
});

const details: SessionDetails = {
  session: { session_id: 's', status: 'completed' }, steps: [], checks: [], notes: null, usage: null, startup: [], video: null,
} as unknown as SessionDetails;
const tab = (name: string) => screen.queryByRole('tab', { name });

describe('Session details tabs', () => {
  it('offers the realtime Running tab only while the task is active', () => {
    render(<SessionDetailsPanel details={details} isRunning sessionId="s" />);
    expect(tab('Running')).toBeInTheDocument();
    expect(tab('Running')).toHaveAttribute('aria-selected', 'true');
    expect(tab('logs')).toBeDisabled();
  });

  it('drops Running and keeps only logs once the task completes, fails or is cancelled', () => {
    const { rerender } = render(<SessionDetailsPanel details={details} isRunning sessionId="s" />);
    expect(tab('Running')).toHaveAttribute('aria-selected', 'true');
    rerender(<SessionDetailsPanel details={details} isRunning={false} sessionId="s" />);
    expect(tab('Running')).not.toBeInTheDocument();
    expect(tab('logs')).toBeEnabled();
    expect(tab('logs')).toHaveAttribute('aria-selected', 'true');
    expect(loadSessionDetails).toHaveBeenCalledWith('s');
  });

  it('opens a finished task directly on logs without a Running tab', () => {
    render(<SessionDetailsPanel details={details} isRunning={false} sessionId="s" />);
    expect(tab('Running')).not.toBeInTheDocument();
    expect(tab('logs')).toHaveAttribute('aria-selected', 'true');
  });
});

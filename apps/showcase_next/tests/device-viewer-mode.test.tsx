import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DeviceViewer } from '@/features/workspace/components/workspace-panels';
import type { SessionDetails } from '@/features/workspace/types';

vi.mock('@/app/providers', () => ({ useAppPreferences: () => ({ preferences: { language: 'en' } }) }));
vi.mock('@/features/workspace/provider', async () => {
  const { useReducer } = await import('react');
  const { initialWorkspaceState, workspaceReducer } = await import('@/features/workspace/reducer');
  return {
    useWorkspace: () => {
      const [state, dispatch] = useReducer(workspaceReducer, initialWorkspaceState);
      return {
        state,
        setPlayerSession: (sessionId: string, mode: 'live' | 'steps' | 'video') => dispatch({ type: 'playerSessionChanged', sessionId, mode }),
        patchPlayer: (patch: Partial<typeof state.player>) => dispatch({ type: 'playerPatched', patch }),
      };
    },
  };
});

const session = { session_id: 's', status: 'completed' };
const details: SessionDetails = {
  session, steps: [{ image_url: '/frame.jpg' }], checks: [], notes: null, usage: null, startup: [],
  video: { video_url: '/videos/test.mp4' },
};

describe('Device viewer default mode', () => {
  it('opens a completed task in Replay even when steps are available', () => {
    const { container } = render(<DeviceViewer session={session} details={details} isActive={false} />);
    expect(screen.getByRole('button', { name: 'Replay' })).toHaveClass('active');
    expect(container.querySelector('video')).toBeInTheDocument();
  });

  it('switches Live to Replay when the same task finishes before its recording loads', () => {
    const { rerender } = render(<DeviceViewer session={{ ...session, status: 'running' }} details={null} isActive />);
    expect(screen.getByRole('button', { name: 'Live' })).toHaveClass('active');
    rerender(<DeviceViewer session={session} details={null} isActive={false} />);
    expect(screen.getByRole('button', { name: 'Replay' })).toHaveClass('active');
    rerender(<DeviceViewer session={session} details={details} isActive={false} />);
    expect(screen.getByRole('button', { name: 'Replay' })).toHaveClass('active');
  });

  it('keeps a manual Steps selection when details refresh and defaults to Replay for another task', () => {
    const { rerender } = render(<DeviceViewer session={session} details={details} isActive={false} />);
    fireEvent.click(screen.getByRole('button', { name: 'Steps' }));
    rerender(<DeviceViewer session={session} details={{ ...details, steps: [...details.steps, {}] }} isActive={false} />);
    expect(screen.getByRole('button', { name: 'Steps' })).toHaveClass('active');
    rerender(<DeviceViewer session={{ ...session, session_id: 'other' }} details={details} isActive={false} />);
    expect(screen.getByRole('button', { name: 'Replay' })).toHaveClass('active');
  });
});

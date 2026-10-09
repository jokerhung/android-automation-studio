import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { sessionProfile, TaskList } from '@/features/workspace/components/workspace-panels';
import type { SessionSummary } from '@/features/workspace/types';

describe('Workspace profile branding', () => {
  it('renders persisted architecture with AAS branding without changing session data', () => {
    const session: SessionSummary = {
      session_id: 'history-session', status: 'completed', goal: 'Recorded task',
      model_info: { architecture: 'ARTEMIS FLASH' },
    };
    render(<TaskList title="History" empty="No tasks" tasks={[session]} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByText('AAS FLASH')).toBeInTheDocument();
    expect(screen.queryByText('ARTEMIS FLASH')).toBeNull();
    expect(session.model_info).toEqual({ architecture: 'ARTEMIS FLASH' });
    expect(sessionProfile(session)).toBe('AAS FLASH');
  });

  it('normalizes the fallback device profile and preserves other profile names', () => {
    expect(sessionProfile({ session_id: 'pro', status: 'completed', device_info: { profile: 'Artemis Pro' } })).toBe('AAS Pro');
    expect(sessionProfile({ session_id: 'flash', status: 'completed', device_info: { profile: 'flash' } })).toBe('flash');
    expect(sessionProfile({ session_id: 'empty', status: 'completed' })).toBe('flash');
  });
});

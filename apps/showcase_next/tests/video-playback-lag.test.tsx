import { fireEvent, render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DeviceViewer } from '@/features/workspace/components/workspace-panels';
import type { SessionDetails } from '@/features/workspace/types';

const shared = vi.hoisted(() => {
  const state = { player: { sessionId: 's', mode: 'video', currentTime: 0, playbackRate: 1, playing: false, stepIndex: 0 } };
  const patch = (changes: Record<string, unknown>) => { Object.assign(state.player, changes); };
  return { state, patch };
});
vi.mock('@/app/providers', () => ({ useAppPreferences: () => ({ preferences: { language: 'en' } }) }));
vi.mock('@/features/workspace/provider', () => ({
  useWorkspace: () => ({ state: shared.state, setPlayerSession: () => {}, patchPlayer: shared.patch }),
}));

const details: SessionDetails = {
  session: {}, steps: [], checks: [], notes: {}, usage: {}, startup: [],
  video: { video_url: '/videos/a.mp4', video_segments: [{ url: '/videos/a.mp4', start: 0, duration: 120 }] },
} as unknown as SessionDetails;
const viewer = () => <DeviceViewer session={{ session_id: 's', status: 'completed' }} isActive={false} details={details} />;

describe('Replay playback on a slow device', () => {
  it('does not rewind the video when React state lags behind the playing video', () => {
    shared.state.player.currentTime = 0;
    const { container, rerender } = render(viewer());
    const video = container.querySelector('video')!;
    Object.defineProperty(video, 'readyState', { value: 1, configurable: true });
    Object.defineProperty(video, 'duration', { value: 120, configurable: true });
    fireEvent.loadedMetadata(video);

    // The browser reports 2 s (timeupdate), then keeps playing while the page is busy.
    video.currentTime = 2;
    fireEvent.timeUpdate(video);
    rerender(viewer());
    video.currentTime = 3.4;
    rerender(viewer());

    expect(video.currentTime).toBe(3.4);
  });

  it('still jumps the video when something else moves the playhead', () => {
    shared.state.player.currentTime = 0;
    const { container, rerender } = render(viewer());
    const video = container.querySelector('video')!;
    Object.defineProperty(video, 'readyState', { value: 1, configurable: true });
    Object.defineProperty(video, 'duration', { value: 120, configurable: true });
    fireEvent.loadedMetadata(video);
    video.currentTime = 2;
    fireEvent.timeUpdate(video);

    shared.state.player.currentTime = 50;
    rerender(viewer());

    expect(video.currentTime).toBe(50);
  });
});

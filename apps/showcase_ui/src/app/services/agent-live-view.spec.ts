import { signal } from '@angular/core';
import { of } from 'rxjs';
import { AgentService } from './agent.service';

describe('AgentService automatic live view', () => {
  let service: AgentService;
  let status: any;

  beforeEach(() => {
    service = Object.create(AgentService.prototype) as AgentService;
    Object.assign(service, {
      currentSessionId: signal(null), userPinnedSessionId: signal(null),
      runningSessionId: signal(null), runningGoal: signal(null), agentStatus: signal('idle'),
      activeModel: signal(null), isPaused: signal(false), isRetrying: signal(false), pausedError: signal(null),
      pendingQueue: signal([]), activeTasks: signal([]), sessions: signal([]),
      isVideoWindowOpen: signal(false), isVideoMinimized: signal(false),
      activeVideoUrl: signal(null), activeVideoSegments: signal([]), activeVideoTitle: signal(''),
      isVideoLoading: signal(false), recordingPlaybackStatus: signal('idle'),
      recordingPlaybackMessage: signal(''), shouldAutoplayVideo: signal(false),
      autoOpenedLiveSessions: new Set(), activeVideoSessionId: null,
      videoRequestGeneration: 0, videoRetryTimer: null,
      zone: { runOutsideAngular: (fn: () => void) => fn() },
      http: { get: () => of(status) }
    });
    spyOn(service, 'selectSession').and.callFake(id => service.currentSessionId.set(id));
    spyOn(service, 'fetchSessions');
    spyOn<any>(service, 'flushStreamChunks');
    spyOn<any>(service, 'appendPausedErrorCard');
    spyOn<any>(service, 'requestSessionVideo');
    status = { status: 'running', session_id: 'run-1', active_tasks: [], queue: [] };
  });

  it('opens on the first running status even before sessions are loaded', () => {
    service.fetchStatus();
    expect(service.currentSessionId()).toBe('run-1');
    expect(service.isVideoWindowOpen()).toBeTrue();
    expect(service.isVideoMinimized()).toBeFalse();
    expect(service.recordingPlaybackStatus()).toBe('live');
    expect((service as any).requestSessionVideo).not.toHaveBeenCalled();
  });

  it('opens on session_started and ignores duplicate events after closing', () => {
    const listeners = new Map<string, (event: any) => void>();
    spyOn(window, 'EventSource').and.returnValue({
      addEventListener: (type: string, cb: (event: any) => void) => listeners.set(type, cb),
      close: () => {}
    } as unknown as EventSource);
    service.ensureLiveStream();
    const started = () => listeners.get('session_started')!({
      data: JSON.stringify({ session_id: 'run-1', initial_goal: 'Test task' })
    });
    started();
    expect(service.isVideoWindowOpen()).toBeTrue();
    expect(service.recordingPlaybackStatus()).toBe('live');
    service.closeVideoPlayer();
    started();
    service.fetchStatus();
    expect(service.isVideoWindowOpen()).toBeFalse();
  });

  it('respects closing through the toolbar and minimizing through repeated polls', () => {
    service.fetchStatus();
    service.isVideoMinimized.set(true);
    service.fetchStatus();
    expect(service.isVideoMinimized()).toBeTrue();
    service.toggleVideoPlayer();
    service.fetchStatus();
    expect(service.isVideoWindowOpen()).toBeFalse();
  });

  it('does not reopen the same task when paused or resumed', () => {
    service.fetchStatus();
    service.closeVideoPlayer();
    status.status = 'paused';
    service.fetchStatus();
    status.status = 'running';
    service.fetchStatus();
    expect(service.isVideoWindowOpen()).toBeFalse();
  });

  it('opens again for the next running task', () => {
    service.fetchStatus();
    service.closeVideoPlayer();
    status.session_id = 'run-2';
    service.fetchStatus();
    expect(service.isVideoWindowOpen()).toBeTrue();
    expect((service as any).activeVideoSessionId).toBe('run-2');
  });

  it('does not interrupt a pinned historical session or its replay', () => {
    service.currentSessionId.set('history');
    service.userPinnedSessionId.set('history');
    service.isVideoWindowOpen.set(true);
    service.recordingPlaybackStatus.set('ready');
    (service as any).activeVideoSessionId = 'history';
    service.fetchStatus();
    expect(service.currentSessionId()).toBe('history');
    expect((service as any).activeVideoSessionId).toBe('history');
    expect(service.recordingPlaybackStatus()).toBe('ready');
  });

  it('does not open for a task that is only queued', () => {
    status = { status: 'idle', queue: [{ session_id: 'queued', status: 'pending' }] };
    service.fetchStatus();
    expect(service.isVideoWindowOpen()).toBeFalse();
  });

  it('keeps recording finalization when the run ends', () => {
    const finalize = spyOn<any>(service, 'beginRecordingFinalization');
    service.fetchStatus();
    status = { status: 'idle', session_id: null };
    service.fetchStatus();
    expect(finalize).toHaveBeenCalledOnceWith('run-1');
  });
});

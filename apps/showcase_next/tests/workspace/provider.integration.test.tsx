import { StrictMode, useState } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AppProviders } from '@/app/providers';
import { useWorkspace } from '@/features/workspace/provider';

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  readonly url: string;
  closed = false;
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  private readonly listeners = new Map<string, Set<EventListener>>();

  constructor(url: string | URL) {
    this.url = String(url);
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListenerOrEventListenerObject): void {
    const callback = typeof listener === 'function' ? listener : listener.handleEvent.bind(listener);
    const listeners = this.listeners.get(type) ?? new Set<EventListener>();
    listeners.add(callback);
    this.listeners.set(type, listeners);
  }

  close(): void { this.closed = true; }

  emit(type: string, data: Record<string, unknown>): void {
    const event = new MessageEvent(type, { data: JSON.stringify(data) });
    if (type === 'message') this.onmessage?.(event);
    for (const listener of this.listeners.get(type) ?? []) listener(event);
  }
}

const json = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } }));

function Probe() {
  const { state, selectSession, patchPlayer } = useWorkspace();
  return <>
    <button onClick={() => selectSession('selected')}>select</button>
    <button onClick={() => patchPlayer({ currentTime: state.player.currentTime + 1 })}>advance</button>
    <output data-testid="selection">{state.selectedSessionId ?? 'none'}</output>
    <output data-testid="time">{state.player.currentTime}</output>
    <output data-testid="events">{state.streamEvents.map(event => String(event.data.step_id ?? event.data.chunk ?? '')).join(',')}</output>
  </>;
}

function Routes() {
  const [route, setRoute] = useState<'one' | 'two'>('one');
  return <>
    <button onClick={() => setRoute(current => current === 'one' ? 'two' : 'one')}>route</button>
    <Probe key={route} />
    <span>{route}</span>
  </>;
}

function requestCount(path: string): number {
  return vi.mocked(fetch).mock.calls.filter(([input]) => String(input) === path).length;
}

describe('WorkspaceProvider integration lifecycle', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeEventSource.instances = [];
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    vi.stubGlobal('EventSource', FakeEventSource);
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path === '/api/sessions') return json([]);
      if (path === '/api/status') return json({ status: 'idle' });
      if (path.endsWith('/video')) return json({ session_id: 'selected', status: 'unavailable', has_video: false });
      if (path.includes('/steps') || path.includes('/startup_progress')) return json([]);
      return json({});
    }));
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('keeps one active stream after the StrictMode effect remount and closes it on cleanup', async () => {
    const view = render(<StrictMode><AppProviders><Probe /></AppProviders></StrictMode>);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    expect(FakeEventSource.instances).toHaveLength(2);
    expect(FakeEventSource.instances.filter(source => !source.closed)).toHaveLength(1);
    expect(FakeEventSource.instances[0]?.closed).toBe(true);

    view.unmount();
    expect(FakeEventSource.instances.every(source => source.closed)).toBe(true);
  });

  it('does not duplicate the 2s and 6s polls, pauses while hidden, and refreshes immediately when visible', async () => {
    render(<StrictMode><AppProviders><Probe /></AppProviders></StrictMode>);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    const initialStatus = requestCount('/api/status');
    const initialSessions = requestCount('/api/sessions');

    await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });
    expect(requestCount('/api/status') - initialStatus).toBe(1);
    expect(requestCount('/api/sessions') - initialSessions).toBe(0);

    await act(async () => { await vi.advanceTimersByTimeAsync(4_000); });
    expect(requestCount('/api/status') - initialStatus).toBe(3);
    expect(requestCount('/api/sessions') - initialSessions).toBe(1);

    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    const hiddenStatus = requestCount('/api/status');
    const hiddenSessions = requestCount('/api/sessions');
    await act(async () => { await vi.advanceTimersByTimeAsync(12_000); });
    expect(requestCount('/api/status')).toBe(hiddenStatus);
    expect(requestCount('/api/sessions')).toBe(hiddenSessions);

    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    await act(async () => { fireEvent(document, new Event('visibilitychange')); await vi.advanceTimersByTimeAsync(0); });
    expect(requestCount('/api/status')).toBe(hiddenStatus + 1);
    expect(requestCount('/api/sessions')).toBe(hiddenSessions + 1);
  });

  it('stops fallback polling while SSE is open and ignores heartbeat events', async () => {
    render(<AppProviders><Probe /></AppProviders>);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    fireEvent.click(screen.getByText('select'));
    const source = FakeEventSource.instances[0]!;
    await act(async () => { source.onopen?.(new Event('open')); await vi.advanceTimersByTimeAsync(0); });
    const requests = vi.mocked(fetch).mock.calls.length;
    await act(async () => {
      source.emit('keep-alive', {});
      source.emit('info', { message: 'Subscribed' });
      await vi.advanceTimersByTimeAsync(12_000);
    });
    expect(vi.mocked(fetch).mock.calls).toHaveLength(requests);
    await act(async () => { source.emit('session_ended', { session_id: 'selected' }); await vi.advanceTimersByTimeAsync(0); });
    expect(vi.mocked(fetch).mock.calls.length).toBeGreaterThan(requests);
    const statusRequests = requestCount('/api/status');
    await act(async () => { source.onerror?.(new Event('error')); await vi.advanceTimersByTimeAsync(2_000); });
    expect(requestCount('/api/status')).toBeGreaterThan(statusRequests);
  });

  it('keeps root workspace state when a route child remounts', async () => {
    render(<StrictMode><AppProviders><Routes /></AppProviders></StrictMode>);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    fireEvent.click(screen.getByText('select'));
    fireEvent.click(screen.getByText('advance'));
    expect(screen.getByTestId('selection')).toHaveTextContent('selected');
    expect(screen.getByTestId('time')).toHaveTextContent('1');
    const sourceCount = FakeEventSource.instances.length;
    const mutationCount = vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method && init.method !== 'GET').length;

    fireEvent.click(screen.getByText('route'));
    expect(screen.getByText('two')).toBeInTheDocument();
    expect(screen.getByTestId('selection')).toHaveTextContent('selected');
    expect(screen.getByTestId('time')).toHaveTextContent('1');
    expect(FakeEventSource.instances).toHaveLength(sourceCount);
    expect(FakeEventSource.instances.filter(source => !source.closed)).toHaveLength(1);
    expect(vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method && init.method !== 'GET')).toHaveLength(mutationCount);
  });

  it('ignores foreign-session events and events from the stale StrictMode stream', async () => {
    render(<StrictMode><AppProviders><Probe /></AppProviders></StrictMode>);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    fireEvent.click(screen.getByText('select'));
    const stale = FakeEventSource.instances[0];
    const active = FakeEventSource.instances[1];
    expect(stale?.closed).toBe(true);

    act(() => active?.emit('step_recorded', { session_id: 'foreign', step_id: 'foreign-step' }));
    act(() => stale?.emit('step_recorded', { session_id: 'selected', step_id: 'stale-step' }));
    expect(screen.getByTestId('events')).toHaveTextContent('');

    act(() => active?.emit('step_recorded', { session_id: 'selected', step_id: 'active-step' }));
    expect(screen.getByTestId('events')).toHaveTextContent('active-step');
    expect(screen.getByTestId('events')).not.toHaveTextContent('foreign-step');
    expect(screen.getByTestId('events')).not.toHaveTextContent('stale-step');
  });
});

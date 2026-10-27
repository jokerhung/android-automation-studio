import { afterEach,describe,expect,it,vi } from 'vitest'; import { ApiError,apiPath,apiRequest } from '@/lib/api/client';
afterEach(()=>vi.unstubAllGlobals()); describe('typed API client',()=>{it('encodes path segments',()=>expect(apiPath('/api/schedules','schedule/1','run 1')).toBe('/api/schedules/schedule%2F1/run%201'));it('uses same-origin JSON requests',async()=>{const mock=vi.fn().mockResolvedValue(new Response(JSON.stringify({ready:true}),{status:200,headers:{'content-type':'application/json'}}));vi.stubGlobal('fetch',mock);await expect(apiRequest('/api/system/readiness',{query:{force:true}})).resolves.toEqual({ready:true});expect(mock).toHaveBeenCalledWith('/api/system/readiness?force=true',expect.objectContaining({credentials:'same-origin'}));});it('throws a structured error',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:'Offline'}),{status:503,headers:{'content-type':'application/json'}})));await expect(apiRequest('/api/status')).rejects.toMatchObject({status:503,message:'Offline'} satisfies Partial<ApiError>);});it('rejects non-api paths',async()=>await expect(apiRequest('https://example.com')).rejects.toThrow('/api/'));});


describe('API request deadlines', () => {
  afterEach(() => { vi.useRealTimers(); });

  function pending(signal: AbortSignal): Promise<never> {
    return new Promise((_, reject) => {
      if (signal.aborted) reject(signal.reason);
      else signal.addEventListener('abort', () => reject(signal.reason), { once: true });
    });
  }

  it('bounds a stalled fetch and permits the next request to succeed', async () => {
    vi.useFakeTimers();
    const mock = vi.fn((_url: string, init: RequestInit) => pending(init.signal as AbortSignal));
    vi.stubGlobal('fetch', mock);
    const result = expect(apiRequest('/api/status')).rejects.toMatchObject({ name: 'TimeoutError', url: '/api/status' });
    await vi.advanceTimersByTimeAsync(15_000);
    await result;
    expect((mock.mock.calls[0]![1].signal as AbortSignal).aborted).toBe(true);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}')));
    await expect(apiRequest('/api/status')).resolves.toBe('{}');
    expect(vi.getTimerCount()).toBe(0);
  });

  it('keeps the deadline active while reading the body and honors an override', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn((_url: string, init: RequestInit) => Promise.resolve({
      status: 200, ok: true, headers: new Headers({ 'content-type': 'application/json' }),
      json: () => pending(init.signal as AbortSignal),
    })));
    const result = expect(apiRequest('/api/system/readiness', { timeoutMs: 45_000 })).rejects.toMatchObject({ name: 'TimeoutError' });
    await vi.advanceTimersByTimeAsync(44_999);
    expect(vi.getTimerCount()).toBe(1);
    await vi.advanceTimersByTimeAsync(1);
    await result;
    expect(vi.getTimerCount()).toBe(0);
  });

  it('preserves caller cancellation and removes its listener', async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    const remove = vi.spyOn(controller.signal, 'removeEventListener');
    vi.stubGlobal('fetch', vi.fn((_url: string, init: RequestInit) => pending(init.signal as AbortSignal)));
    const result = expect(apiRequest('/api/status', { signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' });
    controller.abort();
    await result;
    expect(remove).toHaveBeenCalledWith('abort', expect.any(Function));
    expect(vi.getTimerCount()).toBe(0);
  });
});

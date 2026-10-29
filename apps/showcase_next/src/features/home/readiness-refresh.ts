export const HOME_READINESS_REFRESH_INTERVAL_MS = 30000;

type ReadinessRefreshCoordinatorOptions = {
  refresh(signal: AbortSignal): Promise<void>;
  onError(error: unknown): void;
  intervalMs?: number;
  documentObject?: Document;
  windowObject?: Window;
};

export type ReadinessRefreshCoordinator = { start(): void; stop(): void; refresh(): void };

export function createReadinessRefreshCoordinator({
  refresh,
  onError,
  intervalMs = HOME_READINESS_REFRESH_INTERVAL_MS,
  documentObject = document,
  windowObject = window,
}: ReadinessRefreshCoordinatorOptions): ReadinessRefreshCoordinator {
  let timer: ReturnType<typeof setInterval> | null = null;
  let request: AbortController | null = null;
  let stopped = true;

  const run = () => {
    if (stopped || documentObject.hidden || request) return;
    const controller = new AbortController();
    request = controller;
    void refresh(controller.signal)
      .catch((error: unknown) => {
        if (!controller.signal.aborted) onError(error);
      })
      .finally(() => {
        if (request === controller) request = null;
      });
  };
  const refreshWhenActive = () => {
    if (!documentObject.hidden) run();
  };

  return {
    refresh: run,
    start() {
      if (!stopped) return;
      stopped = false;
      documentObject.addEventListener('visibilitychange', refreshWhenActive);
      windowObject.addEventListener('focus', refreshWhenActive);
      timer = setInterval(run, intervalMs);
      run();
    },
    stop() {
      if (stopped) return;
      stopped = true;
      if (timer !== null) clearInterval(timer);
      timer = null;
      documentObject.removeEventListener('visibilitychange', refreshWhenActive);
      windowObject.removeEventListener('focus', refreshWhenActive);
      request?.abort();
      request = null;
    },
  };
}

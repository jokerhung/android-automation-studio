export interface PollDefinition { intervalMs: number; run(signal: AbortSignal): Promise<unknown> }
type Schedule = (callback: () => void, intervalMs: number) => ReturnType<typeof setInterval>;
type Unschedule = (timer: ReturnType<typeof setInterval>) => void;
export interface PollCoordinatorOptions { hidden?: () => boolean; setInterval?: Schedule; clearInterval?: Unschedule }

export class PollCoordinator {
  private readonly controllers = new Map<string, AbortController>();
  private readonly timers = new Map<string, ReturnType<typeof setInterval>>();
  private readonly inFlight = new Set<string>();
  private started = false;
  private readonly hidden: () => boolean;
  private readonly schedule: Schedule;
  private readonly unschedule: Unschedule;
  constructor(private readonly polls: Readonly<Record<string, PollDefinition>>, options: PollCoordinatorOptions = {}) {
    this.hidden = options.hidden ?? (() => typeof document !== 'undefined' && document.hidden);
    this.schedule = options.setInterval ?? ((callback, intervalMs) => globalThis.setInterval(callback, intervalMs));
    this.unschedule = options.clearInterval ?? (timer => globalThis.clearInterval(timer));
  }
  start(): void {
    if (this.started) return;
    this.started = true;
    for (const [key, definition] of Object.entries(this.polls)) {
      this.controllers.set(key, new AbortController());
      this.timers.set(key, this.schedule(() => { if (!this.hidden()) void this.tick(key); }, definition.intervalMs));
    }
    if (!this.hidden()) void this.refreshVisible();
  }
  async tick(key: string): Promise<void> {
    if (!this.started || this.hidden() || this.inFlight.has(key)) return;
    const definition = this.polls[key];
    const controller = this.controllers.get(key);
    if (!definition || !controller || controller.signal.aborted) return;
    this.inFlight.add(key);
    try { await definition.run(controller.signal); } finally { this.inFlight.delete(key); }
  }
  async refreshVisible(): Promise<void> { if (!this.started || this.hidden()) return; await Promise.all(Object.keys(this.polls).map(key => this.tick(key))); }
  stop(): void {
    this.started = false;
    for (const timer of this.timers.values()) this.unschedule(timer);
    for (const controller of this.controllers.values()) controller.abort();
    this.timers.clear(); this.controllers.clear(); this.inFlight.clear();
  }
}

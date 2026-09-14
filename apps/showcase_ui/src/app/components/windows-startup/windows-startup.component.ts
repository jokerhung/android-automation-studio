import { HttpClient } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { finalize } from 'rxjs';

interface StartupStatus { supported: boolean; enabled: boolean; port: number | null; }

@Component({
  selector: 'app-windows-startup',
  standalone: true,
  template: `
    <section aria-labelledby="startup-title">
      <div class="setting-row">
        <div>
          <h3 id="startup-title">Start with Windows</h3>
          <p>Start ARTEMIS in the background when you sign in to Windows. No browser or terminal window opens.</p>
        </div>
        <label class="startup-switch" [class.is-disabled]="loading() || saving() || !status()?.supported"
          [attr.title]="saving() ? 'Saving…' : (status()?.enabled ? 'On' : 'Off')">
          <input type="checkbox" role="switch" aria-label="Start with Windows"
            [attr.aria-busy]="saving()"
            [checked]="status()?.enabled ?? false" [disabled]="loading() || saving() || !status()?.supported"
            (change)="toggle($event)">
          <span class="switch-track" aria-hidden="true"><span class="switch-thumb"></span></span>
        </label>
      </div>
      @if (loading()) { <p role="status">Loading startup settings…</p> }
      @if (status()?.supported === false) { <p>This feature is only available on Windows.</p> }
      @if (status()?.enabled) { <p>Enabled for the current Windows user · Port {{ status()?.port ?? 'unknown' }}.</p> }
      <p class="hint">Applies at sign-in, not before login. Enabled schedules may run once ARTEMIS starts. Turning this off does not stop the current server. If you move ARTEMIS or change its port, turn this off and on again.</p>
      @if (error()) { <p class="error" role="alert">{{ error() }} <button type="button" (click)="load()" [disabled]="loading() || saving()">Retry</button></p> }
      @if (message()) { <p role="status">{{ message() }}</p> }
    </section>
  `,
  styles: [`
    :host { display:block; margin-bottom:22px; }
    section { background:var(--theme-bg-surface); border:1px solid var(--theme-border); border-radius:16px; padding:22px; }
    .setting-row { display:flex; align-items:center; gap:24px; justify-content:space-between; }
    h3 { margin:0 0 8px; color:var(--theme-text-primary); } p { margin:8px 0 0; color:var(--theme-text-muted); font-size:13px; line-height:1.5; }
    .startup-switch { position:relative; display:inline-flex; width:64px; height:36px; flex:0 0 64px; cursor:pointer; }
    .startup-switch input { position:absolute; inset:0; width:100%; height:100%; opacity:0; margin:0; z-index:1; cursor:inherit; }
    .switch-track { display:block; width:100%; height:100%; box-sizing:border-box; border:2px solid var(--theme-bg-surface); border-radius:999px; background:var(--theme-border-strong); transition:background .18s ease; }
    .switch-thumb { display:block; width:32px; height:32px; border-radius:50%; background:var(--theme-switch-thumb); box-shadow:0 2px 4px rgba(15,23,42,.22),0 0 1px rgba(15,23,42,.12); transition:transform .18s ease; }
    input:checked + .switch-track { background:#43d05c; }
    input:checked + .switch-track .switch-thumb { transform:translateX(28px); }
    input:focus-visible + .switch-track { outline:3px solid var(--theme-focus); outline-offset:3px; }
    .startup-switch.is-disabled { cursor:not-allowed; opacity:.5; }
    @media (prefers-reduced-motion: reduce) { .switch-track,.switch-thumb { transition:none; } }
    .error { color:var(--theme-error); } .hint { font-size:12px; }
    button { margin-left:8px; cursor:pointer; }
  `]
})
export class WindowsStartupComponent implements OnInit {
  private readonly http = inject(HttpClient);
  readonly status = signal<StartupStatus | null>(null);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly message = signal<string | null>(null);

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true); this.error.set(null);
    this.http.get<StartupStatus>('/api/system/windows-startup')
      .pipe(finalize(() => this.loading.set(false))).subscribe({
        next: status => this.status.set(status),
        error: err => { this.status.set(null); this.error.set(this.errorText(err)); }
      });
  }

  toggle(event: Event): void {
    const input = event.target as HTMLInputElement;
    const enabled = input.checked;
    input.checked = this.status()?.enabled ?? false;
    if (this.saving() || this.loading() || !this.status()?.supported) return;
    this.saving.set(true); this.error.set(null); this.message.set(null);
    this.http.put<StartupStatus>('/api/system/windows-startup', { enabled })
      .pipe(finalize(() => this.saving.set(false))).subscribe({
        next: status => {
          this.status.set(status); input.checked = status.enabled;
          this.message.set(status.enabled ? 'ARTEMIS will start at your next Windows sign-in.' : 'Start with Windows is turned off.');
        },
        error: err => this.error.set(this.errorText(err))
      });
  }

  private errorText(err: any): string {
    return typeof err?.error?.detail === 'string' ? err.error.detail : 'Unable to access startup settings. Restart the ARTEMIS backend if it has not been updated.';
  }
}

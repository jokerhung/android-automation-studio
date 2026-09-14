import { HttpClient } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { finalize } from 'rxjs';
import { TranslatePipe } from '../../core/i18n/translate.pipe';
import { TranslationService } from '../../core/i18n/translation.service';

interface StartupStatus { supported: boolean; enabled: boolean; port: number | null; }

@Component({
  selector: 'app-windows-startup',
  standalone: true,
  imports: [TranslatePipe],
  template: `
    <section aria-labelledby="startup-title">
      <div class="setting-row">
        <div>
          <h3 id="startup-title">{{ 'startup.title' | translate }}</h3>
          <p>{{ 'startup.description' | translate }}</p>
        </div>
        <label class="startup-switch" [class.is-disabled]="loading() || saving() || !status()?.supported"
          [attr.title]="(saving() ? 'startup.saving' : (status()?.enabled ? 'startup.on' : 'common.off')) | translate">
          <input type="checkbox" role="switch" [attr.aria-label]="'startup.title' | translate"
            [attr.aria-busy]="saving()"
            [checked]="status()?.enabled ?? false" [disabled]="loading() || saving() || !status()?.supported"
            (change)="toggle($event)">
          <span class="switch-track" aria-hidden="true"><span class="switch-thumb"></span></span>
        </label>
      </div>
      @if (loading()) { <p role="status">{{ 'startup.loading' | translate }}</p> }
      @if (status()?.supported === false) { <p>{{ 'startup.windowsOnly' | translate }}</p> }
      @if (status()?.enabled) { <p>{{ i18n.translate('startup.enabled', { port: status()?.port ?? i18n.translate('startup.unknown') }) }}</p> }
      <p class="hint">{{ 'startup.hint' | translate }}</p>
      @if (error()) { <p class="error" role="alert">{{ error() }} <button type="button" (click)="load()" [disabled]="loading() || saving()">{{ 'common.retry' | translate }}</button></p> }
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
  readonly i18n = inject(TranslationService);
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
          this.message.set(this.i18n.translate(status.enabled ? 'startup.enabledMessage' : 'startup.disabledMessage'));
        },
        error: err => this.error.set(this.errorText(err))
      });
  }

  private errorText(err: any): string {
    return typeof err?.error?.detail === 'string' ? err.error.detail : this.i18n.translate('startup.loadError');
  }
}

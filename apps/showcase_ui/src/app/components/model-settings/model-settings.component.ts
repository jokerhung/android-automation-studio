import { HttpClient } from '@angular/common/http';
import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { catchError, finalize, of, switchMap, takeWhile, timer, timeout } from 'rxjs';

interface ModelSettings {
  provider: string; default_model: string; fallback_model: string; fallback_provider: string;
  base_url: string; fallback_url: string; version: string;
  keys_configured: Record<string, boolean>; config_path: string; env_path: string; node_overrides: string[];
}

@Component({
  selector: 'app-model-settings', standalone: true, imports: [FormsModule],
  template: `
    <section class="model-editor" aria-labelledby="model-editor-title">
      <h3 id="model-editor-title">Default models & connection</h3>
      <p>Save to artemis.jsonc and .env, then restart ARTEMIS automatically. API keys are never shown.</p>
      @if (loading()) { <p role="status">Loading model settings…</p> }
      @if (saved(); as current) {
        <form #modelForm="ngForm" (ngSubmit)="confirmSave(modelForm)" novalidate>
          <fieldset [disabled]="busy()">
            <label>Provider<select name="provider" [(ngModel)]="draft.provider" (ngModelChange)="providerChanged()" required>
              @for (provider of providers; track provider.id) { <option [value]="provider.id">{{ provider.label }}</option> }
            </select></label>
            <div class="row">
              <label>Default model<input name="defaultModel" [(ngModel)]="draft.default_model" required maxlength="200" placeholder="Model name served by your provider"></label>
              <label>Fallback model<input name="fallbackModel" [(ngModel)]="draft.fallback_model" required maxlength="200"></label>
            </div>
            <label>API key <span class="hint">{{ current.keys_configured[draft.provider] ? 'Configured — leave blank to keep existing key' : 'Not configured' }}</span>
              <input type="password" name="apiKey" [(ngModel)]="apiKey" autocomplete="new-password" placeholder="Leave blank to keep existing key">
            </label>
            @if (draft.provider !== 'google') {
              <div class="row">
                <label>Base URL<input name="baseUrl" [(ngModel)]="draft.base_url" placeholder="https://your-endpoint/v1"></label>
                <label>Fallback URL<input name="fallbackUrl" [(ngModel)]="draft.fallback_url" placeholder="Same as Base URL when blank"></label>
              </div>
              <p class="hint">Both models use this provider's API key. Only use URLs you trust. Include the API prefix, not /chat/completions.</p>
            } @else { <p class="hint">Google uses its standard endpoint; custom Google URLs are not supported by this editor.</p> }
            <p class="hint">Per-agent overrides (including Flash step summarizer) are kept unchanged. They can override the default models above.</p>
            @if (current.fallback_provider !== current.provider) { <p class="warning">The current fallback uses another provider. Saving this form will set both models to the selected provider.</p> }
            <p class="paths">Config: {{ current.config_path }}<br>Keys: {{ current.env_path }}</p>
            <button type="submit">Save & restart</button>
          </fieldset>
        </form>
      }
      @if (error()) { <div class="error" role="alert">{{ error() }} <button type="button" (click)="load()" [disabled]="busy()">Reload settings</button></div> }
      @if (message()) { <p class="status" role="status">{{ message() }}</p> }
      @if (confirming()) {
        <div class="confirm-backdrop"><section class="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="restart-title">
          <h3 id="restart-title">Save settings and restart ARTEMIS?</h3>
          <p>Your model settings will be saved to disk. The service will restart and this page will briefly disconnect. Changes apply to future tasks.</p>
          <p>Task, queue or email activity blocks this action. Wait until the service is idle.</p>
          <div class="buttons"><button type="button" (click)="confirming.set(false)">Cancel</button><button type="button" (click)="save()">Save & restart now</button></div>
        </section></div>
      }
    </section>
  `,
  styles: [`
    :host { display:block; margin-bottom:28px; } .model-editor { border:1px solid #e2e8f0; border-radius:12px; padding:22px; background:white; }
    h3 { margin:0 0 10px; } p { font-size:13px; line-height:1.6; color:#64748b; }
    fieldset { border:0; padding:0; margin:0; min-width:0; } label { display:flex; flex-direction:column; gap:7px; margin:16px 0; font-size:13px; font-weight:600; color:#334155; }
    input,select { box-sizing:border-box; width:100%; min-width:0; min-height:42px; font-family:'Segoe UI',Arial,sans-serif; font-size:14px; font-weight:400; line-height:20px; padding:10px 12px; border:1px solid #94a3b8; border-radius:8px; background:#fff; color:#0f172a; caret-color:#0f172a; opacity:1; text-shadow:none; }
    input::placeholder { color:#64748b; opacity:1; font-weight:400; }
    input:hover:not(:disabled),select:hover:not(:disabled) { border-color:#64748b; }
    input:focus,select:focus { border-color:#1a73e8; outline:2px solid #bfdbfe; outline-offset:1px; }
    input:disabled,select:disabled { background:#f1f5f9; color:#64748b; cursor:wait; }
    input.ng-invalid.ng-touched { border-color:#dc2626; } .row { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
    .hint,.paths { font-size:12px; font-weight:400; overflow-wrap:anywhere; } .error { color:#b91c1c; padding:12px; background:#fff1f2; border-radius:8px; margin-top:12px; }
    button { padding:9px 15px; border-radius:8px; border:1px solid #cbd5e1; cursor:pointer; background:#f8fafc; color:#172033; font:inherit; }
    button[type=submit],.buttons button:last-child { background:#1a73e8; border-color:#1a73e8; color:white; } button:disabled { opacity:.5; cursor:wait; }
    .status { color:#1769d2; } .warning { color:#92400e; } .confirm-backdrop { position:fixed; inset:0; background:#0f172a80; display:flex; align-items:center; justify-content:center; z-index:2100; padding:20px; }
    .confirm-dialog { background:white; padding:24px; border-radius:14px; max-width:480px; } .buttons { display:flex; justify-content:flex-end; gap:12px; margin-top:20px; }
    :focus-visible { outline:2px solid #93c5fd; outline-offset:2px; } @media(max-width:700px) { .row { grid-template-columns:1fr; gap:0; } }
  `]
})
export class ModelSettingsComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly destroyRef = inject(DestroyRef);
  readonly providers = [
    {id:'openai',label:'OpenAI'}, {id:'google',label:'Google Gemini'}, {id:'anthropic',label:'Anthropic'},
    {id:'openrouter',label:'OpenRouter'}, {id:'xai',label:'xAI'}, {id:'custom',label:'Custom (OpenAI-compatible)'},
    {id:'ollama',label:'Ollama'}, {id:'vllm',label:'vLLM'}
  ];
  readonly saved = signal<ModelSettings | null>(null);
  readonly loading = signal(false); readonly busy = signal(false); readonly confirming = signal(false);
  readonly error = signal<string | null>(null); readonly message = signal<string | null>(null);
  draft = {provider:'openai',default_model:'',fallback_model:'',base_url:'',fallback_url:''};
  apiKey = '';
  ngOnInit(): void { this.load(); }
  load(): void {
    this.loading.set(true); this.error.set(null);
    this.http.get<ModelSettings>('/api/settings/model').pipe(takeUntilDestroyed(this.destroyRef),finalize(()=>this.loading.set(false))).subscribe({
      next: value => { this.saved.set(value); this.draft = {provider:value.provider,default_model:value.default_model,fallback_model:value.fallback_model,base_url:value.base_url,fallback_url:value.fallback_url}; this.apiKey=''; },
      error: err => this.error.set(this.errorText(err,'Unable to load model settings. Restart the backend after updating code.'))
    });
  }
  providerChanged(): void { this.apiKey=''; this.draft.base_url=''; this.draft.fallback_url=''; }
  confirmSave(form: NgForm): void {
    this.error.set(null); this.message.set(null);
    if(form.invalid || !this.draft.default_model.trim() || !this.draft.fallback_model.trim()) { form.control.markAllAsTouched(); this.error.set('Enter the provider, default model and fallback model.'); return; }
    this.confirming.set(true);
  }
  save(): void {
    if(this.busy() || !this.saved()) return;
    this.confirming.set(false); this.busy.set(true);
    this.message.set('Saving configuration. ARTEMIS will restart after the files are saved…');
    this.http.put<any>('/api/settings/model',{...this.draft,api_key:this.apiKey || null,expected_version:this.saved()!.version,confirm_restart:true})
      .pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
        next: res => {
          this.apiKey='';
          if(res.status !== 'restarting') { this.busy.set(false); this.message.set(null); this.error.set(res.message || 'Saved; restart manually to apply.'); return; }
          this.message.set('Settings saved. Restarting ARTEMIS — reconnecting automatically…');
          this.reconnect(res.previous_pid);
        },
        error: err => { this.busy.set(false); this.message.set(null); this.error.set(this.errorText(err,'Save/restart could not be confirmed. Reload settings before trying again.')); }
      });
  }
  private reconnect(previousPid: number): void {
    let recovered = false;
    timer(2500,1500).pipe(
      switchMap(()=>this.http.get<any>('/api/system/server-status').pipe(timeout(1200),catchError(()=>of(null)))),
      takeWhile((status,index)=>{ recovered = !!status?.current_pid && status.current_pid !== previousPid; return !recovered && index < 59; },true),
      takeUntilDestroyed(this.destroyRef),
      finalize(()=>this.busy.set(false))
    ).subscribe({
      next: () => {},
      complete: ()=> { if(this.destroyRef.destroyed) return; if(recovered) { this.message.set('ARTEMIS restarted. New model settings are active.'); this.load(); } else { this.message.set(null); this.error.set('Reconnection timed out. Settings were saved; check the server or restart it manually.'); } }
    });
  }
  private errorText(err:any,fallback:string):string { return typeof err?.error?.detail === 'string' ? err.error.detail : fallback; }
}

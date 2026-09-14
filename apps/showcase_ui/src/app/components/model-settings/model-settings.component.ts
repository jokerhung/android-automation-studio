import { HttpClient } from '@angular/common/http';
import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { catchError, finalize, of, switchMap, takeWhile, timer, timeout } from 'rxjs';
import { TranslatePipe } from '../../core/i18n/translate.pipe';
import { TranslationService } from '../../core/i18n/translation.service';

interface ModelSettings {
  provider: string; default_model: string; fallback_model: string; fallback_provider: string;
  base_url: string; fallback_url: string; version: string;
  keys_configured: Record<string, boolean>; config_path: string; env_path: string; node_overrides: string[];
}

@Component({
  selector: 'app-model-settings', standalone: true, imports: [FormsModule, TranslatePipe],
  template: `
    <section class="model-editor" aria-labelledby="model-editor-title">
      <h3 id="model-editor-title">{{ 'model.title' | translate }}</h3>
      <p>{{ 'model.description' | translate }}</p>
      @if (loading()) { <p role="status">{{ 'model.loading' | translate }}</p> }
      @if (saved(); as current) {
        <form #modelForm="ngForm" (ngSubmit)="confirmSave(modelForm)" novalidate>
          <fieldset [disabled]="busy()">
            <label>{{ 'model.provider' | translate }}<select name="provider" [(ngModel)]="draft.provider" (ngModelChange)="providerChanged()" required>
              @for (provider of providers; track provider.id) { <option [value]="provider.id">{{ provider.id === 'custom' ? ('model.customProvider' | translate) : provider.label }}</option> }
            </select></label>
            <div class="row">
              <label>{{ 'model.default' | translate }}<input name="defaultModel" [(ngModel)]="draft.default_model" required maxlength="200" [placeholder]="'model.modelPlaceholder' | translate"></label>
              <label>{{ 'model.fallback' | translate }}<input name="fallbackModel" [(ngModel)]="draft.fallback_model" required maxlength="200"></label>
            </div>
            <label>{{ 'model.apiKey' | translate }} <span class="hint">{{ (current.keys_configured[draft.provider] ? 'model.configured' : 'model.notConfigured') | translate }}</span>
              <input type="password" name="apiKey" [(ngModel)]="apiKey" autocomplete="new-password" [placeholder]="'model.keepKey' | translate">
            </label>
            @if (draft.provider !== 'google') {
              <div class="row">
                <label>{{ 'model.baseUrl' | translate }}<input name="baseUrl" [(ngModel)]="draft.base_url" placeholder="https://your-endpoint/v1"></label>
                <label>{{ 'model.fallbackUrl' | translate }}<input name="fallbackUrl" [(ngModel)]="draft.fallback_url" [placeholder]="'model.sameBaseUrl' | translate"></label>
              </div>
              <p class="hint">{{ 'model.urlHint' | translate }}</p>
            } @else { <p class="hint">{{ 'model.googleHint' | translate }}</p> }
            <p class="hint">{{ 'model.overrideHint' | translate }}</p>
            @if (current.fallback_provider !== current.provider) { <p class="warning">{{ 'model.fallbackWarning' | translate }}</p> }
            <p class="paths">{{ 'model.configPath' | translate }}: {{ current.config_path }}<br>{{ 'model.keysPath' | translate }}: {{ current.env_path }}</p>
            <button type="submit">{{ 'model.saveRestart' | translate }}</button>
          </fieldset>
        </form>
      }
      @if (error()) { <div class="error" role="alert">{{ error() }} <button type="button" (click)="load()" [disabled]="busy()">{{ 'model.reload' | translate }}</button></div> }
      @if (message()) { <p class="status" role="status">{{ message() }}</p> }
      @if (confirming()) {
        <div class="confirm-backdrop"><section class="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="restart-title">
          <h3 id="restart-title">{{ 'model.confirmTitle' | translate }}</h3>
          <p>{{ 'model.confirmDescription' | translate }}</p>
          <p>{{ 'model.confirmBusy' | translate }}</p>
          <div class="buttons"><button type="button" (click)="confirming.set(false)">{{ 'common.cancel' | translate }}</button><button type="button" (click)="save()">{{ 'model.saveRestartNow' | translate }}</button></div>
        </section></div>
      }
    </section>
  `,
  styles: [`
    :host { display:block; margin-bottom:28px; } .model-editor { border:1px solid var(--theme-border); border-radius:12px; padding:22px; background:var(--theme-bg-surface); }
    h3 { margin:0 0 10px; } p { font-size:13px; line-height:1.6; color:var(--theme-text-muted); }
    fieldset { border:0; padding:0; margin:0; min-width:0; } label { display:flex; flex-direction:column; gap:7px; margin:16px 0; font-size:13px; font-weight:600; color:var(--theme-text-secondary); }
    input,select { box-sizing:border-box; width:100%; min-width:0; min-height:42px; font-family:'Segoe UI',Arial,sans-serif; font-size:14px; font-weight:400; line-height:20px; padding:10px 12px; border:1px solid var(--theme-input-border); border-radius:8px; background:var(--theme-input-bg); color:var(--theme-input-text); caret-color:var(--theme-input-text); opacity:1; text-shadow:none; }
    input::placeholder { color:var(--theme-text-muted); opacity:1; font-weight:400; }
    input:hover:not(:disabled),select:hover:not(:disabled) { border-color:var(--theme-text-muted); }
    input:focus,select:focus { border-color:var(--theme-accent); outline:2px solid var(--theme-focus-ring); outline-offset:1px; }
    input:disabled,select:disabled { background:var(--theme-bg-surface-muted); color:var(--theme-text-muted); cursor:wait; }
    input.ng-invalid.ng-touched { border-color:var(--theme-error); } .row { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
    .hint,.paths { font-size:12px; font-weight:400; overflow-wrap:anywhere; } .error { color:var(--theme-error); padding:12px; background:var(--theme-error-bg); border-radius:8px; margin-top:12px; }
    button { padding:9px 15px; border-radius:8px; border:1px solid var(--theme-border-strong); cursor:pointer; background:var(--theme-bg-surface-subtle); color:var(--theme-text-primary); font:inherit; }
    button[type=submit],.buttons button:last-child { background:var(--theme-accent); border-color:var(--theme-accent); color:var(--theme-on-accent); } button:disabled { opacity:.5; cursor:wait; }
    .status { color:var(--theme-info); } .warning { color:var(--theme-warning); } .confirm-backdrop { position:fixed; inset:0; background:#0f172a80; display:flex; align-items:center; justify-content:center; z-index:2100; padding:20px; }
    .confirm-dialog { background:var(--theme-bg-surface); padding:24px; border-radius:14px; max-width:480px; } .buttons { display:flex; justify-content:flex-end; gap:12px; margin-top:20px; }
    :focus-visible { outline:2px solid var(--theme-focus); outline-offset:2px; } @media(max-width:700px) { .row { grid-template-columns:1fr; gap:0; } }
  `]
})
export class ModelSettingsComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly destroyRef = inject(DestroyRef);
  private readonly i18n = inject(TranslationService);
  readonly providers = [
    {id:'openai',label:'OpenAI'}, {id:'google',label:'Google Gemini'}, {id:'anthropic',label:'Anthropic'},
    {id:'openrouter',label:'OpenRouter'}, {id:'xai',label:'xAI'}, {id:'custom',label:'Custom'},
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
      error: err => this.error.set(this.errorText(err,this.i18n.translate('model.loadError')))
    });
  }
  providerChanged(): void { this.apiKey=''; this.draft.base_url=''; this.draft.fallback_url=''; }
  confirmSave(form: NgForm): void {
    this.error.set(null); this.message.set(null);
    if(form.invalid || !this.draft.default_model.trim() || !this.draft.fallback_model.trim()) { form.control.markAllAsTouched(); this.error.set(this.i18n.translate('model.requiredError')); return; }
    this.confirming.set(true);
  }
  save(): void {
    if(this.busy() || !this.saved()) return;
    this.confirming.set(false); this.busy.set(true);
    this.message.set(this.i18n.translate('model.saving'));
    this.http.put<any>('/api/settings/model',{...this.draft,api_key:this.apiKey || null,expected_version:this.saved()!.version,confirm_restart:true})
      .pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
        next: res => {
          this.apiKey='';
          if(res.status !== 'restarting') { this.busy.set(false); this.message.set(null); this.error.set(res.message || this.i18n.translate('model.restartManual')); return; }
          this.message.set(this.i18n.translate('model.restarting'));
          this.reconnect(res.previous_pid);
        },
        error: err => { this.busy.set(false); this.message.set(null); this.error.set(this.errorText(err,this.i18n.translate('model.saveError'))); }
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
      complete: ()=> { if(this.destroyRef.destroyed) return; if(recovered) { this.message.set(this.i18n.translate('model.restarted')); this.load(); } else { this.message.set(null); this.error.set(this.i18n.translate('model.timeout')); } }
    });
  }
  private errorText(err:any,fallback:string):string { return typeof err?.error?.detail === 'string' ? err.error.detail : fallback; }
}

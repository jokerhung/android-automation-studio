import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { finalize } from 'rxjs';
import { EmailSettings, EmailSettingsDraft, EmailSettingsUpdate, InlineActionState } from '../../core/models/email-settings.model';
import { EmailSettingsService } from '../../services/email-settings.service';

@Component({
  selector: 'app-email-settings',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './email-settings.component.html',
  styleUrl: './email-settings.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class EmailSettingsComponent implements OnInit {
  private readonly api = inject(EmailSettingsService);
  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);
  readonly saveState = signal<InlineActionState>('idle');
  readonly saveMessage = signal<string | null>(null);
  readonly connectionState = signal<InlineActionState>('idle');
  readonly connectionMessage = signal<string | null>(null);
  readonly sendState = signal<InlineActionState>('idle');
  readonly sendMessage = signal<string | null>(null);
  readonly clearing = signal(false);
  readonly passwordConfigured = signal(false);
  readonly lastTestedAt = signal<string | null>(null);
  readonly lastTestError = signal<string | null>(null);
  private savedFingerprint = '';
  private savedAccount = '';
  draft: EmailSettingsDraft = this.emptyDraft();

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true); this.loadError.set(null);
    this.api.get().pipe(finalize(() => this.loading.set(false))).subscribe({
      next: settings => this.apply(settings),
      error: error => this.loadError.set(this.errorText(error, 'Unable to load email settings.'))
    });
  }

  save(form: NgForm): void {
    this.resetAction('save');
    if (form.invalid) { form.control.markAllAsTouched(); this.saveState.set('error'); this.saveMessage.set('Correct the highlighted email settings before saving.'); return; }
    if (this.passwordConfigured() && !this.draft.password && this.accountFingerprint() !== this.savedAccount && !window.confirm('The SMTP host or username changed. Keep using the saved password with this new account?')) return;
    const testRecipient = this.draft.test_recipient;
    this.saveState.set('pending');
    this.api.save(this.payload()).pipe(finalize(() => { if (this.saveState() === 'pending') this.saveState.set('idle'); })).subscribe({
      next: settings => { this.apply(settings); this.draft.test_recipient = testRecipient || settings.sender_email; this.saveState.set('success'); this.saveMessage.set('Email settings saved. Saving does not prove a message reached an inbox.'); },
      error: error => { this.saveState.set('error'); this.saveMessage.set(this.errorText(error, 'Unable to save email settings.')); }
    });
  }

  clearPassword(): void {
    if (!this.passwordConfigured() || this.clearing() || !window.confirm('Clear the saved SMTP password? Email delivery will remain unavailable until a new password is saved.')) return;
    this.clearing.set(true); this.saveMessage.set(null);
    this.api.clearPassword().pipe(finalize(() => this.clearing.set(false))).subscribe({
      next: settings => { this.apply(settings); this.saveState.set('success'); this.saveMessage.set('SMTP password cleared.'); },
      error: error => { this.saveState.set('error'); this.saveMessage.set(this.errorText(error, 'Unable to clear SMTP password.')); }
    });
  }

  testConnection(): void {
    this.connectionMessage.set(null);
    if (this.dirty()) { this.connectionState.set('error'); this.connectionMessage.set('Save changes before testing so the saved SMTP configuration is used.'); return; }
    this.connectionState.set('pending');
    this.api.testConnection().pipe(finalize(() => { if (this.connectionState() === 'pending') this.connectionState.set('idle'); })).subscribe({
      next: result => { this.connectionState.set(result.success ? 'success' : 'error'); this.connectionMessage.set(result.message); this.lastTestedAt.set(result.tested_at ?? new Date().toISOString()); this.lastTestError.set(result.success ? null : result.message); },
      error: error => { this.connectionState.set('error'); this.connectionMessage.set(this.errorText(error, 'SMTP connection test failed.')); }
    });
  }

  sendTestEmail(): void {
    this.sendMessage.set(null);
    if (this.dirty()) { this.sendState.set('error'); this.sendMessage.set('Save changes before sending a test email.'); return; }
    if (!this.draft.test_recipient.trim()) { this.sendState.set('error'); this.sendMessage.set('Enter a valid test recipient.'); return; }
    this.sendState.set('pending');
    this.api.sendTest(this.draft.test_recipient.trim()).pipe(finalize(() => { if (this.sendState() === 'pending') this.sendState.set('idle'); })).subscribe({
      next: result => { this.sendState.set(result.success ? 'success' : 'error'); this.sendMessage.set(result.message); },
      error: error => { this.sendState.set('error'); this.sendMessage.set(this.errorText(error, 'Unable to send the test email.')); }
    });
  }

  dirty(): boolean { return this.fingerprint() !== this.savedFingerprint || Boolean(this.draft.password); }
  busy(): boolean { return this.saveState() === 'pending' || this.connectionState() === 'pending' || this.sendState() === 'pending' || this.clearing(); }

  private apply(settings: EmailSettings): void {
    this.passwordConfigured.set(Boolean(settings.password_configured));
    this.lastTestedAt.set(settings.last_tested_at ?? null); this.lastTestError.set(settings.last_test_error ?? null);
    this.draft = { enabled: Boolean(settings.enabled), smtp_host: settings.smtp_host ?? '', smtp_port: settings.smtp_port ?? 587, security: settings.security ?? 'starttls', sender_email: settings.sender_email ?? '', sender_name: settings.sender_name ?? '', smtp_username: settings.smtp_username ?? settings.sender_email ?? '', password: '', test_recipient: settings.test_recipient ?? settings.sender_email ?? '', expected_version: settings.version };
    this.savedFingerprint = this.fingerprint();
    this.savedAccount = this.accountFingerprint();
  }
  private payload(): EmailSettingsUpdate { return { enabled: this.draft.enabled, smtp_host: this.draft.smtp_host.trim(), smtp_port: Number(this.draft.smtp_port), security: this.draft.security, sender_email: this.draft.sender_email.trim(), sender_name: this.draft.sender_name.trim(), smtp_username: this.draft.smtp_username.trim(), password: this.draft.password?.trim() || undefined, expected_version: this.draft.expected_version }; }
  private fingerprint(): string { const { password: _password, ...value } = this.payload(); return JSON.stringify(value); }
  private accountFingerprint(): string { return JSON.stringify([this.draft.smtp_host.trim().toLowerCase(), this.draft.smtp_username.trim().toLowerCase()]); }
  private emptyDraft(): EmailSettingsDraft { return { enabled: false, smtp_host: '', smtp_port: 587, security: 'starttls', sender_email: '', sender_name: 'ARTEMIS', smtp_username: '', password: '', test_recipient: '' }; }
  private resetAction(action: 'save'): void { if (action === 'save') { this.saveState.set('idle'); this.saveMessage.set(null); } }
  private errorText(error: any, fallback: string): string { const detail = error?.error?.detail || error?.error?.message; return typeof detail === 'string' ? detail : fallback; }
}

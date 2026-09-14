import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { Router } from '@angular/router';
import { finalize, forkJoin } from 'rxjs';
import { ScheduleDevice, ScheduleRun, ScheduleStatus, ScheduleType, TaskSchedule, TaskScheduleDraft } from '../../core/models/schedule.model';
import { AgentService } from '../../services/agent.service';
import { ScheduleService } from '../../services/schedule.service';
import { EmailSettingsService } from '../../services/email-settings.service';
import { TranslatePipe } from '../../core/i18n/translate.pipe';
import { TranslationService } from '../../core/i18n/translation.service';

const WEEKDAYS = [1, 2, 3, 4, 5, 6, 7].map(value => ({ value }));

@Component({ selector: 'app-task-schedule', standalone: true, imports: [CommonModule, FormsModule, TranslatePipe], templateUrl: './task-schedule.component.html', styleUrl: './task-schedule.component.scss', changeDetection: ChangeDetectionStrategy.OnPush })
export class TaskScheduleComponent implements OnInit {
  private readonly schedulesApi = inject(ScheduleService);
  private readonly agentService = inject(AgentService);
  private readonly emailSettingsApi = inject(EmailSettingsService);
  private readonly router = inject(Router);
  readonly i18n = inject(TranslationService);
  readonly weekdays = WEEKDAYS;
  readonly schedules = signal<TaskSchedule[]>([]);
  readonly devices = signal<ScheduleDevice[]>([]);
  readonly health = signal<ScheduleStatus | null>(null);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly actionId = signal<string | null>(null);
  readonly emailActionRunId = signal<string | null>(null);
  readonly smtpReady = signal(false);
  readonly smtpReadinessKnown = signal(false);
  readonly error = signal<string | null>(null);
  readonly formError = signal<string | null>(null);
  readonly message = signal<string | null>(null);
  readonly formOpen = signal(false);
  readonly editing = signal<TaskSchedule | null>(null);
  readonly preview = signal<string[]>([]);
  readonly previewError = signal<string | null>(null);
  readonly previewLoading = signal(false);
  readonly historySchedule = signal<TaskSchedule | null>(null);
  readonly history = signal<ScheduleRun[]>([]);
  readonly historyLoading = signal(false);
  readonly activeSchedules = computed(() => this.schedules().filter(item => item.enabled));
  readonly pausedSchedules = computed(() => this.schedules().filter(item => !item.enabled));
  draft: TaskScheduleDraft = this.emptyDraft();
  private subjectCustomized = false;

  ngOnInit(): void { this.refresh(); this.loadEmailReadiness(); }

  private loadEmailReadiness(): void {
    this.emailSettingsApi.get().subscribe({
      next: settings => { this.smtpReady.set(Boolean(settings.enabled && settings.smtp_host && settings.sender_email && settings.smtp_username && settings.password_configured)); this.smtpReadinessKnown.set(true); },
      error: () => { this.smtpReady.set(false); this.smtpReadinessKnown.set(true); }
    });
  }

  refresh(): void {
    this.loading.set(true); this.error.set(null);
    forkJoin({ schedules: this.schedulesApi.list(), devices: this.schedulesApi.devices(), health: this.schedulesApi.status() })
      .pipe(finalize(() => this.loading.set(false))).subscribe({
        next: result => { this.schedules.set(result.schedules); this.devices.set(result.devices); this.health.set(result.health); },
        error: error => this.error.set(this.errorText(error, this.i18n.translate('schedule.loadError')))
      });
  }

  newSchedule(): void { this.editing.set(null); this.draft = this.emptyDraft(); this.subjectCustomized = false; this.preview.set([]); this.previewError.set(null); this.formOpen.set(true); this.clearNotices(); }
  edit(schedule: TaskSchedule): void {
    this.editing.set(schedule);
    this.draft = { name: schedule.name, goal: schedule.goal, profile: schedule.profile, device_serial: schedule.device_serial, expected_output: schedule.expected_output ?? '', enable_outputter: schedule.enable_outputter ?? false, verification_level: schedule.verification_level ?? '', explorer_mode: schedule.explorer_mode ?? '', schedule_type: schedule.schedule_type, interval_minutes: schedule.interval_minutes ?? 15, time_of_day: this.normalizeTime(schedule.time_of_day), weekdays: [...(schedule.weekdays ?? [])], timezone: schedule.timezone, enabled: schedule.enabled, email_enabled: schedule.email_enabled ?? false, recipient_name: schedule.recipient_name ?? '', recipient_email: schedule.recipient_email ?? '', email_subject: schedule.email_subject ?? this.suggestedSubject(schedule.name) };
    this.subjectCustomized = Boolean(schedule.email_subject && schedule.email_subject !== this.suggestedSubject(schedule.name));
    this.preview.set([]); this.previewError.set(null); this.formOpen.set(true); this.clearNotices();
  }
  closeForm(): void { if (!this.saving()) { this.formOpen.set(false); this.formError.set(null); this.previewError.set(null); } }
  setScheduleType(type: ScheduleType): void { this.draft.schedule_type = type; this.preview.set([]); this.previewError.set(null); }
  toggleWeekday(day: number, selected: boolean): void { const values = new Set(this.draft.weekdays ?? []); selected ? values.add(day) : values.delete(day); this.draft.weekdays = [...values].sort(); this.preview.set([]); this.previewError.set(null); }
  onScheduleNameChange(): void { if (!this.subjectCustomized) this.draft.email_subject = this.suggestedSubject(this.draft.name); }
  onEmailToggle(): void { if (this.draft.email_enabled && !this.draft.email_subject) { this.draft.email_subject = this.suggestedSubject(this.draft.name); this.subjectCustomized = false; } }
  onSubjectChange(): void { this.subjectCustomized = this.draft.email_subject !== this.suggestedSubject(this.draft.name); }
  useSuggestedSubject(): void { this.draft.email_subject = this.suggestedSubject(this.draft.name); this.subjectCustomized = false; }
  suggestedSubject(name = this.draft.name): string { return 'ARTEMIS — ' + (name.trim() || '{schedule_name}') + ' — {status}'; }
  openEmailSettings(): void { void this.router.navigate(['/settings'], { queryParams: { tab: 'email' } }); }

  requestPreview(form: NgForm): void {
    this.clearNotices();
    this.previewError.set(null);
    if (!this.valid(form, 'preview')) return;
    this.previewLoading.set(true);
    this.schedulesApi.preview(this.payload()).pipe(finalize(() => this.previewLoading.set(false))).subscribe({
      next: times => this.preview.set(times),
      error: error => {
        this.preview.set([]);
        this.previewError.set(this.errorText(error, this.i18n.translate('schedule.previewError')));
      }
    });
  }

  save(form: NgForm): void {
    this.clearNotices();
    if (!this.valid(form)) return;
    if (!this.preview().length) { this.formError.set(this.i18n.translate('schedule.previewRequired')); return; }
    this.saving.set(true);
    const current = this.editing();
    const request = current ? this.schedulesApi.update(current, this.payload()) : this.schedulesApi.create(this.payload());
    request.pipe(finalize(() => this.saving.set(false))).subscribe({
      next: saved => { this.upsert(saved); this.formOpen.set(false); this.message.set(this.i18n.translate(current ? 'schedule.updatedMessage' : 'schedule.savedMessage')); },
      error: error => this.formError.set(this.errorText(error, this.i18n.translate('schedule.saveError')))
    });
  }

  pauseResume(schedule: TaskSchedule): void { this.perform(schedule, this.schedulesApi.setEnabled(schedule, !schedule.enabled), updated => { this.upsert(updated); this.message.set(this.i18n.translate(updated.enabled ? 'schedule.resumedMessage' : 'schedule.pausedMessage')); }); }
  runNow(schedule: TaskSchedule): void { this.perform(schedule, this.schedulesApi.runNow(schedule.id), () => { this.message.set(this.i18n.translate('schedule.runNowMessage')); this.openHistory(schedule); }); }
  remove(schedule: TaskSchedule): void { if (!window.confirm(this.i18n.translate('schedule.deleteConfirm'))) return; this.perform(schedule, this.schedulesApi.delete(schedule), () => { this.schedules.update(items => items.filter(item => item.id !== schedule.id)); if (this.historySchedule()?.id === schedule.id) this.closeHistory(); this.message.set(this.i18n.translate('schedule.deletedMessage')); }); }

  openHistory(schedule: TaskSchedule): void { this.historySchedule.set(schedule); this.history.set([]); this.historyLoading.set(true); this.schedulesApi.runs(schedule.id).pipe(finalize(() => this.historyLoading.set(false))).subscribe({ next: runs => this.history.set(runs), error: error => this.error.set(this.errorText(error, this.i18n.translate('schedule.historyError'))) }); }
  closeHistory(): void { this.historySchedule.set(null); this.history.set([]); }
  openSession(sessionId: string): void { this.agentService.selectSession(sessionId); void this.router.navigate(['/workspace']); }
  notification(run: ScheduleRun) { return run.email_notification ?? run.notification ?? (run.email_status ? { status: run.email_status } : null); }
  notificationLabel(status: string): string { const keys = { pending: 'schedule.emailPending', retry: 'schedule.emailRetry', sending: 'schedule.emailSending', accepted_by_smtp: 'schedule.emailAccepted', failed: 'schedule.emailFailed', delivery_unknown: 'schedule.emailUnknown', suppressed: 'schedule.emailSuppressed', report_incomplete: 'schedule.emailReportIncomplete', attachment_too_large: 'schedule.emailAttachmentLarge' } as const; return keys[status as keyof typeof keys] ? this.i18n.translate(keys[status as keyof typeof keys]) : status.replaceAll('_', ' '); }
  canRetryEmail(run: ScheduleRun): boolean { const note = this.notification(run); return Boolean(note?.can_retry || ['failed', 'delivery_unknown', 'report_incomplete', 'attachment_too_large'].includes(note?.status ?? '')); }
  canReviewReport(run: ScheduleRun): boolean { const note = this.notification(run); return Boolean(note?.report_available || note?.status === 'accepted_by_smtp'); }
  retryEmail(run: ScheduleRun): void {
    const schedule = this.historySchedule(); if (!schedule || this.emailActionRunId()) return;
    const note = this.notification(run);
    if (note?.status === 'delivery_unknown' && !window.confirm(this.i18n.translate('schedule.duplicateConfirm'))) return;
    this.emailActionRunId.set(run.id);
    this.schedulesApi.retryEmail(schedule.id, run.id).pipe(finalize(() => this.emailActionRunId.set(null))).subscribe({
      next: updated => { this.history.update(items => items.map(item => item.id === run.id ? { ...item, email_notification: { ...(this.notification(item) ?? {}), status: updated.status, can_retry: false } } : item)); this.message.set(this.i18n.translate('schedule.retryQueued')); },
      error: error => this.error.set(this.errorText(error, this.i18n.translate('schedule.retryError')))
    });
  }
  reviewReport(run: ScheduleRun): void { const schedule = this.historySchedule(); if (schedule) window.open(this.schedulesApi.emailReportUrl(schedule.id, run.id), '_blank', 'noopener'); }

  ruleText(schedule: TaskSchedule): string {
    if (schedule.schedule_type === 'interval') return this.i18n.translate('schedule.everyMinutes', { count: schedule.interval_minutes ?? '' });
    const time = this.normalizeTime(schedule.time_of_day);
    if (schedule.schedule_type === 'daily') return this.i18n.translate('schedule.dailyAt', { time });
    const labels = (schedule.weekdays ?? []).map(day => this.i18n.translate('weekday.' + day)).filter(Boolean).join(', ');
    return this.i18n.translate('schedule.daysAt', { days: labels || this.i18n.translate('schedule.noDays'), time });
  }
  runStatus(status?: string | null): string { if (!status) return this.i18n.translate('schedule.noRuns'); const keys = { pending: 'schedule.statusPending', queued: 'schedule.statusQueued', running: 'schedule.statusRunning', completed: 'schedule.statusCompleted', failed: 'schedule.statusFailed', cancelled: 'schedule.statusCancelled', canceled: 'schedule.statusCancelled' } as const; return keys[status as keyof typeof keys] ? this.i18n.translate(keys[status as keyof typeof keys]) : status.replaceAll('_', ' '); }
  triggerLabel(trigger?: string | null): string { if (!trigger) return ''; return this.i18n.translate(trigger === 'scheduled' ? 'schedule.triggerScheduled' : trigger === 'manual' || trigger === 'run_now' ? 'schedule.triggerManual' : trigger); }
  latenessLabel(value: number): string { return this.i18n.translate('schedule.lateMs', { value }); }
  deviceLabel(serial: string): string { const device = this.devices().find(value => value.serial === serial); return device ? ((device.name || device.model || serial) + (device.serial !== (device.name || device.model) ? ' · ' + device.serial : '')) : serial; }
  trackById(_index: number, value: { id: string }): string { return value.id; }

  private valid(form: NgForm, target: 'form' | 'preview' = 'form'): boolean {
    const error = target === 'preview' ? this.previewError : this.formError;
    if (form.invalid) { form.control.markAllAsTouched(); error.set(this.i18n.translate('schedule.requiredFields')); return false; }
    if (this.draft.schedule_type === 'weekly' && !(this.draft.weekdays?.length)) { error.set(this.i18n.translate('schedule.weekdayRequired')); return false; }
    if (target === 'form' && this.draft.email_enabled && !this.smtpReady()) { error.set(this.i18n.translate('schedule.smtpRequired')); return false; }
    return true;
  }
  private payload(): TaskScheduleDraft { return { ...this.draft, name: this.draft.name.trim(), goal: this.draft.goal.trim(), expected_output: this.draft.expected_output?.trim() || null, enable_outputter: Boolean(this.draft.enable_outputter), verification_level: this.draft.verification_level?.trim() || null, explorer_mode: this.draft.explorer_mode?.trim() || null, interval_minutes: this.draft.schedule_type === 'interval' ? Number(this.draft.interval_minutes) : null, time_of_day: this.draft.schedule_type === 'interval' ? null : this.normalizeTime(this.draft.time_of_day), weekdays: this.draft.schedule_type === 'weekly' ? this.draft.weekdays : [], email_enabled: Boolean(this.draft.email_enabled), recipient_name: this.draft.email_enabled ? this.draft.recipient_name?.trim() || null : null, recipient_email: this.draft.email_enabled ? this.draft.recipient_email?.trim() || null : null, email_subject: this.draft.email_enabled ? this.draft.email_subject?.trim() || null : null }; }
  private emptyDraft(): TaskScheduleDraft { let timezone = 'UTC'; try { timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; } catch {} return { name: '', goal: '', profile: 'flash', device_serial: '', expected_output: '', enable_outputter: false, verification_level: '', explorer_mode: '', schedule_type: 'interval', interval_minutes: 15, time_of_day: '08:30:00', weekdays: [1], timezone, enabled: true, email_enabled: false, recipient_name: '', recipient_email: '', email_subject: this.suggestedSubject('') }; }
  private normalizeTime(value?: string | null): string { const parts = (value || '00:00:00').split(':'); return [parts[0] || '00', parts[1] || '00', parts[2] || '00'].map(part => part.padStart(2, '0')).join(':'); }
  private upsert(schedule: TaskSchedule): void { this.schedules.update(items => { const index = items.findIndex(item => item.id === schedule.id); return index < 0 ? [schedule, ...items] : items.map(item => item.id === schedule.id ? schedule : item); }); }
  private perform<T>(schedule: TaskSchedule, request: import('rxjs').Observable<T>, done: (value: T) => void): void { this.clearNotices(); this.actionId.set(schedule.id); request.pipe(finalize(() => this.actionId.set(null))).subscribe({ next: done, error: error => this.error.set(this.errorText(error, this.i18n.translate('schedule.actionFailed'))) }); }
  private clearNotices(): void { this.error.set(null); this.formError.set(null); this.message.set(null); }
  private errorText(error: any, fallback: string): string {
    const detail = error?.error?.detail || error?.error?.message;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map(item => typeof item === 'string' ? item : item?.msg).filter(Boolean).join('; ') || fallback;
    }
    return fallback;
  }
}

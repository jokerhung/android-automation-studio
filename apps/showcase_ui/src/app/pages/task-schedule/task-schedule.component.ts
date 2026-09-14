import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { Router } from '@angular/router';
import { finalize, forkJoin } from 'rxjs';
import { ScheduleDevice, ScheduleRun, ScheduleStatus, ScheduleType, TaskSchedule, TaskScheduleDraft } from '../../core/models/schedule.model';
import { AgentService } from '../../services/agent.service';
import { ScheduleService } from '../../services/schedule.service';

const WEEKDAYS = [{ value: 1, label: 'Mon' }, { value: 2, label: 'Tue' }, { value: 3, label: 'Wed' }, { value: 4, label: 'Thu' }, { value: 5, label: 'Fri' }, { value: 6, label: 'Sat' }, { value: 7, label: 'Sun' }];

@Component({ selector: 'app-task-schedule', standalone: true, imports: [CommonModule, FormsModule], templateUrl: './task-schedule.component.html', styleUrl: './task-schedule.component.scss', changeDetection: ChangeDetectionStrategy.OnPush })
export class TaskScheduleComponent implements OnInit {
  private readonly schedulesApi = inject(ScheduleService);
  private readonly agentService = inject(AgentService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  readonly weekdays = WEEKDAYS;
  readonly schedules = signal<TaskSchedule[]>([]);
  readonly devices = signal<ScheduleDevice[]>([]);
  readonly health = signal<ScheduleStatus | null>(null);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly actionId = signal<string | null>(null);
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

  ngOnInit(): void { this.refresh(); }

  refresh(): void {
    this.loading.set(true); this.error.set(null);
    forkJoin({ schedules: this.schedulesApi.list(), devices: this.schedulesApi.devices(), health: this.schedulesApi.status() })
      .pipe(finalize(() => this.loading.set(false))).subscribe({
        next: result => { this.schedules.set(result.schedules); this.devices.set(result.devices); this.health.set(result.health); },
        error: error => this.error.set(this.errorText(error, 'Unable to load schedules. Is the scheduler API available?'))
      });
  }

  newSchedule(): void { this.editing.set(null); this.draft = this.emptyDraft(); this.preview.set([]); this.previewError.set(null); this.formOpen.set(true); this.clearNotices(); }
  edit(schedule: TaskSchedule): void {
    this.editing.set(schedule);
    this.draft = { name: schedule.name, goal: schedule.goal, profile: schedule.profile, device_serial: schedule.device_serial, expected_output: schedule.expected_output ?? '', enable_outputter: schedule.enable_outputter ?? false, verification_level: schedule.verification_level ?? '', explorer_mode: schedule.explorer_mode ?? '', schedule_type: schedule.schedule_type, interval_minutes: schedule.interval_minutes ?? 15, time_of_day: this.normalizeTime(schedule.time_of_day), weekdays: [...(schedule.weekdays ?? [])], timezone: schedule.timezone, enabled: schedule.enabled };
    this.preview.set([]); this.previewError.set(null); this.formOpen.set(true); this.clearNotices();
  }
  closeForm(): void { if (!this.saving()) { this.formOpen.set(false); this.formError.set(null); this.previewError.set(null); } }
  setScheduleType(type: ScheduleType): void { this.draft.schedule_type = type; this.preview.set([]); this.previewError.set(null); }
  toggleWeekday(day: number, selected: boolean): void { const values = new Set(this.draft.weekdays ?? []); selected ? values.add(day) : values.delete(day); this.draft.weekdays = [...values].sort(); this.preview.set([]); this.previewError.set(null); }

  requestPreview(form: NgForm): void {
    this.clearNotices();
    this.previewError.set(null);
    if (!this.valid(form, 'preview')) return;
    this.previewLoading.set(true);
    this.schedulesApi.preview(this.payload()).pipe(finalize(() => this.previewLoading.set(false))).subscribe({
      next: times => this.preview.set(times),
      error: error => {
        this.preview.set([]);
        this.previewError.set(this.errorText(error, 'Backend could not preview this schedule.'));
      }
    });
  }

  save(form: NgForm): void {
    this.clearNotices();
    if (!this.valid(form)) return;
    if (!this.preview().length) { this.formError.set('Preview the next five runs before saving.'); return; }
    this.saving.set(true);
    const current = this.editing();
    const request = current ? this.schedulesApi.update(current, this.payload()) : this.schedulesApi.create(this.payload());
    request.pipe(finalize(() => this.saving.set(false))).subscribe({
      next: saved => { this.upsert(saved); this.formOpen.set(false); this.message.set(current ? 'Schedule updated. Changes apply to future runs.' : 'Schedule saved. It will not run until its due time.'); },
      error: error => this.formError.set(this.errorText(error, 'Unable to save schedule. Refresh if another tab changed it.'))
    });
  }

  pauseResume(schedule: TaskSchedule): void { this.perform(schedule, this.schedulesApi.setEnabled(schedule, !schedule.enabled), updated => { this.upsert(updated); this.message.set(updated.enabled ? 'Schedule resumed; its next run was recalculated.' : 'Schedule paused. Already queued or running tasks are not stopped.'); }); }
  runNow(schedule: TaskSchedule): void { this.perform(schedule, this.schedulesApi.runNow(schedule.id), () => { this.message.set('Run now request accepted. The scheduled next run is unchanged.'); this.openHistory(schedule); }); }
  remove(schedule: TaskSchedule): void { if (!window.confirm('Delete this schedule? Existing sessions and run history will be kept.')) return; this.perform(schedule, this.schedulesApi.delete(schedule), () => { this.schedules.update(items => items.filter(item => item.id !== schedule.id)); if (this.historySchedule()?.id === schedule.id) this.closeHistory(); this.message.set('Schedule deleted; its session history was preserved.'); }); }

  openHistory(schedule: TaskSchedule): void { this.historySchedule.set(schedule); this.history.set([]); this.historyLoading.set(true); this.schedulesApi.runs(schedule.id).pipe(finalize(() => this.historyLoading.set(false))).subscribe({ next: runs => this.history.set(runs), error: error => this.error.set(this.errorText(error, 'Unable to load schedule history.')) }); }
  closeHistory(): void { this.historySchedule.set(null); this.history.set([]); }
  openSession(sessionId: string): void { this.agentService.selectSession(sessionId); void this.router.navigate(['/workspace']); }

  ruleText(schedule: TaskSchedule): string {
    if (schedule.schedule_type === 'interval') return 'Every ' + schedule.interval_minutes + ' minute' + (schedule.interval_minutes === 1 ? '' : 's');
    const time = this.normalizeTime(schedule.time_of_day);
    if (schedule.schedule_type === 'daily') return 'Daily at ' + time;
    const labels = (schedule.weekdays ?? []).map(day => WEEKDAYS.find(value => value.value === day)?.label).filter(Boolean).join(', ');
    return (labels || 'No days') + ' at ' + time;
  }
  deviceLabel(serial: string): string { const device = this.devices().find(value => value.serial === serial); return device ? ((device.name || device.model || serial) + (device.serial !== (device.name || device.model) ? ' · ' + device.serial : '')) : serial; }
  trackById(_index: number, value: { id: string }): string { return value.id; }

  private valid(form: NgForm, target: 'form' | 'preview' = 'form'): boolean {
    const error = target === 'preview' ? this.previewError : this.formError;
    if (form.invalid) { form.control.markAllAsTouched(); error.set('Complete all required fields and correct the highlighted values.'); return false; }
    if (this.draft.schedule_type === 'weekly' && !(this.draft.weekdays?.length)) { error.set('Select at least one weekday.'); return false; }
    return true;
  }
  private payload(): TaskScheduleDraft { return { ...this.draft, name: this.draft.name.trim(), goal: this.draft.goal.trim(), expected_output: this.draft.expected_output?.trim() || null, enable_outputter: Boolean(this.draft.enable_outputter), verification_level: this.draft.verification_level?.trim() || null, explorer_mode: this.draft.explorer_mode?.trim() || null, interval_minutes: this.draft.schedule_type === 'interval' ? Number(this.draft.interval_minutes) : null, time_of_day: this.draft.schedule_type === 'interval' ? null : this.normalizeTime(this.draft.time_of_day), weekdays: this.draft.schedule_type === 'weekly' ? this.draft.weekdays : [] }; }
  private emptyDraft(): TaskScheduleDraft { let timezone = 'UTC'; try { timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; } catch {} return { name: '', goal: '', profile: 'flash', device_serial: '', expected_output: '', enable_outputter: false, verification_level: '', explorer_mode: '', schedule_type: 'interval', interval_minutes: 15, time_of_day: '08:30:00', weekdays: [1], timezone, enabled: true }; }
  private normalizeTime(value?: string | null): string { const parts = (value || '00:00:00').split(':'); return [parts[0] || '00', parts[1] || '00', parts[2] || '00'].map(part => part.padStart(2, '0')).join(':'); }
  private upsert(schedule: TaskSchedule): void { this.schedules.update(items => { const index = items.findIndex(item => item.id === schedule.id); return index < 0 ? [schedule, ...items] : items.map(item => item.id === schedule.id ? schedule : item); }); }
  private perform<T>(schedule: TaskSchedule, request: import('rxjs').Observable<T>, done: (value: T) => void): void { this.clearNotices(); this.actionId.set(schedule.id); request.pipe(finalize(() => this.actionId.set(null))).subscribe({ next: done, error: error => this.error.set(this.errorText(error, 'Schedule action failed.')) }); }
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

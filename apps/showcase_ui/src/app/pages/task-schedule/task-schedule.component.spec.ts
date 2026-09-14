import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AgentService } from '../../services/agent.service';
import { ScheduleService } from '../../services/schedule.service';
import { EmailSettingsService } from '../../services/email-settings.service';
import { TaskScheduleComponent } from './task-schedule.component';
import { UiPreferencesService } from '../../services/ui-preferences.service';

describe('TaskScheduleComponent', () => {
  let fixture: ComponentFixture<TaskScheduleComponent>;
  let component: TaskScheduleComponent;
  const scheduleApi = jasmine.createSpyObj<ScheduleService>('ScheduleService', ['list', 'devices', 'status', 'preview', 'create', 'update', 'setEnabled', 'delete', 'runNow', 'runs', 'retryEmail', 'emailReportUrl']);
  const emailApi = jasmine.createSpyObj<EmailSettingsService>('EmailSettingsService', ['get']);
  const agent = jasmine.createSpyObj<AgentService>('AgentService', ['selectSession']);

  beforeEach(async () => {
    scheduleApi.list.and.returnValue(of([]));
    scheduleApi.devices.and.returnValue(of([{ serial: 'pixel-1', name: 'Pixel 8' }]));
    scheduleApi.status.and.returnValue(of({ healthy: true, last_heartbeat: '2026-09-14T04:00:00Z' }));
    emailApi.get.and.returnValue(of({ enabled: true, smtp_host: 'smtp.example.com', smtp_port: 587, security: 'starttls', sender_email: 'sender@example.com', smtp_username: 'sender@example.com', password_configured: true }));
    await TestBed.configureTestingModule({
      imports: [TaskScheduleComponent],
      providers: [provideRouter([]), { provide: ScheduleService, useValue: scheduleApi }, { provide: EmailSettingsService, useValue: emailApi }, { provide: AgentService, useValue: agent }]
    }).compileComponents();
    fixture = TestBed.createComponent(TaskScheduleComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('loads health, devices, and the empty state', () => {
    expect(scheduleApi.list).toHaveBeenCalled();
    expect(component.health()?.healthy).toBeTrue();
    expect(component.devices()[0].serial).toBe('pixel-1');
    expect(fixture.nativeElement.textContent).toContain('No schedules yet');
  });

  it('translates the schedule page, create form, and history actions to Vietnamese', () => {
    const preferences = TestBed.inject(UiPreferencesService);
    preferences.setLanguage('vi');
    component.newSchedule();
    component.draft.email_enabled = true;
    component.historySchedule.set({ id: 's1', name: 'Lịch kiểm tra' } as any);
    component.historyLoading.set(false);
    component.history.set([{ id: 'r1', schedule_id: 's1', due_at: '2026-09-14T08:00:00Z', trigger: 'scheduled', status: 'completed', email_notification: { status: 'failed', can_retry: true } }] as any);
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Lịch tác vụ');
    expect(text).toContain('Tạo lịch tác vụ');
    expect(text).toContain('Hướng dẫn tác vụ');
    expect(text).toContain('Xem trước 5 lần tiếp theo');
    expect(text).toContain('Email: Thất bại');
    expect(text).toContain('Gửi lại email');
    preferences.setLanguage('en');
    fixture.detectChanges();
  });

  it('shows schedule email policy directly on each card', () => {
    component.schedules.set([{ id: 'email-card', version: 1, name: 'Email result', goal: 'Check app', profile: 'flash', device_serial: 'pixel-1', enabled: true, schedule_type: 'daily', time_of_day: '08:30:00', timezone: 'UTC', email_enabled: true, recipient_email: 'ops@example.com' }]);
    fixture.detectChanges();
    const card = fixture.nativeElement.querySelector('.schedule-card');
    expect(card.textContent).toContain('Email');
    expect(card.textContent).toContain('ops@example.com');
  });

  it('keeps seconds and ISO weekdays in readable rules', () => {
    expect(component.ruleText({
      id: 'weekly-1', version: 1, name: 'Weekly', goal: 'Check app', profile: 'flash', device_serial: 'pixel-1',
      enabled: true, schedule_type: 'weekly', weekdays: [1, 3, 5], time_of_day: '09:00:00', timezone: 'Asia/Bangkok'
    })).toBe('Mon, Wed, Fri at 09:00:00');
  });

  it('shows preview API errors inside the open schedule dialog', () => {
    scheduleApi.preview.and.returnValue(throwError(() => ({ error: { detail: 'Invalid timezone' } })));
    component.newSchedule();
    component.draft.name = 'Test';
    component.draft.goal = 'Open settings';
    component.draft.device_serial = 'pixel-1';
    component.requestPreview({ invalid: false, control: { markAllAsTouched: () => undefined } } as any);
    fixture.detectChanges();

    const modal = fixture.nativeElement.querySelector('.form-modal');
    expect(modal.textContent).toContain('Invalid timezone');
    expect(component.error()).toBeNull();
  });

  it('opens a new schedule with the browser timezone and default interval', () => {
    component.newSchedule();
    expect(component.formOpen()).toBeTrue();
    expect(component.draft.schedule_type).toBe('interval');
    expect(component.draft.interval_minutes).toBe(15);
    expect(component.draft.timezone).toBeTruthy();
  });

  it('omits advanced task options while keeping the schedule fields', () => {
    component.newSchedule();
    fixture.detectChanges();
    const modal = fixture.nativeElement.querySelector('.form-modal');
    expect(modal.textContent).not.toContain('Advanced task options');
    expect(modal.querySelector('[name="outputter"]')).toBeNull();
    expect(modal.querySelector('[name="verification"]')).toBeNull();
    expect(modal.querySelector('[name="explorer"]')).toBeNull();
    expect(modal.querySelector('[name="name"]')).not.toBeNull();
    expect(modal.querySelector('[name="interval"]')).not.toBeNull();
    expect(modal.textContent).toContain('Preview next 5');
  });

  it('shows missing required fields beside Preview next 5, not on the list', async () => {
    component.newSchedule();
    fixture.detectChanges();
    await fixture.whenStable();
    const modal = fixture.nativeElement.querySelector('.form-modal');
    modal.querySelector('.preview button').click();
    fixture.detectChanges();
    expect(modal.querySelector('.preview-error').textContent).toContain('Complete all required fields');
    expect(modal.querySelector('input[name="name"]').classList).toContain('ng-touched');
    expect(fixture.nativeElement.querySelector('.schedule-page [role="alert"]')).toBeNull();
  });

  it('keeps weekly validation errors in the form for both actions', () => {
    component.newSchedule();
    component.draft.schedule_type = 'weekly';
    component.draft.weekdays = [];
    const form = { invalid: false } as any;
    component.requestPreview(form);
    expect(component.previewError()).toBe('Select at least one weekday.');
    component.save(form);
    expect(component.formError()).toBe('Select at least one weekday.');
    expect(component.error()).toBeNull();
  });

  it('shows the preview-before-save message inside the dialog', () => {
    component.newSchedule();
    component.save({ invalid: false } as any);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.form-modal .form-error').textContent).toContain('Preview the next five');
    expect(component.formOpen()).toBeTrue();
    expect(component.error()).toBeNull();
  });

  it('shows create errors inline without closing the form or losing the draft', () => {
    component.newSchedule();
    component.draft.name = 'Keep my draft';
    component.preview.set(['2026-09-14T08:00:00Z']);
    scheduleApi.create.and.returnValue(throwError(() => ({ error: { detail: [{ msg: 'Invalid timezone' }] } })));
    component.save({ invalid: false } as any);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.form-modal .form-error').textContent).toContain('Invalid timezone');
    expect(component.draft.name).toBe('Keep my draft');
    expect(component.formOpen()).toBeTrue();
    expect(component.saving()).toBeFalse();
    expect(component.error()).toBeNull();
    component.closeForm();
    component.newSchedule();
    expect(component.formError()).toBeNull();
    expect(component.previewError()).toBeNull();
  });

  it('keeps schedule email off by default and suggests a subject without overwriting edits', () => {
    component.newSchedule();
    expect(component.draft.email_enabled).toBeFalse();
    component.draft.name = 'Morning check'; component.onScheduleNameChange();
    expect(component.draft.email_subject).toBe('ARTEMIS — Morning check — {status}');
    component.draft.email_subject = 'My custom subject'; component.onSubjectChange(); component.draft.name = 'Changed'; component.onScheduleNameChange();
    expect(component.draft.email_subject).toBe('My custom subject');
  });

  it('renders opt-in fields, summary body, attachment, and preview safety copy', () => {
    component.newSchedule(); component.draft.email_enabled = true; component.onEmailToggle(); fixture.detectChanges();
    const modal = fixture.nativeElement.querySelector('.form-modal');
    expect(modal.querySelector('[name="recipientName"]')).not.toBeNull();
    expect(modal.querySelector('[name="recipientEmail"]')).not.toBeNull();
    expect(modal.querySelector('[name="emailSubject"]')).not.toBeNull();
    expect(modal.textContent).toContain("final summary after completion");
    expect(modal.textContent).toContain('Full execution log (.txt), with secrets redacted');
    expect(modal.textContent).toContain('Preview never sends email');
  });

  it('sends trimmed opt-in fields in create payload and omits them while off', () => {
    const form = { invalid: false } as any;
    component.newSchedule(); Object.assign(component.draft, { name: ' Daily ', goal: ' Check ', device_serial: 'pixel-1', email_enabled: true, recipient_name: ' Ops ', recipient_email: ' ops@example.com ', email_subject: ' Result {status} ' });
    component.preview.set(['2026-09-14T08:00:00Z']); scheduleApi.create.and.returnValue(of({ ...component.draft, id: 'created', version: 1 } as any)); component.save(form);
    const enabledPayload = scheduleApi.create.calls.mostRecent().args[0];
    expect(enabledPayload.recipient_name).toBe('Ops'); expect(enabledPayload.recipient_email).toBe('ops@example.com'); expect(enabledPayload.email_subject).toBe('Result {status}');
    scheduleApi.create.calls.reset(); component.newSchedule(); Object.assign(component.draft, { name: 'No email', goal: 'Check', device_serial: 'pixel-1', email_enabled: false, recipient_name: 'Ignore', recipient_email: 'ignore@example.com', email_subject: 'Ignore' });
    component.preview.set(['2026-09-14T08:00:00Z']); scheduleApi.create.and.returnValue(of({ ...component.draft, id: 'created-2', version: 1 } as any)); component.save(form);
    const disabledPayload = scheduleApi.create.calls.mostRecent().args[0];
    expect(disabledPayload.recipient_name).toBeNull(); expect(disabledPayload.recipient_email).toBeNull(); expect(disabledPayload.email_subject).toBeNull();
  });

  it('allows preview while SMTP is unavailable but blocks save', () => {
    component.newSchedule(); Object.assign(component.draft, { name: 'Test', goal: 'Open settings', device_serial: 'pixel-1', email_enabled: true, recipient_email: 'ops@example.com' }); component.smtpReady.set(false);
    scheduleApi.preview.and.returnValue(of(['2026-09-14T08:00:00Z'])); component.requestPreview({ invalid: false } as any);
    expect(scheduleApi.preview).toHaveBeenCalled(); expect(component.preview().length).toBe(1);
  });

  it('shows SMTP readiness inline and blocks saving an enabled notification', () => {
    component.newSchedule(); component.draft.email_enabled = true; component.smtpReady.set(false); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.smtp-warning').textContent).toContain('SMTP is not ready');
    component.preview.set(['2026-09-14T08:00:00Z']); component.save({ invalid: false } as any);
    expect(component.formError()).toContain('Settings → Email');
  });

  it('renders notification state, safe error, retry, and report actions in history', () => {
    component.historySchedule.set({ id: 's1', name: 'Schedule' } as any); component.historyLoading.set(false); component.history.set([
      { id: 'failed', schedule_id: 's1', due_at: '2026-09-14T08:00:00Z', trigger: 'scheduled', status: 'completed', email_notification: { status: 'failed', safe_error_message: 'Authentication failed safely' } },
      { id: 'accepted', schedule_id: 's1', due_at: '2026-09-14T09:00:00Z', trigger: 'scheduled', status: 'completed', email_notification: { status: 'accepted_by_smtp', accepted_at: '2026-09-14T09:01:00Z' } }
    ] as any); fixture.detectChanges();
    const history = fixture.nativeElement.querySelector('.history-modal');
    expect(history.textContent).toContain('Email: Failed'); expect(history.textContent).toContain('Authentication failed safely'); expect(history.textContent).toContain('Retry email');
    expect(history.textContent).toContain('Email: Accepted by SMTP'); expect(history.textContent).toContain('Review report');
  });

  it('requires confirmation before retrying an unknown delivery', () => {
    scheduleApi.retryEmail.calls.reset();
    const confirm = spyOn(window, 'confirm').and.returnValue(false); const run = { id: 'r1', email_notification: { status: 'delivery_unknown' } } as any;
    component.historySchedule.set({ id: 's1' } as any); component.retryEmail(run);
    expect(confirm).toHaveBeenCalled(); expect(scheduleApi.retryEmail).not.toHaveBeenCalled();
  });

  it('opens the sanitized report endpoint in a new tab', () => {
    const opened = spyOn(window, 'open'); const run = { id: 'r1' } as any; component.historySchedule.set({ id: 's1' } as any); scheduleApi.emailReportUrl.and.returnValue('/report');
    component.reviewReport(run); expect(scheduleApi.emailReportUrl).toHaveBeenCalledWith('s1', 'r1'); expect(opened).toHaveBeenCalledWith('/report', '_blank', 'noopener');
  });

  it('retries only email and does not run the task again', () => {
    const schedule = { id: 's1', name: 'Schedule' } as any; const run = { id: 'r1', schedule_id: 's1', due_at: '2026-09-14T08:00:00Z', trigger: 'scheduled', status: 'completed', email_notification: { status: 'failed', can_retry: true } } as any;
    component.historySchedule.set(schedule); component.history.set([run]); scheduleApi.retryEmail.and.returnValue(of({ run_id: 'r1', status: 'pending' }));
    component.retryEmail(run);
    expect(scheduleApi.retryEmail).toHaveBeenCalledWith('s1', 'r1'); expect(scheduleApi.runNow).not.toHaveBeenCalled(); expect(component.history()[0].email_notification?.status).toBe('pending');
  });

  it('keeps the schedule form and draft open when the backdrop is clicked', () => {
    component.newSchedule();
    component.draft.name = 'Unsaved schedule';
    fixture.detectChanges();
    fixture.nativeElement.querySelector('.form-modal').parentElement.click();
    fixture.detectChanges();
    expect(component.formOpen()).toBeTrue();
    expect(component.draft.name).toBe('Unsaved schedule');
    expect(fixture.nativeElement.querySelector('.form-modal')).not.toBeNull();
  });

  it('still closes the schedule form through Cancel and the close button', () => {
    component.newSchedule();
    fixture.detectChanges();
    fixture.nativeElement.querySelector('.form-modal footer button[type="button"]').click();
    fixture.detectChanges();
    expect(component.formOpen()).toBeFalse();
    component.newSchedule();
    fixture.detectChanges();
    fixture.nativeElement.querySelector('[aria-label="Close schedule form"]').click();
    fixture.detectChanges();
    expect(component.formOpen()).toBeFalse();
  });

  it('shows edit conflicts in the same dialog', () => {
    component.newSchedule();
    component.editing.set({ id: 'existing', version: 1 } as any);
    component.preview.set(['2026-09-14T08:00:00Z']);
    scheduleApi.update.and.returnValue(throwError(() => ({ error: { detail: 'Schedule changed in another tab' } })));
    component.save({ invalid: false } as any);
    expect(component.formError()).toBe('Schedule changed in another tab');
    expect(component.error()).toBeNull();
    expect(component.formOpen()).toBeTrue();
  });
});

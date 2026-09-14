import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AgentService } from '../../services/agent.service';
import { ScheduleService } from '../../services/schedule.service';
import { TaskScheduleComponent } from './task-schedule.component';

describe('TaskScheduleComponent', () => {
  let fixture: ComponentFixture<TaskScheduleComponent>;
  let component: TaskScheduleComponent;
  const scheduleApi = jasmine.createSpyObj<ScheduleService>('ScheduleService', ['list', 'devices', 'status', 'preview', 'create', 'update', 'setEnabled', 'delete', 'runNow', 'runs']);
  const agent = jasmine.createSpyObj<AgentService>('AgentService', ['selectSession']);

  beforeEach(async () => {
    scheduleApi.list.and.returnValue(of([]));
    scheduleApi.devices.and.returnValue(of([{ serial: 'pixel-1', name: 'Pixel 8' }]));
    scheduleApi.status.and.returnValue(of({ healthy: true, last_heartbeat: '2026-09-14T04:00:00Z' }));
    await TestBed.configureTestingModule({
      imports: [TaskScheduleComponent],
      providers: [provideRouter([]), { provide: ScheduleService, useValue: scheduleApi }, { provide: AgentService, useValue: agent }]
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

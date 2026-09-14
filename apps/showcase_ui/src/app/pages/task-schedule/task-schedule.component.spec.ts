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
});

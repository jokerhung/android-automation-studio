import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { TaskScheduleDraft } from '../core/models/schedule.model';
import { ScheduleService } from './schedule.service';

describe('ScheduleService', () => {
  let service: ScheduleService;
  let http: HttpTestingController;
  const draft: TaskScheduleDraft = { name: 'Daily check', goal: 'Check app', profile: 'flash', device_serial: 'device-1', schedule_type: 'daily', time_of_day: '08:30:00', weekdays: [], interval_minutes: null, timezone: 'Asia/Bangkok', enabled: true };
  beforeEach(() => { TestBed.configureTestingModule({ providers: [ScheduleService, provideHttpClient(withXhr()), provideHttpClientTesting()] }); service = TestBed.inject(ScheduleService); http = TestBed.inject(HttpTestingController); });
  afterEach(() => http.verify());
  it('requests backend preview and preserves seconds', () => { let result: string[] = []; service.preview(draft).subscribe(value => result = value); const request = http.expectOne('/api/schedules/preview'); expect(request.request.method).toBe('POST'); expect(request.request.body.time_of_day).toBe('08:30:00'); request.flush({ due_times: ['2026-09-15T01:30:00Z'] }); expect(result.length).toBe(1); });
  it('passes schedule email policy to preview and create unchanged', () => {
    const emailDraft: TaskScheduleDraft = { ...draft, email_enabled: true, recipient_name: 'Ops', recipient_email: 'ops@example.com', email_subject: 'ARTEMIS — Daily check — {status}' };
    service.preview(emailDraft).subscribe(); const preview = http.expectOne('/api/schedules/preview'); expect(preview.request.body.recipient_email).toBe('ops@example.com'); preview.flush({ occurrences: [] });
    service.create(emailDraft).subscribe(); const create = http.expectOne('/api/schedules'); expect(create.request.method).toBe('POST'); expect(create.request.body.email_enabled).toBeTrue(); expect(create.request.body.email_subject).toContain('{status}'); create.flush({ ...emailDraft, id: 's1', version: 1 });
  });
  it('uses optimistic version when pausing', () => { service.setEnabled({ ...draft, id: 'schedule-1', version: 4, enabled: true }, false).subscribe(); const request = http.expectOne('/api/schedules/schedule-1'); expect(request.request.method).toBe('PATCH'); expect(request.request.body).toEqual({ enabled: false, expected_version: 4 }); request.flush({ ...draft, id: 'schedule-1', version: 5, enabled: false }); });
  it('uses notification endpoints without rerunning a task', () => { service.retryEmail('schedule/1', 'run/1').subscribe(); const retry = http.expectOne('/api/schedules/schedule%2F1/runs/run%2F1/email/retry'); expect(retry.request.method).toBe('POST'); expect(retry.request.body).toEqual({}); retry.flush({ run_id: 'run/1', status: 'pending' }); expect(service.emailReportUrl('schedule/1', 'run/1')).toBe('/api/schedules/schedule%2F1/runs/run%2F1/email/report'); });
  it('normalizes connected device response', () => { let serial = ''; service.devices().subscribe(devices => serial = devices[0].serial); const request = http.expectOne('/api/devices'); request.flush({ devices: [{ device_id: 'abc', model: 'Pixel', is_busy: true }] }); expect(serial).toBe('abc'); });
});

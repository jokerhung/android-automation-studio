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
  it('uses optimistic version when pausing', () => { service.setEnabled({ ...draft, id: 'schedule-1', version: 4, enabled: true }, false).subscribe(); const request = http.expectOne('/api/schedules/schedule-1'); expect(request.request.method).toBe('PATCH'); expect(request.request.body).toEqual({ enabled: false, expected_version: 4 }); request.flush({ ...draft, id: 'schedule-1', version: 5, enabled: false }); });
  it('normalizes connected device response', () => { let serial = ''; service.devices().subscribe(devices => serial = devices[0].serial); const request = http.expectOne('/api/devices'); request.flush({ devices: [{ device_id: 'abc', model: 'Pixel', is_busy: true }] }); expect(serial).toBe('abc'); });
});

import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { ScheduleDevice, ScheduleListResponse, SchedulePreviewResponse, ScheduleRun, ScheduleRunListResponse, ScheduleStatus, TaskSchedule, TaskScheduleDraft } from '../core/models/schedule.model';
@Injectable({ providedIn: 'root' })
export class ScheduleService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/schedules';
  list(): Observable<TaskSchedule[]> { return this.http.get<ScheduleListResponse | TaskSchedule[]>(this.baseUrl).pipe(map(value => Array.isArray(value) ? value : value.schedules ?? [])); }
  get(id: string): Observable<TaskSchedule> { return this.http.get<TaskSchedule>(this.baseUrl + '/' + encodeURIComponent(id)); }
  preview(draft: TaskScheduleDraft): Observable<string[]> { return this.http.post<SchedulePreviewResponse | string[]>(this.baseUrl + '/preview', draft).pipe(map(value => Array.isArray(value) ? value : value.due_times ?? value.next_runs ?? value.occurrences ?? [])); }
  create(draft: TaskScheduleDraft): Observable<TaskSchedule> { return this.http.post<TaskSchedule>(this.baseUrl, draft); }
  update(schedule: TaskSchedule, draft: TaskScheduleDraft): Observable<TaskSchedule> { return this.http.patch<TaskSchedule>(this.baseUrl + '/' + encodeURIComponent(schedule.id), { ...draft, expected_version: schedule.version }); }
  setEnabled(schedule: TaskSchedule, enabled: boolean): Observable<TaskSchedule> { return this.http.patch<TaskSchedule>(this.baseUrl + '/' + encodeURIComponent(schedule.id), { enabled, expected_version: schedule.version }); }
  delete(schedule: TaskSchedule): Observable<void> { const params = new HttpParams().set('expected_version', schedule.version); return this.http.delete<void>(this.baseUrl + '/' + encodeURIComponent(schedule.id), { params }); }
  runNow(id: string): Observable<ScheduleRun> { const key = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : 'manual-' + Date.now() + '-' + Math.random(); return this.http.post<{ run: ScheduleRun }>(this.baseUrl + '/' + encodeURIComponent(id) + '/run-now', { idempotency_key: key }).pipe(map(value => value.run)); }
  runs(id: string, limit = 25): Observable<ScheduleRun[]> { return this.http.get<ScheduleRunListResponse | ScheduleRun[]>(this.baseUrl + '/' + encodeURIComponent(id) + '/runs', { params: { limit } }).pipe(map(value => Array.isArray(value) ? value : value.runs ?? [])); }
  retryEmail(scheduleId: string, runId: string): Observable<{ run_id: string; status: string }> { return this.http.post<{ run_id: string; status: string }>(this.baseUrl + '/' + encodeURIComponent(scheduleId) + '/runs/' + encodeURIComponent(runId) + '/email/retry', {}); }
  emailReportUrl(scheduleId: string, runId: string): string { return this.baseUrl + '/' + encodeURIComponent(scheduleId) + '/runs/' + encodeURIComponent(runId) + '/email/report'; }
  status(): Observable<ScheduleStatus> { return this.http.get<ScheduleStatus>(this.baseUrl + '/status').pipe(map(value => ({ ...value, healthy: value.healthy ?? Boolean(value.running && value.last_heartbeat) }))); }
  devices(): Observable<ScheduleDevice[]> { return this.http.get<{ devices: Record<string, unknown>[] }>('/api/devices').pipe(map(response => (response.devices ?? []).map(raw => ({ serial: String(raw['serial'] ?? raw['device_serial'] ?? raw['device_id'] ?? ''), name: String(raw['name'] ?? raw['model'] ?? raw['device_name'] ?? raw['serial'] ?? ''), model: raw['model'] == null ? null : String(raw['model']), status: raw['status'] == null ? null : String(raw['status']), busy: Boolean(raw['busy'] ?? raw['is_busy']), authorized: raw['authorized'] == null ? undefined : Boolean(raw['authorized']) })).filter(device => device.serial))); }
}

import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { EmailActionResponse, EmailSettings, EmailSettingsUpdate } from '../core/models/email-settings.model';

@Injectable({ providedIn: 'root' })
export class EmailSettingsService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/settings/email';

  get(): Observable<EmailSettings> { return this.http.get<EmailSettings>(this.baseUrl); }
  save(settings: EmailSettingsUpdate): Observable<EmailSettings> { return this.http.put<EmailSettings>(this.baseUrl, settings); }
  clearPassword(): Observable<EmailSettings> { return this.http.delete<EmailSettings>(this.baseUrl + '/password'); }
  testConnection(): Observable<EmailActionResponse> { return this.http.post<EmailActionResponse>(this.baseUrl + '/test-connection', {}); }
  sendTest(recipient: string): Observable<EmailActionResponse> { return this.http.post<EmailActionResponse>(this.baseUrl + '/send-test', { recipient_email: recipient }); }
}

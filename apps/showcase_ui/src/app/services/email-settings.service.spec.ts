import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { EmailSettingsService } from './email-settings.service';

describe('EmailSettingsService', () => {
  let service: EmailSettingsService;
  let http: HttpTestingController;
  beforeEach(() => { TestBed.configureTestingModule({ providers: [EmailSettingsService, provideHttpClient(withXhr()), provideHttpClientTesting()] }); service = TestBed.inject(EmailSettingsService); http = TestBed.inject(HttpTestingController); });
  afterEach(() => http.verify());

  it('never reads a password and only sends a newly entered value on save', () => {
    service.get().subscribe(settings => expect(settings.password_configured).toBeTrue());
    http.expectOne('/api/settings/email').flush({ enabled: true, smtp_host: 'smtp.example.com', smtp_port: 587, security: 'starttls', sender_email: 'a@example.com', sender_name: 'ARTEMIS', smtp_username: 'a@example.com', password_configured: true });
    service.save({ enabled: true, smtp_host: 'smtp.example.com', smtp_port: 587, security: 'starttls', sender_email: 'a@example.com', sender_name: 'ARTEMIS', smtp_username: 'a@example.com', password: 'new-app-password' }).subscribe();
    const request = http.expectOne('/api/settings/email'); expect(request.request.method).toBe('PUT'); expect(request.request.body.password).toBe('new-app-password'); expect(request.request.body.test_recipient).toBeUndefined(); request.flush({ password_configured: true });
  });

  it('uses explicit clear, connection-test and send-test endpoints', () => {
    service.clearPassword().subscribe(); http.expectOne('/api/settings/email/password').flush({ password_configured: false });
    service.testConnection().subscribe(); const connection = http.expectOne('/api/settings/email/test-connection'); expect(connection.request.method).toBe('POST'); expect(connection.request.body).toEqual({}); connection.flush({ success: true, message: 'Connected' });
    service.sendTest('test@example.com').subscribe(); const send = http.expectOne('/api/settings/email/send-test'); expect(send.request.body).toEqual({ recipient_email: 'test@example.com' }); send.flush({ success: true, message: 'Accepted' });
  });
});

import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { EmailSettingsService } from '../../services/email-settings.service';
import { EmailSettingsComponent } from './email-settings.component';

describe('EmailSettingsComponent', () => {
  let fixture: ComponentFixture<EmailSettingsComponent>;
  let component: EmailSettingsComponent;
  const api = jasmine.createSpyObj<EmailSettingsService>('EmailSettingsService', ['get', 'save', 'clearPassword', 'testConnection', 'sendTest']);
  beforeEach(async () => {
    api.get.and.returnValue(of({ enabled: true, smtp_host: 'smtp.example.com', smtp_port: 587, security: 'starttls', sender_email: 'sender@example.com', sender_name: 'ARTEMIS', smtp_username: 'sender@example.com', password_configured: true, test_recipient: 'sender@example.com', version: 2 }));
    api.save.and.callFake((draft: any) => of({ ...draft, password_configured: true, version: 3 }));
    api.testConnection.and.returnValue(of({ success: true, message: 'TLS and authentication succeeded.', tested_at: '2026-09-14T08:00:00Z' }));
    api.sendTest.and.returnValue(of({ success: true, message: 'Accepted by SMTP.' }));
    await TestBed.configureTestingModule({ imports: [EmailSettingsComponent], providers: [{ provide: EmailSettingsService, useValue: api }] }).compileComponents();
    fixture = TestBed.createComponent(EmailSettingsComponent); component = fixture.componentInstance; fixture.detectChanges();
    api.testConnection.calls.reset(); api.sendTest.calls.reset();
  });
  it('renders password as write-only and does not populate it', () => { const input = fixture.nativeElement.querySelector('[name="smtpPassword"]'); expect(input.type).toBe('password'); expect(component.draft.password).toBe(''); expect(fixture.nativeElement.textContent).toContain('Password configured'); });
  it('requires saving dirty settings before either test action', () => { component.draft.smtp_host = 'changed.example.com'; component.testConnection(); component.sendTestEmail(); expect(api.testConnection).not.toHaveBeenCalled(); expect(api.sendTest).not.toHaveBeenCalled(); expect(component.connectionMessage()).toContain('Save changes'); expect(component.sendMessage()).toContain('Save changes'); });
  it('uses mocks for connection and test-email requests', () => { component.testConnection(); component.sendTestEmail(); expect(api.testConnection).toHaveBeenCalled(); expect(api.sendTest).toHaveBeenCalledWith('sender@example.com'); expect(component.connectionState()).toBe('success'); expect(component.sendState()).toBe('success'); });
});

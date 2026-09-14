export type EmailSecurity = 'starttls' | 'ssl';
export type InlineActionState = 'idle' | 'pending' | 'success' | 'error';

export interface EmailSettings {
  enabled: boolean;
  smtp_host: string;
  smtp_port: number;
  security: EmailSecurity;
  sender_email: string;
  sender_name?: string | null;
  smtp_username: string;
  password_configured: boolean;
  test_recipient?: string | null;
  version?: number;
  last_tested_at?: string | null;
  last_test_success?: boolean | null;
  last_test_error?: string | null;
}

export interface EmailSettingsDraft {
  enabled: boolean;
  smtp_host: string;
  smtp_port: number;
  security: EmailSecurity;
  sender_email: string;
  sender_name: string;
  smtp_username: string;
  password?: string;
  test_recipient: string;
  expected_version?: number;
}

export type EmailSettingsUpdate = Omit<EmailSettingsDraft, 'test_recipient'>;

export interface EmailActionResponse {
  success: boolean;
  message: string;
  tested_at?: string | null;
}

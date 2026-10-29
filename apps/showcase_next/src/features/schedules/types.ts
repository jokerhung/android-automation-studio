export type ScheduleType = 'interval' | 'daily' | 'weekly';
export type ScheduleProfile = 'flash' | 'pro';
export type IsoWeekday = 1 | 2 | 3 | 4 | 5 | 6 | 7;
/** Backend wall-clock format. Seconds are intentionally retained. */
export type TimeOfDay = `${number}${number}:${number}${number}:${number}${number}`;

export interface IntervalRule {
  schedule_type: 'interval';
  interval_minutes: number;
  time_of_day?: null;
  weekdays?: readonly [];
  timezone: string;
}
export interface DailyRule {
  schedule_type: 'daily';
  interval_minutes?: null;
  time_of_day: TimeOfDay;
  weekdays?: readonly [];
  timezone: string;
}
export interface WeeklyRule {
  schedule_type: 'weekly';
  interval_minutes?: null;
  time_of_day: TimeOfDay;
  weekdays: readonly IsoWeekday[];
  timezone: string;
}
export type ScheduleRule = IntervalRule | DailyRule | WeeklyRule;

export interface ScheduleTask {
  name: string;
  goal: string;
  profile: ScheduleProfile;
  device_serial: string;
  expected_output?: string | null;
  enable_outputter?: boolean | null;
  verification_level?: string | null;
  explorer_mode?: string | null;
  locked_app_package?: string | null;
  app_path?: string | null;
}
export interface ScheduleEmailPolicy {
  email_enabled?: boolean;
  recipient_name?: string | null;
  recipient_email?: string | null;
  email_subject?: string | null;
}
export type ScheduleDraft = ScheduleRule & ScheduleTask & ScheduleEmailPolicy & { enabled: boolean };
export type ScheduleRunStatus = 'scheduled' | 'claimed' | 'queued' | 'running' | 'paused' | 'completed' | 'failed' | 'blocked' | 'expired' | 'skipped_misfire' | 'skipped_overlap' | (string & {});
export type EmailNotificationStatus = 'pending' | 'retry' | 'sending' | 'accepted_by_smtp' | 'failed' | 'delivery_unknown' | 'suppressed' | 'report_incomplete' | 'attachment_too_large' | (string & {});
export interface ScheduleEmailNotification { id?: string; status: EmailNotificationStatus; attempted_at?: string | null; accepted_at?: string | null; updated_at?: string | null; safe_error_code?: string | null; safe_error_message?: string | null; can_retry?: boolean; report_available?: boolean; attempt_count?: number }
export interface ScheduleRun { id: string; schedule_id: string; schedule_version?: number; due_at: string; trigger: 'scheduled' | 'manual' | (string & {}); status: ScheduleRunStatus; session_id?: string | null; queued_at?: string | null; started_at?: string | null; finished_at?: string | null; safe_error_message?: string | null; error_message?: string | null; lateness_ms?: number | null; email_notification?: ScheduleEmailNotification | null; notification?: ScheduleEmailNotification | null; email_status?: EmailNotificationStatus | null }
export type TaskSchedule = ScheduleDraft & { id: string; version: number; next_run_at?: string | null; last_run?: ScheduleRun | null; last_run_at?: string | null; last_run_status?: ScheduleRunStatus | null; created_at?: string; updated_at?: string };
export type ScheduleUpdate = Partial<ScheduleDraft>;
export type SchedulePreviewRequest = ScheduleRule & { anchor_at?: string | null; count?: number };
export interface SchedulePreviewResponse { due_times?: string[]; next_runs?: string[]; occurrences?: string[]; timezone?: string }
export interface ScheduleRunList { runs: ScheduleRun[]; total?: number; limit?: number; offset?: number; next_cursor?: string | null }
export interface ScheduleDevice { serial: string; name?: string | null; model?: string | null; status?: string | null; busy?: boolean; authorized?: boolean }
export interface ScheduleStatus { healthy: boolean; running?: boolean; leader?: boolean; status?: string; last_heartbeat?: string | null; timezone_support?: boolean; message?: string | null }
export interface EmailRetryResult { run_id: string; status: EmailNotificationStatus }

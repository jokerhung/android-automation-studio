export type ScheduleType = 'interval' | 'daily' | 'weekly';
export type ScheduleProfile = 'flash' | 'pro';
export type ScheduleRunStatus = 'scheduled' | 'claimed' | 'queued' | 'running' | 'paused' | 'completed' | 'failed' | 'blocked' | 'expired' | 'skipped_misfire' | 'skipped_overlap' | string;
export interface ScheduleRule { schedule_type: ScheduleType; interval_minutes?: number | null; time_of_day?: string | null; weekdays?: number[]; timezone: string; }
export interface ScheduleTaskOptions { expected_output?: string | null; enable_outputter?: boolean | null; verification_level?: string | null; explorer_mode?: string | null; }
export interface ScheduleEmailPolicy { email_enabled?: boolean; recipient_name?: string | null; recipient_email?: string | null; email_subject?: string | null; }
export type EmailNotificationStatus = 'pending' | 'sending' | 'accepted_by_smtp' | 'failed' | 'delivery_unknown' | 'suppressed' | 'report_incomplete' | 'attachment_too_large' | string;
export interface ScheduleEmailNotification { id?: string; status: EmailNotificationStatus; attempted_at?: string | null; accepted_at?: string | null; updated_at?: string | null; safe_error_code?: string | null; safe_error_message?: string | null; can_retry?: boolean; report_available?: boolean; attempt_count?: number; }
export interface TaskSchedule extends ScheduleRule, ScheduleTaskOptions, ScheduleEmailPolicy { id: string; name: string; goal: string; profile: ScheduleProfile; device_serial: string; device_name?: string | null; enabled: boolean; version: number; next_run_at?: string | null; last_run?: ScheduleRun | null; last_run_at?: string | null; last_run_status?: ScheduleRunStatus | null; created_at?: string; updated_at?: string; }
export interface TaskScheduleDraft extends ScheduleRule, ScheduleTaskOptions, ScheduleEmailPolicy { name: string; goal: string; profile: ScheduleProfile; device_serial: string; enabled: boolean; }
export interface ScheduleRun { id: string; schedule_id: string; due_at: string; trigger: 'scheduled' | 'manual' | string; status: ScheduleRunStatus; session_id?: string | null; queued_at?: string | null; started_at?: string | null; finished_at?: string | null; safe_error_message?: string | null; error_message?: string | null; lateness_ms?: number | null; email_notification?: ScheduleEmailNotification | null; notification?: ScheduleEmailNotification | null; email_status?: EmailNotificationStatus | null; }
export interface SchedulePreviewResponse { due_times?: string[]; next_runs?: string[]; occurrences?: string[]; timezone?: string; }
export interface ScheduleStatus { healthy?: boolean; running?: boolean; leader?: boolean; status?: string; last_heartbeat?: string | null; timezone_support?: boolean; message?: string | null; }
export interface ScheduleDevice { serial: string; name?: string | null; model?: string | null; status?: string | null; busy?: boolean; authorized?: boolean; }
export interface ScheduleListResponse { schedules: TaskSchedule[]; }
export interface ScheduleRunListResponse { runs: ScheduleRun[]; total?: number; next_cursor?: string | null; }

export type ScheduleType = 'interval' | 'daily' | 'weekly';
export type ScheduleProfile = 'flash' | 'pro';
export type ScheduleRunStatus = 'scheduled' | 'claimed' | 'queued' | 'running' | 'paused' | 'completed' | 'failed' | 'blocked' | 'expired' | 'skipped_misfire' | 'skipped_overlap' | string;
export interface ScheduleRule { schedule_type: ScheduleType; interval_minutes?: number | null; time_of_day?: string | null; weekdays?: number[]; timezone: string; }
export interface ScheduleTaskOptions { expected_output?: string | null; enable_outputter?: boolean | null; verification_level?: string | null; explorer_mode?: string | null; }
export interface TaskSchedule extends ScheduleRule, ScheduleTaskOptions { id: string; name: string; goal: string; profile: ScheduleProfile; device_serial: string; device_name?: string | null; enabled: boolean; version: number; next_run_at?: string | null; last_run?: ScheduleRun | null; last_run_at?: string | null; last_run_status?: ScheduleRunStatus | null; created_at?: string; updated_at?: string; }
export interface TaskScheduleDraft extends ScheduleRule, ScheduleTaskOptions { name: string; goal: string; profile: ScheduleProfile; device_serial: string; enabled: boolean; }
export interface ScheduleRun { id: string; schedule_id: string; due_at: string; trigger: 'scheduled' | 'manual' | string; status: ScheduleRunStatus; session_id?: string | null; queued_at?: string | null; started_at?: string | null; finished_at?: string | null; safe_error_message?: string | null; error_message?: string | null; lateness_ms?: number | null; }
export interface SchedulePreviewResponse { due_times?: string[]; next_runs?: string[]; occurrences?: string[]; timezone?: string; }
export interface ScheduleStatus { healthy?: boolean; running?: boolean; leader?: boolean; status?: string; last_heartbeat?: string | null; timezone_support?: boolean; message?: string | null; }
export interface ScheduleDevice { serial: string; name?: string | null; model?: string | null; status?: string | null; busy?: boolean; authorized?: boolean; }
export interface ScheduleListResponse { schedules: TaskSchedule[]; }
export interface ScheduleRunListResponse { runs: ScheduleRun[]; total?: number; next_cursor?: string | null; }

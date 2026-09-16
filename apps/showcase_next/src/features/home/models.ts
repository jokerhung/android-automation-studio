export type ExecutionProfile = 'flash' | 'pro';
export type VerificationLevelId = 'off' | 'final' | 'checkpoints' | 'strict';
export type ExplorerModeId = 'flash' | 'pro' | 'ultra';

export interface ProbeResult { id: string; status: 'pass'|'warn'|'fail'|'skipped'; is_blocker: boolean; summary: string }
export interface DeviceInfo { serial: string; state: string; model: string|null; is_locked: boolean|null; installed_packages?: string[] }
export interface SystemReadinessReport { overall_ready: boolean; blocker_count: number; passed_blocker_count: number; probes: ProbeResult[]; active_device: DeviceInfo|null; timestamp: number }
export interface ProTuningDefaults { verification_level?: string|null; explorer_mode?: string|null }
export interface RunTaskRequest { goal: string; profile: ExecutionProfile; expected_output?: string; enable_outputter?: boolean; verification_level?: VerificationLevelId; explorer_mode?: ExplorerModeId }
export interface RunTaskResponse { tasks?: Array<{ session_id?: string }> }
export interface TuningLevel<T extends string> { id:T; label:string; tagline:string; latency:string; runs:readonly string[]; skips?:readonly string[]; bestFor:string }

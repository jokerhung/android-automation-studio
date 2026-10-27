import { apiRequest, READINESS_REQUEST_TIMEOUT_MS } from '@/lib/api/client';

export type ModelProvider = 'openai'|'google'|'anthropic'|'openrouter'|'xai'|'custom'|'ollama'|'vllm';
export interface ModelSettings { provider: ModelProvider; default_model: string; fallback_model: string; fallback_provider: string; base_url: string; fallback_url: string; version: string; keys_configured: Record<string,boolean>; config_path?: string; env_path?: string; node_overrides: string[] }
export interface ModelSettingsUpdate { provider: ModelProvider; default_model: string; fallback_model: string; base_url: string; fallback_url: string; api_key: string|null; expected_version: string; confirm_restart: true }
export interface RestartResponse { status: 'restarting'|'saved_restart_failed'|string; previous_pid?: number; message?: string }
export interface ServerStatus { current_pid?: number }
export interface StartupStatus { supported: boolean; enabled: boolean; port: number|null }
export type EmailSecurity = 'starttls'|'ssl';
export interface EmailSettings { enabled:boolean; smtp_host:string; smtp_port:number; security:EmailSecurity; sender_email:string; sender_name?:string|null; smtp_username:string; password_configured:boolean; test_recipient?:string|null; version?:number; last_tested_at?:string|null; last_test_success?:boolean|null; last_test_error?:string|null }
export interface EmailSettingsUpdate { enabled:boolean; smtp_host:string; smtp_port:number; security:EmailSecurity; sender_email:string; sender_name:string; smtp_username:string; password?:string; expected_version?:number }
export interface EmailActionResponse { success:boolean; message:string; tested_at?:string|null }
export type ProbeStatus='pass'|'warn'|'fail'|'skipped';
export interface ProbeAction { action_type:'command'|'hint'|'link'; label:string; payload:string }
export interface DeviceInfo { serial:string; state:string; model:string|null; product:string|null; android_version:string|null; screen_resolution:string|null; is_locked:boolean|null; is_emulator:boolean }
export interface ProbeResult { id:string; category:'device'|'auth'|'toolchain'|'runtime'; title:string; status:ProbeStatus; is_blocker:boolean; summary:string; description:string; metadata:Record<string,unknown>; actions:ProbeAction[] }
export interface ReadinessReport { overall_ready:boolean; blocker_count:number; passed_blocker_count:number; probes:ProbeResult[]; active_device:DeviceInfo|null; os_type?:string; timestamp:number }
export interface AdbEndpoint { host:string; port:number; socket:string; identity?:string; mode:'local'|'remote'; is_local_default:boolean }
export interface AdbDevice { serial:string; state:string; model:string|null; product:string|null }
export interface AdbConnectionResult { success:boolean; message:string; endpoint:AdbEndpoint; devices:AdbDevice[]; persisted?:boolean; persistence_error?:string|null }
export interface AdbConnectionResponse { connection_result:AdbConnectionResult; report?:ReadinessReport }
export interface EmulatorState { avd_name:string|null; status:'idle'|'starting'|'waiting_for_adb'|'booting'|'ready'|'failed'|'stopped'; pid:number|null; serial:string|null; stage_message:string; progress_percent:number; started_at:number|null; elapsed_seconds:number; error:string|null; logs:string[]; can_retry:boolean }

export const settingsApi={
 model:(signal?:AbortSignal)=>apiRequest<ModelSettings>('/api/settings/model',signal?{signal}:{}),
 saveModel:(body:ModelSettingsUpdate,signal?:AbortSignal)=>apiRequest<RestartResponse,ModelSettingsUpdate>('/api/settings/model',{method:'PUT',body,...(signal?{signal}:{})}),
 serverStatus:(signal?:AbortSignal)=>apiRequest<ServerStatus>('/api/system/server-status',signal?{signal}:{}),
 startup:(signal?:AbortSignal)=>apiRequest<StartupStatus>('/api/system/windows-startup',signal?{signal}:{}),
 setStartup:(enabled:boolean,signal?:AbortSignal)=>apiRequest<StartupStatus,{enabled:boolean}>('/api/system/windows-startup',{method:'PUT',body:{enabled},...(signal?{signal}:{})}),
 email:(signal?:AbortSignal)=>apiRequest<EmailSettings>('/api/settings/email',signal?{signal}:{}),
 saveEmail:(body:EmailSettingsUpdate,signal?:AbortSignal)=>apiRequest<EmailSettings,EmailSettingsUpdate>('/api/settings/email',{method:'PUT',body,...(signal?{signal}:{})}),
 clearEmailPassword:(signal?:AbortSignal)=>apiRequest<EmailSettings>('/api/settings/email/password',{method:'DELETE',...(signal?{signal}:{})}),
 testEmail:(signal?:AbortSignal)=>apiRequest<EmailActionResponse,Record<string,never>>('/api/settings/email/test-connection',{method:'POST',body:{},...(signal?{signal}:{})}),
 sendTestEmail:(recipient_email:string,signal?:AbortSignal)=>apiRequest<EmailActionResponse,{recipient_email:string}>('/api/settings/email/send-test',{method:'POST',body:{recipient_email},...(signal?{signal}:{})}),
 readiness:(force=false,signal?:AbortSignal)=>apiRequest<ReadinessReport>('/api/system/readiness',{timeoutMs:READINESS_REQUEST_TIMEOUT_MS,...(force?{query:{force:true}}:{}),...(signal?{signal}:{})}),
 adbStatus:(signal?:AbortSignal)=>apiRequest<{endpoint:AdbEndpoint}>('/api/system/adb/server',signal?{signal}:{}),
 probeAdb:(host:string,port:number,signal?:AbortSignal)=>apiRequest<AdbConnectionResponse,{host:string;port:number;persist:false}>('/api/system/adb/server/probe',{method:'POST',body:{host,port,persist:false},...(signal?{signal}:{})}),
 connectAdb:(host:string,port:number,signal?:AbortSignal)=>apiRequest<AdbConnectionResponse,{host:string;port:number;persist:true}>('/api/system/adb/server/connect',{method:'POST',body:{host,port,persist:true},...(signal?{signal}:{})}),
 useLocalAdb:(signal?:AbortSignal)=>apiRequest<AdbConnectionResponse,Record<string,never>>('/api/system/adb/server/local',{method:'POST',query:{persist:true},body:{},...(signal?{signal}:{})}),
 restartAdb:(signal?:AbortSignal)=>apiRequest<{report?:ReadinessReport},Record<string,never>>('/api/system/adb/restart',{method:'POST',body:{},...(signal?{signal}:{})}),
 connectDevice:(host:string,port:number,signal?:AbortSignal)=>apiRequest<{report?:ReadinessReport},{host:string;port:number}>('/api/system/adb/connect',{method:'POST',body:{host,port},...(signal?{signal}:{})}),
 selectDevice:(serial:string,signal?:AbortSignal)=>apiRequest<{report?:ReadinessReport},{serial:string}>('/api/system/devices/select',{method:'POST',body:{serial},...(signal?{signal}:{})}),
 emulatorStatus:(signal?:AbortSignal)=>apiRequest<EmulatorState>('/api/system/emulator/status',signal?{signal}:{}),
 launchEmulator:(avd_name:string,signal?:AbortSignal)=>apiRequest<EmulatorState,{avd_name:string}>('/api/system/emulator/launch',{method:'POST',body:{avd_name},...(signal?{signal}:{})}),
 stopEmulator:(signal?:AbortSignal)=>apiRequest<unknown,Record<string,never>>('/api/system/emulator/stop',{method:'POST',body:{},...(signal?{signal}:{})}),
 dismissEmulator:(signal?:AbortSignal)=>apiRequest<unknown,Record<string,never>>('/api/system/emulator/dismiss',{method:'POST',body:{},...(signal?{signal}:{})}),
};

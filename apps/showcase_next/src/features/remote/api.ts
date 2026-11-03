import { apiRequest } from '@/lib/api/client';
import type { DeviceInfo, RemoteState } from './types';
export const remoteApi = {
 devices: (signal?:AbortSignal) => apiRequest<{devices:DeviceInfo[]}>('/api/remote/devices', signal ? {signal} : {}),
 state: (serial:string, signal?:AbortSignal) => apiRequest<RemoteState>('/api/remote/state',{query:{device_serial:serial},...(signal ? {signal}:{})}),
 tap: (body:Record<string,unknown>, signal?:AbortSignal) => apiRequest<{ok:boolean;sequence:number},Record<string,unknown>>('/api/remote/input/tap',{method:'POST',body,...(signal?{signal}:{})}),
 swipe: (body:Record<string,unknown>, signal?:AbortSignal) => apiRequest<{ok:boolean;sequence:number},Record<string,unknown>>('/api/remote/input/swipe',{method:'POST',body,...(signal?{signal}:{})}),
 text: (body:Record<string,unknown>, signal?:AbortSignal) => apiRequest<{ok:boolean;mode:'ascii'|'ime'},Record<string,unknown>>('/api/remote/input/text',{method:'POST',body,...(signal?{signal}:{})}),
 key: (body:Record<string,unknown>, signal?:AbortSignal) => apiRequest<{ok:boolean},Record<string,unknown>>('/api/remote/input/key',{method:'POST',body,...(signal?{signal}:{})}),
};

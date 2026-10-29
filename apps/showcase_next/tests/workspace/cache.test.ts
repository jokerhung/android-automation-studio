import { describe,expect,it } from 'vitest';
import { MAX_CACHED_SESSIONS,parseSessionsCache,serializeSessionsCache } from '@/features/workspace/cache';

describe('sessions cache',()=>{
 it('validates version, shape, ids, and normalizes statuses',()=>{
  expect(parseSessionsCache(null)).toBeNull(); expect(parseSessionsCache('{bad')).toBeNull();
  expect(parseSessionsCache(JSON.stringify({version:2,cachedAt:1,sessions:[]}))).toBeNull();
  expect(parseSessionsCache(JSON.stringify({version:1,cachedAt:1,sessions:[{status:'running'}]}))).toBeNull();
  expect(parseSessionsCache(JSON.stringify({version:1,cachedAt:1,sessions:[{id:'a',status:'NEW_VALUE'}]}))?.sessions[0]).toMatchObject({session_id:'a',status:'unknown'});
 });
 it('round trips and bounds cached history',()=>{
  const sessions=Array.from({length:MAX_CACHED_SESSIONS+3},(_,index)=>({session_id:String(index),status:'completed' as const}));
  const parsed=parseSessionsCache(serializeSessionsCache(sessions,42));
  expect(parsed?.cachedAt).toBe(42); expect(parsed?.sessions).toHaveLength(MAX_CACHED_SESSIONS); expect(parsed?.sessions[0]?.session_id).toBe('0');
 });
});

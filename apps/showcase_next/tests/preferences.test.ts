import { describe,expect,it } from 'vitest';
import { DEFAULT_UI_PREFERENCES,parseUiPreferences,validateUiPreferences } from '@/lib/preferences/preferences';

describe('UI preference compatibility',()=>{
  it.each([['en','light'],['en','dark'],['vi','light'],['vi','dark']] as const)('accepts exact v1 %s/%s schema',(language,theme)=>expect(validateUiPreferences({version:1,language,theme,extra:true})).toEqual({version:1,language,theme}));
  it.each([null,true,1,'value',[],{}, {version:2,language:'vi',theme:'dark'}, {version:'1',language:'vi',theme:'dark'}])('uses full defaults for incompatible value %#',(value)=>expect(validateUiPreferences(value)).toEqual(DEFAULT_UI_PREFERENCES));
  it('falls back v1 fields independently',()=>{expect(validateUiPreferences({version:1,language:'fr',theme:'dark'})).toEqual({version:1,language:'en',theme:'dark'});expect(validateUiPreferences({version:1,language:'vi',theme:'auto'})).toEqual({version:1,language:'vi',theme:'light'});});
  it('survives missing and malformed storage with fresh defaults',()=>{expect(parseUiPreferences(null)).toEqual(DEFAULT_UI_PREFERENCES);expect(parseUiPreferences('{')).toEqual(DEFAULT_UI_PREFERENCES);expect(parseUiPreferences(null)).not.toBe(DEFAULT_UI_PREFERENCES);});
});

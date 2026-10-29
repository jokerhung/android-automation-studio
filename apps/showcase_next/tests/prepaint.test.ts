import { beforeEach,describe,expect,it } from 'vitest';
import { UI_PREFERENCES_BOOTSTRAP,UI_PREFERENCES_STORAGE_KEY } from '@/lib/preferences/preferences';

describe('prepaint preference bootstrap',()=>{
 beforeEach(()=>{localStorage.clear();document.documentElement.lang='en';document.documentElement.dataset.theme='light';});
 it.each([['en','light'],['en','dark'],['vi','light'],['vi','dark']] as const)('applies %s/%s before hydration',(language,theme)=>{localStorage.setItem(UI_PREFERENCES_STORAGE_KEY,JSON.stringify({version:1,language,theme}));Function(UI_PREFERENCES_BOOTSTRAP)();expect(document.documentElement.lang).toBe(language);expect(document.documentElement.dataset.theme).toBe(theme);});
 it('swallows malformed and ignores wrong-version values',()=>{localStorage.setItem(UI_PREFERENCES_STORAGE_KEY,'{');expect(()=>Function(UI_PREFERENCES_BOOTSTRAP)()).not.toThrow();localStorage.setItem(UI_PREFERENCES_STORAGE_KEY,JSON.stringify({version:2,language:'vi',theme:'dark'}));Function(UI_PREFERENCES_BOOTSTRAP)();expect(document.documentElement.lang).toBe('en');expect(document.documentElement.dataset.theme).toBe('light');});
});

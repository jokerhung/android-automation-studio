import { act,render,screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach,describe,expect,it,vi } from 'vitest';
import { PreferencesPanel } from '@/components/preferences-panel';
import { AppProviders,useAppPreferences } from '@/app/providers';
import { UI_PREFERENCES_STORAGE_KEY } from '@/lib/preferences/preferences';

function Probe(){const {preferences,setLanguage,setTheme,t}=useAppPreferences();return <><output>{preferences.language}:{preferences.theme}:{t('nav.home')}</output><button onClick={()=>setLanguage(preferences.language==='en'?'vi':'en')}>language</button><button onClick={()=>setTheme(preferences.theme==='light'?'dark':'light')}>theme</button></>}

describe('AppProviders',()=>{
 beforeEach(()=>{localStorage.clear();document.documentElement.lang='en';document.documentElement.dataset.theme='light';vi.restoreAllMocks();});
 it.each([['en','light','Home'],['en','dark','Home'],['vi','light','Trang chủ'],['vi','dark','Trang chủ']] as const)('hydrates %s/%s without rewriting storage',async(language,theme,label)=>{const stored=JSON.stringify({version:1,language,theme});localStorage.setItem(UI_PREFERENCES_STORAGE_KEY,stored);const write=vi.spyOn(Storage.prototype,'setItem');render(<AppProviders><Probe/></AppProviders>);expect(await screen.findByText(language+':'+theme+':'+label)).toBeInTheDocument();expect(document.documentElement).toHaveAttribute('lang',language);expect(document.documentElement).toHaveAttribute('data-theme',theme);expect(localStorage.getItem(UI_PREFERENCES_STORAGE_KEY)).toBe(stored);expect(write).not.toHaveBeenCalled();});
 it('updates language, theme and compatible storage',async()=>{render(<AppProviders><Probe/></AppProviders>);const user=userEvent.setup();await user.click(screen.getByText('language'));await user.click(screen.getByText('theme'));expect(screen.getByText('vi:dark:Trang chủ')).toBeInTheDocument();expect(JSON.parse(localStorage.getItem(UI_PREFERENCES_STORAGE_KEY)??'{}')).toEqual({version:1,language:'vi',theme:'dark'});});
 it('merges updates with the latest storage value',async()=>{localStorage.setItem(UI_PREFERENCES_STORAGE_KEY,JSON.stringify({version:1,language:'vi',theme:'light'}));render(<AppProviders><Probe/></AppProviders>);await userEvent.click(screen.getByText('theme'));expect(JSON.parse(localStorage.getItem(UI_PREFERENCES_STORAGE_KEY)!)).toEqual({version:1,language:'vi',theme:'dark'});});
 it('keeps prior in-memory changes when storage is readable but unwritable',async()=>{vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new DOMException('blocked')});render(<AppProviders><Probe/></AppProviders>);const user=userEvent.setup();await user.click(screen.getByText('theme'));await user.click(screen.getByText('language'));expect(screen.getByText('vi:dark:Trang chủ')).toBeInTheDocument();expect(localStorage.getItem(UI_PREFERENCES_STORAGE_KEY)).toBeNull();});
 it('syncs cross-tab values, ignores unrelated keys, and never writes back',async()=>{render(<AppProviders><Probe/></AppProviders>);const write=vi.spyOn(Storage.prototype,'setItem');act(()=>window.dispatchEvent(new StorageEvent('storage',{key:'other',newValue:'x'})));expect(screen.getByText('en:light:Home')).toBeInTheDocument();act(()=>window.dispatchEvent(new StorageEvent('storage',{key:UI_PREFERENCES_STORAGE_KEY,newValue:JSON.stringify({version:1,language:'vi',theme:'dark'})})));expect(await screen.findByText('vi:dark:Trang chủ')).toBeInTheDocument();expect(write).not.toHaveBeenCalled();});
 it.each([
  ['malformed JSON','{'],
  ['JSON null','null'],
  ['primitive','true'],
  ['array','[]'],
  ['missing version',JSON.stringify({language:'vi',theme:'dark'})],
  ['future version',JSON.stringify({version:2,language:'vi',theme:'dark'})],
  ['invalid fields',JSON.stringify({version:1,language:'fr',theme:'auto'})],
 ] as const)('safely defaults an invalid synthetic cross-tab payload: %s',async(_label,newValue)=>{
  render(<AppProviders><Probe/></AppProviders>);
  const write=vi.spyOn(Storage.prototype,'setItem');
  act(()=>window.dispatchEvent(new StorageEvent('storage',{key:UI_PREFERENCES_STORAGE_KEY,newValue})));
  expect(await screen.findByText('en:light:Home')).toBeInTheDocument();
  expect(document.documentElement).toHaveAttribute('lang','en');
  expect(document.documentElement).toHaveAttribute('data-theme','light');
  expect(write).not.toHaveBeenCalled();
 });
 it('removes its storage listener on unmount and installs one listener after remount',async()=>{
  const add=vi.spyOn(window,'addEventListener'); const remove=vi.spyOn(window,'removeEventListener');
  const first=render(<AppProviders><Probe/></AppProviders>);
  await screen.findByText('en:light:Home');
  const firstListener=add.mock.calls.find(([type])=>type==='storage')?.[1];
  expect(firstListener).toBeTypeOf('function');
  first.unmount();
  expect(remove).toHaveBeenCalledWith('storage',firstListener);
  const second=render(<AppProviders><Probe/></AppProviders>);
  await screen.findByText('en:light:Home');
  const storageAdds=add.mock.calls.filter(([type])=>type==='storage');
  expect(storageAdds).toHaveLength(2);
  expect(storageAdds[1]?.[1]).not.toBe(firstListener);
  act(()=>window.dispatchEvent(new StorageEvent('storage',{key:UI_PREFERENCES_STORAGE_KEY,newValue:JSON.stringify({version:1,language:'vi',theme:'dark'})})));
  expect(await screen.findByText('vi:dark:Trang chủ')).toBeInTheDocument();
  second.unmount();
  expect(remove.mock.calls.filter(([type])=>type==='storage')).toHaveLength(2);
 });
 it('exposes named, stateful preference controls to assistive technology',async()=>{
  render(<AppProviders><PreferencesPanel/></AppProviders>);
  const language=screen.getByRole('combobox',{name:'Language'});
  expect(language).toHaveValue('en');
  const theme=screen.getByRole('group',{name:'Theme'});
  const light=screen.getByRole('button',{name:'Light'}); const dark=screen.getByRole('button',{name:'Dark'});
  expect(theme).toContainElement(light); expect(theme).toContainElement(dark);
  expect(light).toHaveAttribute('aria-pressed','true'); expect(dark).toHaveAttribute('aria-pressed','false');
  await userEvent.click(dark);
  expect(light).toHaveAttribute('aria-pressed','false'); expect(dark).toHaveAttribute('aria-pressed','true');
 });
 it('resets defaults when another tab removes the key without writing back',async()=>{localStorage.setItem(UI_PREFERENCES_STORAGE_KEY,JSON.stringify({version:1,language:'vi',theme:'dark'}));render(<AppProviders><Probe/></AppProviders>);expect(await screen.findByText('vi:dark:Trang chủ')).toBeInTheDocument();localStorage.removeItem(UI_PREFERENCES_STORAGE_KEY);act(()=>window.dispatchEvent(new StorageEvent('storage',{key:UI_PREFERENCES_STORAGE_KEY,newValue:null})));expect(await screen.findByText('en:light:Home')).toBeInTheDocument();expect(localStorage.getItem(UI_PREFERENCES_STORAGE_KEY)).toBeNull();});
});

import { act,render,screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach,describe,expect,it,vi } from 'vitest';
import { AppProviders,useAppPreferences } from '@/app/providers';
import { ModelSettingsPanel } from '@/features/settings/general-model-panels';
import { EmailSettingsPanel } from '@/features/settings/email-panel';
import { UI_PREFERENCES_STORAGE_KEY } from '@/lib/preferences/preferences';

function Controls(){const {setLanguage,setTheme}=useAppPreferences();return <><button onClick={()=>setLanguage('vi')}>vi</button><button onClick={()=>setTheme('dark')}>dark</button></>}
const json=(body:unknown)=>Promise.resolve(new Response(JSON.stringify(body),{status:200,headers:{'Content-Type':'application/json'}}));
afterEach(()=>{vi.restoreAllMocks();localStorage.clear();});
describe('dirty drafts and UI preferences',()=>{
 it('does not reset an unsaved Email draft across local and cross-tab preference changes',async()=>{
  vi.spyOn(globalThis,'fetch').mockImplementation(()=>json({enabled:true,smtp_host:'smtp.example.com',smtp_port:587,security:'starttls',sender_email:'a@example.com',sender_name:'ARTEMIS',smtp_username:'a@example.com',password_configured:true,test_recipient:'test@example.com',version:2}));
  render(<AppProviders><Controls/><EmailSettingsPanel/></AppProviders>); const host=await screen.findByLabelText('SMTP host'); const password=screen.getByLabelText('Password'); const user=userEvent.setup();
  await user.clear(host); await user.type(host,'dirty.smtp.example'); await user.type(password,'dirty-secret');
  await user.click(screen.getByText('vi')); await user.click(screen.getByText('dark')); expect(host).toHaveValue('dirty.smtp.example'); expect(password).toHaveValue('dirty-secret');
  act(()=>window.dispatchEvent(new StorageEvent('storage',{key:UI_PREFERENCES_STORAGE_KEY,newValue:JSON.stringify({version:1,language:'en',theme:'light'})})));
  expect(host).toHaveValue('dirty.smtp.example'); expect(password).toHaveValue('dirty-secret');
 });
 it('does not reset an unsaved model or secret across local and cross-tab preference changes',async()=>{vi.spyOn(globalThis,'fetch').mockImplementation(()=>json({provider:'openai',default_model:'primary',fallback_model:'backup',fallback_provider:'openai',base_url:'',fallback_url:'',version:'v1',keys_configured:{openai:true},node_overrides:[]}));render(<AppProviders><Controls/><ModelSettingsPanel/></AppProviders>);const model=await screen.findByLabelText('Default model');const secret=screen.getByLabelText(/API key/);const user=userEvent.setup();await user.clear(model);await user.type(model,'unsaved-model');await user.type(secret,'unsaved-secret');await user.click(screen.getByText('vi'));await user.click(screen.getByText('dark'));expect(model).toHaveValue('unsaved-model');expect(secret).toHaveValue('unsaved-secret');act(()=>window.dispatchEvent(new StorageEvent('storage',{key:UI_PREFERENCES_STORAGE_KEY,newValue:JSON.stringify({version:1,language:'en',theme:'light'})})));expect(model).toHaveValue('unsaved-model');expect(secret).toHaveValue('unsaved-secret');expect(globalThis.fetch).toHaveBeenCalledTimes(3);});
});

import { act,render,screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach,describe,expect,it,vi } from 'vitest';
import { AppProviders,useAppPreferences } from '@/app/providers';
import { UI_PREFERENCES_STORAGE_KEY } from '@/lib/preferences/preferences';
import type { TaskSchedule } from '@/features/schedules/types';

const api=vi.hoisted(()=>({list:vi.fn(),devices:vi.fn(),status:vi.fn(),runs:vi.fn()}));
const emailApi=vi.hoisted(()=>({email:vi.fn()}));
vi.mock('@/features/schedules/api',()=>({schedulesApi:{...api,emailReportUrl:vi.fn()}}));
vi.mock('@/features/settings/api',()=>({settingsApi:emailApi}));
vi.mock('@/components/page-shell',()=>({PageShell:({children}:{children:React.ReactNode})=><main>{children}</main>}));
vi.mock('next/link',()=>({default:({children,href}:{children:React.ReactNode;href:string})=><a href={href}>{children}</a>}));
import { TaskSchedulePage } from '@/features/schedules/task-schedule-page';

const schedule:TaskSchedule={id:'schedule-1',version:4,name:'Daily check',goal:'Check app',profile:'flash',device_serial:'device-1',enabled:true,schedule_type:'interval',interval_minutes:15,time_of_day:null,weekdays:[],timezone:'UTC',email_enabled:false};
function Controls(){const {setLanguage,setTheme}=useAppPreferences();return <><button onClick={()=>setLanguage('vi')}>local-language</button><button onClick={()=>setTheme('dark')}>local-theme</button></>}

beforeEach(()=>{vi.clearAllMocks();localStorage.clear();api.list.mockResolvedValue([schedule]);api.devices.mockResolvedValue([{serial:'device-1',name:'Pixel'}]);api.status.mockResolvedValue({healthy:true});api.runs.mockResolvedValue({runs:[]});emailApi.email.mockResolvedValue({enabled:true,smtp_host:'smtp.example.com',smtp_port:587,security:'starttls',sender_email:'sender@example.com',smtp_username:'sender@example.com',password_configured:true});});
describe('Schedule dirty drafts and UI preferences',()=>{
 it('keeps a dirty schedule draft across local and cross-tab language/theme changes',async()=>{
  render(<AppProviders><Controls/><TaskSchedulePage/></AppProviders>); await screen.findByText('Daily check'); const user=userEvent.setup();
  await user.click(screen.getByRole('button',{name:'✎'})); const goal=screen.getByLabelText('Task instructions'); const name=screen.getByLabelText('Schedule name');
  await user.clear(goal); await user.type(goal,'Unsaved schedule goal'); await user.clear(name); await user.type(name,'Unsaved schedule name');
  await user.click(screen.getByText('local-language')); await user.click(screen.getByText('local-theme'));
  expect(goal).toHaveValue('Unsaved schedule goal'); expect(name).toHaveValue('Unsaved schedule name');
  act(()=>window.dispatchEvent(new StorageEvent('storage',{key:UI_PREFERENCES_STORAGE_KEY,newValue:JSON.stringify({version:1,language:'en',theme:'light'})})));
  expect(goal).toHaveValue('Unsaved schedule goal'); expect(name).toHaveValue('Unsaved schedule name');
 });
});

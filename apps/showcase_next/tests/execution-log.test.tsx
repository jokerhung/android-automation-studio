import { render,screen } from '@testing-library/react';
import { describe,it,expect,vi } from 'vitest';
import { ExecutionLog } from '@/features/workspace/components/execution-log';
const locale={language:'vi'};
vi.mock('@/app/providers',()=>({useAppPreferences:()=>({preferences:locale,t:(key:string)=>key})}));
describe('Readable execution log',()=>{
 it('renders the persisted action and its trace once, retaining coordinates',()=>{
  render(<ExecutionLog steps={[{step_number:3,action_taken:{action:'click',coordinates:[500,875],args:{target:16}},generic_tools:[{name:'click',payload:{args:{target:16,normalized_coordinates:[500,875]}}}]}]}/>);
  expect(screen.getAllByText('Chạm phần tử')).toHaveLength(1);
  expect(screen.getByText('[500, 875]')).toBeInTheDocument();
 });
 it('merges the coordinate-less trace without hiding a different tap or repeated execution',()=>{
  render(<ExecutionLog steps={[{step_number:3,action_taken:{action:'click',coordinates:[500,875],args:{target:16}},generic_tools:[{name:'click',payload:{args:{target:16}}},{name:'click',payload:{args:{target:17}}},{name:'click',payload:{args:{target:16}}}]}]}/>);
  expect(screen.getAllByText('Chạm phần tử')).toHaveLength(3);
  expect(screen.getByText('17')).toBeInTheDocument();
 });
 it('keeps different coordinates and independent primary actions',()=>{
  render(<ExecutionLog steps={[{step_number:3,action_taken:[{action:'click',args:{target:16},coordinates:[1,2]},{action:'click',args:{target:16},coordinates:[1,2]}],generic_tools:[{name:'click',payload:{args:{target:16,normalized_coordinates:[3,4]}}}]}]}/>);
  expect(screen.getAllByText('Chạm phần tử')).toHaveLength(3);
 });
 it('renders action cards, coordinates and activity without technical JSON',()=>{
  render(<ExecutionLog steps={[{step_id:'private-id',session_id:'session-id',step_number:1,duration:15,total_tokens:9900,pre_image_name:'internal-image',action_taken:{action:'tap',coordinates:[906,49],args:{}},operator_raw_thinking:'Đã tìm thấy nút tài khoản.',summary:'Màn hình hồ sơ đã mở.'}]}/>);
  expect(screen.getByText('Chạm phần tử')).toBeInTheDocument();
  expect(screen.getByText('[906, 49]')).toHaveClass('execution-coordinates');
  expect(screen.getByText('Đã tìm thấy nút tài khoản.')).toBeInTheDocument();
  expect(screen.getByText('Màn hình hồ sơ đã mở.')).toBeInTheDocument();
  expect(screen.queryByText(/private-id|session-id|internal-image|operator_raw_thinking/)).toBeNull();
 });
 it('handles encoded and multiple actions without rendering unsafe HTML',()=>{
  render(<ExecutionLog steps={[{step_number:2,action_taken:JSON.stringify([{action:'manage_app',args:{action:'launch',app_name:'com.example.app'}},{action:'wait_for_delay',args:{duration:'3000ms'}}]),summary:'<img src=x onerror=alert(1)>'}]}/>);
  expect(screen.getByText('Mở ứng dụng')).toBeInTheDocument();
  expect(screen.getByText('com.example.app')).toBeInTheDocument();
  expect(screen.getByText('3000ms')).toBeInTheDocument();
  expect(document.querySelector('.execution-log img')).toBeNull();
 });
 it('updates an existing step when stream content arrives',()=>{
  const {rerender}=render(<ExecutionLog steps={[{step_id:'same',step_number:1}]}/>);
  rerender(<ExecutionLog steps={[{step_id:'same',step_number:1,summary:'Hoàn tất'}]}/>);
  expect(document.querySelectorAll('.execution-step')).toHaveLength(1);
  expect(screen.getByText('Hoàn tất')).toBeInTheDocument();
 });
});

import {fireEvent,render,screen} from '@testing-library/react';
import {describe,it,expect,vi} from 'vitest';
import {DeviceViewer} from '@/features/workspace/components/workspace-panels';
import type {SessionDetails} from '@/features/workspace/types';
const patch=vi.fn();
vi.mock('@/app/providers',()=>({useAppPreferences:()=>({preferences:{language:'en'}})}));
vi.mock('@/features/workspace/provider',()=>({useWorkspace:()=>({state:{player:{sessionId:'s',mode:'video',currentTime:0,playbackRate:1,playing:false,stepIndex:0}},setPlayerSession:()=>{},patchPlayer:patch})}));
const details=(video:SessionDetails['video']):SessionDetails=>({session:{},steps:[],checks:[],notes:{},usage:{},startup:[],video});
describe('Replay time slider',()=>{
 it('seeks a single recording after metadata and shows total time',()=>{
  const {container}=render(<DeviceViewer session={{session_id:'s',status:'completed'}} isActive={false} details={details({video_url:'/videos/test.mp4'})}/>);
  const video=container.querySelector('video')!;
  expect(screen.getByRole('slider',{name:'Seek video'})).toBeDisabled();
  Object.defineProperty(video,'duration',{value:120,configurable:true});
  Object.defineProperty(video,'readyState',{value:1,configurable:true});
  fireEvent.loadedMetadata(video);
  expect(screen.getByText('0:00 / 2:00')).toBeInTheDocument();
  fireEvent.change(screen.getByRole('slider'),{target:{value:'45'}});
  expect(video.currentTime).toBe(45);
  expect(patch).toHaveBeenLastCalledWith({currentTime:45});
 });
 it('maps a seek across segments to the correct timeline position',()=>{
  render(<DeviceViewer session={{session_id:'s',status:'completed'}} isActive={false} details={details({video_segments:[{url:'/videos/a.mp4',start:0,duration:30},{url:'/videos/b.mp4',start:30,duration:40}]})}/>);
  expect(screen.getByRole('slider')).toHaveAttribute('max','70');
  fireEvent.change(screen.getByRole('slider'),{target:{value:'48'}});
  expect(patch).toHaveBeenLastCalledWith({currentTime:48,activeSegmentIndex:1});
 });
});

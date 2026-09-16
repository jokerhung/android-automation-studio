import type { Metadata } from 'next';
import { TaskSchedulePage } from '@/features/schedules/task-schedule-page';
export const metadata: Metadata = { title: 'Task Schedule' };
export default function SchedulePage(){ return <TaskSchedulePage/>; }

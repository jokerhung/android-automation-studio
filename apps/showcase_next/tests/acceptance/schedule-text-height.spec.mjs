import {test,expect} from '@playwright/test';
test('schedule descriptions have equal fixed height and scroll independently',async({page})=>{
 await page.route('**/api/**',route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/schedules'))return route.fulfill({json:{schedules:['Short','Long'].map((name,i)=>({id:name,name,goal:i?'A long task description. '.repeat(150):'Short description',enabled:true,profile:'flash',device_serial:'test',schedule_type:'interval',interval_minutes:15,weekdays:[],timezone:'UTC',version:1}))}});
  if(path.endsWith('/sessions'))return route.fulfill({json:[]});
  if(path.endsWith('/stream'))return route.fulfill({contentType:'text/event-stream',body:':fixture\n\n'});
  return route.fulfill({json:{}});
 });
 await page.goto('/task-schedule/');
 const short=page.getByRole('region',{name:'Task instructions: Short'});
 const long=page.getByRole('region',{name:'Task instructions: Long'});
 await expect(long).toBeVisible();
 expect((await short.boundingBox()).height).toBe(160);
 expect((await long.boundingBox()).height).toBe(160);
 expect(await long.evaluate(el=>el.scrollHeight>el.clientHeight)).toBe(true);
 await long.focus();await page.keyboard.press('End');
 await expect.poll(()=>long.evaluate(el=>el.scrollTop)).toBeGreaterThan(0);
 expect(await short.evaluate(el=>el.scrollTop)).toBe(0);
});

import {test,expect} from '@playwright/test';
for(const status of ['running','completed'])test(`log follow and fixed header: ${status}`,async({page})=>{
 await page.setViewportSize({width:1440,height:900});
 await page.route('**/api/**',route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/stream'))return route.fulfill({contentType:'text/event-stream',body:':fixture\n\n'});
  if(path.endsWith('/sessions'))return route.fulfill({json:[{session_id:'follow-test',status,goal:'Fixed task header'}]});
  if(path.endsWith('/status'))return route.fulfill({json:{status,session_id:'follow-test'}});
  if(path.endsWith('/steps'))return route.fulfill({json:Array.from({length:30},(_,i)=>({step_number:i+1,summary:'Recorded step '+i}))});
  return route.fulfill({json:{}});
 });
 await page.goto('/workspace/?session=follow-test');
 await expect(page.locator('.execution-step')).toHaveCount(30);
 const viewport=page.locator('.ws-log-viewport');
 const header=await page.locator('.ws-session-header').boundingBox();
 const tabs=await page.locator('.ws-tabs').boundingBox();
 if(status==='running')await expect.poll(()=>viewport.evaluate(el=>el.scrollHeight-el.clientHeight-el.scrollTop)).toBeLessThan(2);
 else expect(await viewport.evaluate(el=>el.scrollTop)).toBe(0);
 await viewport.evaluate(el=>{el.scrollTop=100;});
 expect((await page.locator('.ws-session-header').boundingBox()).y).toBe(header.y);
 expect((await page.locator('.ws-tabs').boundingBox()).y).toBe(tabs.y);
 // Simulate layout growth after streamed text arrives; ResizeObserver must follow.
 await page.locator('.ws-log-content').evaluate(el=>{const block=document.createElement('div');block.style.height='300px';el.append(block);});
 if(status==='running')await expect.poll(()=>viewport.evaluate(el=>el.scrollHeight-el.clientHeight-el.scrollTop)).toBeLessThan(2);
 else expect(await viewport.evaluate(el=>el.scrollTop)).toBe(100);
 expect(await page.evaluate(()=>window.scrollY)).toBe(0);
 expect(await page.locator('.ws-rail').evaluate(el=>el.scrollTop)).toBe(0);
});

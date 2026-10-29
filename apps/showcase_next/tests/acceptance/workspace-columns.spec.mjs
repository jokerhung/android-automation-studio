import { test, expect } from '@playwright/test';

for (const theme of ['light', 'dark']) test(`three workspace columns with independent scrolling: ${theme}`, async ({page}) => {
  await page.setViewportSize({width:1648,height:930});
  await page.addInitScript(theme=>localStorage.setItem('artemis.ui.preferences.v1',JSON.stringify({version:1,language:'en',theme})),theme);
  await page.route('**/api/**',route=>{
    const path=new URL(route.request().url()).pathname;
    const sessions=Array.from({length:20},(_,i)=>({session_id:`fixture-${i}`,status:'completed',goal:`Inspect application screens and verify the recorded result ${i+1}`,device_serial:'TEST-ANDROID',created_at:'2026-09-15T09:30:00Z'}));
    if(path.endsWith('/stream'))return route.fulfill({contentType:'text/event-stream',body:':fixture\n\n'});
    if(path.endsWith('/sessions'))return route.fulfill({json:sessions});
    if(path.endsWith('/steps'))return route.fulfill({json:Array.from({length:40},(_,i)=>({step_number:i+1,action_taken:{action:'tap',coordinates:[906,49],args:{}},goal:'Inspect the next application screen',duration:15,total_tokens:9900,operator_raw_thinking:'The account control is visible. Open the profile screen and verify the resulting state.',summary:'The profile screen opened successfully.',status:'completed'}))});
    return route.fulfill({json:{}});
  });
  await page.goto('/workspace/?session=fixture-0');
  await expect(page.locator('.ws-device-card')).toBeVisible();
  await expect(page.getByRole('tab',{name:'logs',exact:true})).toHaveAttribute('aria-selected','true');
  const [left,middle,right]=await Promise.all(['.ws-main','.ws-viewer-column','.ws-rail'].map(s=>page.locator(s).boundingBox()));
  expect(middle.x).toBeCloseTo(left.x+left.width,0);
  expect(right.x).toBeCloseTo(middle.x+middle.width,0);
  expect(left.width).toBeGreaterThan(middle.width);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBe(1648);
  await page.locator('.ws-log-viewport').evaluate(el=>{el.scrollTop=150;});
  expect(await page.locator('.ws-log-viewport').evaluate(el=>el.scrollTop)).toBe(150);
  expect(await page.locator('.ws-rail').evaluate(el=>el.scrollTop)).toBe(0);
  expect((await page.locator('.ws-device-card').boundingBox()).y).toBeGreaterThanOrEqual(60);
  const composer=await page.locator('.ws-composer').boundingBox();
  expect(composer.x+composer.width).toBeLessThanOrEqual(middle.x);
  await page.screenshot({path:`test-results/design/workspace-three-columns-${theme}.png`,fullPage:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBe(390);
});

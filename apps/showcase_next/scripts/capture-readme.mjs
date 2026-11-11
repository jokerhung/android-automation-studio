// Capture the running application. No mocked responses, task runs, or settings writes.
import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
const output=resolve(import.meta.dirname,'../../../docs/assets/screenshots');
await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH}:{})});
try {
 const context=await browser.newContext({viewport:{width:1440,height:960},deviceScaleFactor:1});
 // Preferences affect this disposable browser profile only.
 await context.addInitScript(()=>localStorage.setItem('artemis.ui.preferences.v1',JSON.stringify({version:1,language:'en',theme:'dark'})));
 await context.route('**/api/**',route=>['GET','HEAD','OPTIONS'].includes(route.request().method())?route.continue():route.abort());
 const page=await context.newPage();
 for(const [name,path,ready] of [
  ['home','/','.homeComposer'],
  ['workspace','/workspace/','.ws-main'],
  ['task-schedule','/task-schedule/','main'],
 ]) {
  await page.goto('http://localhost:8009'+path,{waitUntil:'domcontentloaded'});
  await page.locator(ready).waitFor();
  await page.waitForTimeout(1500);
  if(name==='workspace'&&await page.locator('.ws-task').count()){
    await page.locator('.ws-task').first().click();
    await page.locator('.execution-step').first().waitFor({timeout:10000}).catch(()=>{});
  }
  // Blur private content in this disposable browser only; never alter backend data.
  const selectors = name === 'workspace'
   ? ['.ws-task-copy', '.ws-task-meta', '.ws-session-header h2', '.ws-session-header p', '.execution-narrative p', '.execution-action dd', '.execution-action summary span', '.execution-error', '.ws-device-card h2', '.ws-device-stage', '.ws-device-controls span', '.ws-note', '.ws-plan', '.ws-result']
   : name === 'task-schedule'
    ? ['article h3', 'article [role="region"]', 'article dd']
    : [];
  if (selectors.length) await page.addStyleTag({content: selectors.join(',') + '{filter:blur(14px) !important; user-select:none !important;}'});
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({path:resolve(output,name+'.png'),fullPage:false,animations:'disabled'});
  console.log(`Captured ${name} from ${page.url()}`);
 }
 await context.close();
} finally {await browser.close();}

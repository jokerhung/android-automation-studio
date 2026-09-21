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
  ['settings','/settings/','.settingsCard'],
 ]) {
  await page.goto('http://localhost:8009'+path,{waitUntil:'domcontentloaded'});
  await page.locator(ready).waitFor();
  await page.waitForTimeout(1500);
  if(name==='workspace'&&await page.locator('.ws-task').count()){
    await page.locator('.ws-task').first().click();
    await page.locator('.execution-step').first().waitFor({timeout:10000}).catch(()=>{});
  }
  // Redact real task/account/device data at capture time; never alter backend data.
  const masks=name==='workspace'?[page.locator('.ws-task-copy'),page.locator('.ws-task-meta'),page.locator('.ws-session-header h2'),page.locator('.ws-session-header p'),page.locator('.execution-narrative p'),page.locator('.execution-action dd'),page.locator('.execution-error'),page.locator('.ws-device-card h2'),page.locator('.ws-device-stage'),page.locator('.ws-device-controls span')]
   :name==='task-schedule'?[page.locator('article h3'),page.locator('article [role="region"]'),page.locator('article dd')]:[];
  await page.screenshot({path:resolve(output,name+'.png'),fullPage:false,mask:masks,maskColor:'#354255'});
  console.log(`Captured ${name} from ${page.url()}`);
  if(name==='task-schedule'){
    await page.getByRole('button',{name:/New schedule/}).first().click();
    await page.getByRole('dialog').waitFor();
    await page.getByRole('dialog').screenshot({path:resolve(output,'new-schedule.png')});
  }
 }
 await context.close();
} finally {await browser.close();}

// Hermetic visual review: serves compiled assets only, never the user's backend.
import { createServer } from 'node:http';
import { readFile, stat, mkdir } from 'node:fs/promises';
import { resolve, extname, sep } from 'node:path';
import { chromium } from '@playwright/test';
const app = resolve(import.meta.dirname, '..');
const output = resolve(app, 'test-results/design');
await mkdir(output, { recursive: true });
const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon','.woff2':'font/woff2','.txt':'text/plain'};
const server=createServer(async(req,res)=>{
  const path=new URL(req.url,'http://localhost').pathname;
  const root=resolve(app,'out');
  const relative=path;
  let file=resolve(root,'.'+decodeURIComponent(relative));
  if(!file.startsWith(root+sep)&&file!==root){res.writeHead(403).end();return;}
  try{if((await stat(file)).isDirectory())file=resolve(file,'index.html');await stat(file);}catch{file=resolve(root,'index.html');}
  try{let data=await readFile(file);res.setHeader('Content-Type',mime[extname(file)]??'application/octet-stream');res.end(data);}catch{res.writeHead(404).end();}
});
await new Promise(done=>server.listen(0,'127.0.0.1',done));
const origin=`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 for(const theme of ['light','dark']){
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  await context.addInitScript(theme=>localStorage.setItem('artemis.ui.preferences.v1',JSON.stringify({version:1,language:'en',theme})),theme);
  await context.route('**/api/**',route=>{
   const path=new URL(route.request().url()).pathname;
   let data={};
   if(path.endsWith('/readiness'))data={overall_ready:true,blocker_count:0,probes:[],active_device:null};
   else if(path.endsWith('/run/defaults'))data={verification_level:'final',explorer_mode:'flash'};
   else if(path.endsWith('/windows-startup'))data={enabled:false,supported:true,port:8009};
   else if(path.endsWith('/settings/model'))data={provider:'openai',default_model:'gpt-4.1',fallback_model:'gpt-4.1-mini',base_url:'',fallback_url:'',version:'test',keys_configured:{},node_overrides:[]};
   else if(path.endsWith('/emulator/status'))data={status:'idle',logs:[],avd_name:null};
   else if(path.endsWith('/sessions'))data=[];
   else if(path.endsWith('/stream')){return route.fulfill({contentType:'text/event-stream',body:': fixture\n\n'});}
   else if(path.endsWith('/schedules'))data={schedules:[]};
   else if(path.endsWith('/devices'))data={devices:[]};
   return route.fulfill({json:data});
  });
  const page=await context.newPage();
  for(const [name,path] of [['home','/'],['settings','/settings/'],['models','/settings/?tab=models'],['schedule','/task-schedule/'],['workspace','/workspace/']]){
   await page.goto(origin+path);await page.waitForTimeout(800);
   await page.screenshot({path:resolve(output,`${name}-${theme}.png`),fullPage:true});
   if(name==='home'){await page.getByRole('button',{name:'Pro',exact:true}).first().click();await page.screenshot({path:resolve(output,`home-pro-${theme}.png`),fullPage:true});}
   if(name==='schedule'){await page.getByRole('button',{name:/New schedule/}).first().click();await page.screenshot({path:resolve(output,`schedule-modal-${theme}.png`),fullPage:true});}
   console.log(name,theme,await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth})));
  }
  await page.setViewportSize({width:390,height:844});
  await page.goto(origin+'/settings/');await page.waitForTimeout(500);await page.screenshot({path:resolve(output,`settings-mobile-${theme}.png`),fullPage:true});
  await context.close();
 }
}finally{await browser.close();server.close();}

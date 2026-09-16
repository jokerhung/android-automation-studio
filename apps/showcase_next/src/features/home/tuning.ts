import type { ExplorerModeId, TuningLevel, VerificationLevelId } from './models';
export const VERIFICATION_LEVELS: readonly TuningLevel<VerificationLevelId>[] = [
 {id:'off',label:'Off',tagline:'No checking. The run ends as soon as the task looks done.',latency:'no extra time',runs:['Actions complete without a pass / fail verdict.'],skips:['Nothing is double-checked or retried.'],bestFor:'Quick tries and demos.'},
 {id:'final',label:'At the end',tagline:'One check of the finished result against your goal.',latency:'adds about 20–60 s at the end',runs:['The final screen, history, and device state are checked.','A mismatch can be fixed up to 3 times.'],skips:['Nothing is checked while the task is running.'],bestFor:'Everyday tasks.'},
 {id:'checkpoints',label:'Every step',tagline:'Each step is checked, plus the final check.',latency:'a short background check after each step',runs:['Each completed step is checked immediately.','A wrong step can be fixed before moving on.'],bestFor:'Long tasks where early mistakes compound.'},
 {id:'strict',label:'Strict',tagline:'Every step is checked with more retries; failed tests stop the run.',latency:'slowest: more checks and retries',runs:['Checks get more attempts.','The first failed test stops the run with evidence.'],bestFor:'Release checks and regression runs.'},
];
export const EXPLORER_MODES: readonly TuningLevel<ExplorerModeId>[] = [
 {id:'flash',label:'Quick glance',tagline:'Finds buttons and text in a single look.',latency:'1 look per search',runs:['Several clearly labelled things can be found at once.'],skips:['No zooming and no second try.'],bestFor:'Ordinary apps with clear labels.'},
 {id:'pro',label:'Second look',tagline:'Takes up to 3 looks, thinking between attempts.',latency:'up to 3 looks per search',runs:['Reads layout before searching the image.','Tries a different approach after a miss.'],skips:['No close-up crops.'],bestFor:'Unclear labels or position-based descriptions.'},
 {id:'ultra',label:'Close-up',tagline:'Zooms into screen regions and takes up to 8 looks.',latency:'up to 8 looks per search',runs:['Crops and magnifies crowded areas and tiny text.'],bestFor:'Crowded screens, charts, drawings, and precise placement.'},
];
export const DEFAULT_VERIFICATION_LEVEL: VerificationLevelId='final';
export const DEFAULT_EXPLORER_MODE: ExplorerModeId='flash';
export function levelIndex<T extends string>(levels:readonly TuningLevel<T>[], value:string|null|undefined, fallback:T){const index=levels.findIndex(level=>level.id===String(value??'').trim().toLowerCase());return index>=0?index:Math.max(0,levels.findIndex(level=>level.id===fallback));}

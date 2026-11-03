export function imagePoint(event: {clientX:number;clientY:number}, rect:DOMRect, naturalWidth:number, naturalHeight:number) {
 const scale=Math.min(rect.width/naturalWidth,rect.height/naturalHeight), ox=rect.left+(rect.width-naturalWidth*scale)/2, oy=rect.top+(rect.height-naturalHeight*scale)/2;
 if(event.clientX<ox||event.clientX>ox+naturalWidth*scale||event.clientY<oy||event.clientY>oy+naturalHeight*scale)return null;
 return {x:Math.round((event.clientX-ox)/scale),y:Math.round((event.clientY-oy)/scale)};
}
export const KEYMAP:Record<string,string>={Enter:'enter',Backspace:'delete',Tab:'tab',Escape:'escape',ArrowUp:'dpad_up',ArrowDown:'dpad_down',ArrowLeft:'dpad_left',ArrowRight:'dpad_right',Home:'move_home',End:'move_end'};

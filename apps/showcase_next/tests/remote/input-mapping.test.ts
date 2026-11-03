import { describe, expect, it } from 'vitest';
import { imagePoint, KEYMAP } from '@/features/remote/input-mapping';

function rect(left:number, top:number, width:number, height:number): DOMRect {
  return {left, top, width, height, right:left+width, bottom:top+height, x:left, y:top, toJSON(){}} as DOMRect;
}
describe('remote input mapping', () => {
  it('maps contain letterbox coordinates to device pixels', () => {
    expect(imagePoint({clientX:250,clientY:250}, rect(0,0,1000,500), 500,1000)).toBeNull();
    expect(imagePoint({clientX:500,clientY:250}, rect(0,0,1000,500), 500,1000)).toEqual({x:250,y:500});
  });
  it('maps a downscaled stream using the device coordinate space', () => {
    // The stream JPEG can be 411x960 while the phone is 1080x2520. The
    // displayed rectangle still represents the full device screen.
    expect(imagePoint({clientX:205.5,clientY:480}, rect(0,0,411,960), 1080,2520)).toEqual({x:540,y:1260});
  });
  it('exposes the Android special-key allowlist', () => {
    expect(KEYMAP).toMatchObject({Enter:'enter',Backspace:'delete',Escape:'escape',ArrowDown:'dpad_down'});
    expect(KEYMAP['F5']).toBeUndefined();
  });
});

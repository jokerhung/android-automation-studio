import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { AgentService } from '../../services/agent.service';
import { FloatingVideoPlayerComponent } from './floating-video-player.component';

describe('Workspace docked screen player', () => {
  function setup(docked = true) {
    const service = {
      isVideoWindowOpen: signal(true), isVideoMinimized: signal(false),
      activeVideoUrl: signal(null), activeVideoSegments: signal([]),
      activeVideoTitle: signal('Test screen'), currentSessionId: signal('run-1'),
      currentSessionStepFrames: signal([]), videoSeekRequest: signal(null), stepSeekRequest: signal(null),
      recordingPlaybackStatus: signal('live'), playerMode: signal('video'),
      hasCurrentSessionStepFrames: signal(false),
      closeVideoPlayer: () => service.isVideoWindowOpen.set(false)
    };
    TestBed.configureTestingModule({
      imports: [FloatingVideoPlayerComponent],
      providers: [{ provide: AgentService, useValue: service }]
    });
    const fixture = TestBed.createComponent(FloatingVideoPlayerComponent);
    fixture.componentRef.setInput('docked', docked);
    fixture.componentInstance.liveStreamUrl.set('data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7');
    fixture.nativeElement.style.cssText = 'display:block;width:300px;height:600px';
    fixture.detectChanges();
    return { fixture, service };
  }

  it('renders live view in-flow and fits inside the dock', () => {
    const { fixture } = setup();
    const wrapper = fixture.nativeElement.querySelector('.floating-video-wrapper');
    expect(wrapper.classList.contains('docked')).toBeTrue();
    expect(getComputedStyle(wrapper).position).toBe('relative');
    expect(wrapper.style.left).toBe('');
    expect(wrapper.getBoundingClientRect().height).toBe(600);
    expect(fixture.nativeElement.querySelector('.live-screen-img')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('[aria-label="Theater"]')).toBeNull();
    expect(fixture.nativeElement.querySelector('[aria-label="Minimize"]')).toBeNull();
  });

  it('does not drag or hide the embedded stream due to old minimized state', () => {
    const { fixture, service } = setup();
    service.isVideoMinimized.set(true);
    fixture.componentInstance.startDrag(new MouseEvent('mousedown'));
    fixture.detectChanges();
    expect((fixture.componentInstance as any).isDragging).toBeFalse();
    expect(fixture.nativeElement.querySelector('.live-screen-img')).not.toBeNull();
  });

  it('removes the image request when closed', () => {
    const { fixture, service } = setup();
    fixture.nativeElement.querySelector('.close-btn').click();
    fixture.detectChanges();
    expect(service.isVideoWindowOpen()).toBeFalse();
    expect(fixture.nativeElement.querySelector('.live-screen-img')).toBeNull();
  });

  it('keeps the floating player available outside Workspace', () => {
    const { fixture } = setup(false);
    const wrapper = fixture.nativeElement.querySelector('.floating-video-wrapper');
    expect(getComputedStyle(wrapper).position).toBe('fixed');
    expect([...fixture.nativeElement.querySelectorAll('.header-btn')]
      .some((button: Element) => button.textContent?.includes('open_in_full'))).toBeTrue();
  });
});

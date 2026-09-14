import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { WindowsStartupComponent } from './windows-startup.component';

describe('Start with Windows setting', () => {
  function setup(supported = true) {
    TestBed.configureTestingModule({ imports: [WindowsStartupComponent], providers: [provideHttpClient(), provideHttpClientTesting()] });
    const fixture = TestBed.createComponent(WindowsStartupComponent);
    const http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http.expectOne('/api/system/windows-startup').flush({ supported, enabled: false, port: null });
    fixture.detectChanges();
    return { fixture, http, input: fixture.nativeElement.querySelector('input') as HTMLInputElement };
  }

  it('reads state without enabling startup', () => {
    const { input, http } = setup();
    expect(input.checked).toBeFalse();
    expect(input.disabled).toBeFalse();
    http.verify();
  });

  it('saves only the enabled flag after an explicit toggle', () => {
    const { fixture, http, input } = setup();
    input.click(); fixture.detectChanges();
    const request = http.expectOne('/api/system/windows-startup');
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toEqual({ enabled: true });
    expect(input.disabled).toBeTrue();
    request.flush({ supported: true, enabled: true, port: 8009 });
    fixture.detectChanges();
    expect(input.checked).toBeTrue();
    expect(fixture.nativeElement.textContent).toContain('8009');
    http.verify();
  });

  it('keeps the old state and shows an inline error if saving fails', () => {
    const { fixture, http, input } = setup();
    input.click();
    http.expectOne('/api/system/windows-startup').flush({ detail: 'Permission denied' }, { status: 500, statusText: 'Error' });
    fixture.detectChanges();
    expect(input.checked).toBeFalse();
    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain('Permission denied');
    http.verify();
  });

  it('disables the switch outside Windows', () => {
    const { input, http } = setup(false);
    expect(input.disabled).toBeTrue();
    http.verify();
  });

  it('renders a rounded track with a white thumb and green checked state', () => {
    const { fixture, http, input } = setup();
    const track = fixture.nativeElement.querySelector('.switch-track');
    const thumb = fixture.nativeElement.querySelector('.switch-thumb');
    track.style.transition = 'none';
    thumb.style.transition = 'none';
    expect(input.getAttribute('role')).toBe('switch');
    expect(getComputedStyle(track).borderRadius).toBe('999px');
    expect(getComputedStyle(thumb).backgroundColor).toBe('rgb(255, 255, 255)');
    expect(getComputedStyle(track).backgroundColor).toBe('rgb(203, 213, 225)');
    input.click();
    http.expectOne('/api/system/windows-startup').flush({ supported: true, enabled: true, port: 8009 });
    fixture.detectChanges();
    expect(getComputedStyle(track).backgroundColor).toBe('rgb(67, 208, 92)');
    expect(getComputedStyle(thumb).transform).toBe('matrix(1, 0, 0, 1, 28, 0)');
    http.verify();
  });
});

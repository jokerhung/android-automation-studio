import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { routes } from '../../app.routes';
import { HomeComponent } from '../../pages/home/home.component';
import { NavSwitcherComponent } from './nav-switcher.component';

describe('Settings navigation', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [NavSwitcherComponent],
      providers: [provideRouter(routes), provideHttpClient(), provideHttpClientTesting()]
    });
  });

  it('places Settings immediately after Task Schedule', () => {
    const fixture = TestBed.createComponent(NavSwitcherComponent);
    fixture.detectChanges();
    const links = [...fixture.nativeElement.querySelectorAll('a')] as HTMLAnchorElement[];
    expect(links.map(link => link.querySelector('.tab-label')?.textContent?.trim()))
      .toEqual(['Home', 'Workspace', 'Task Schedule', 'Settings']);
    expect(links[3].getAttribute('href')).toBe('/settings');
  });

  it('opens setup directly at /settings and returns to the launcher via Home', async () => {
    const harness = await RouterTestingHarness.create();
    const settings = await harness.navigateByUrl('/settings', HomeComponent);
    expect(settings.activeTab()).toBe('diagnostics');
    expect(harness.routeNativeElement?.querySelector('h1')?.textContent?.trim()).toBe('Settings');
    expect(harness.routeNativeElement?.querySelector('.setup-guide-view')).not.toBeNull();
    expect(harness.routeNativeElement?.querySelector('.mode-tabs-container')).toBeNull();
    const home = await harness.navigateByUrl('/', HomeComponent);
    expect(home.activeTab()).toBe('launcher');
    expect(harness.routeNativeElement?.querySelector('.task-launcher-view')).not.toBeNull();
    const reopened = await harness.navigateByUrl('/settings', HomeComponent);
    expect(reopened.activeTab()).toBe('diagnostics');
  });

  it('routes the readiness shortcut and launch button to the corresponding pages', async () => {
    const harness = await RouterTestingHarness.create();
    const home = await harness.navigateByUrl('/', HomeComponent);
    const navigate = spyOn(TestBed.inject(Router), 'navigate').and.resolveTo(true);
    home.setTab('diagnostics');
    expect(navigate).toHaveBeenCalledWith(['/settings']);
    home.proceedToLauncher();
    expect(navigate).toHaveBeenCalledWith(['/']);
  });
});

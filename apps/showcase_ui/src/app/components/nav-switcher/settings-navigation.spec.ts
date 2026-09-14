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

  it('shows one settings panel at a time and preserves model form state', async () => {
    const harness = await RouterTestingHarness.create();
    const settings = await harness.navigateByUrl('/settings', HomeComponent);
    const root = harness.routeNativeElement!;
    const tabs = [...root.querySelectorAll<HTMLButtonElement>('[role="tab"]')];
    const visiblePanels = () => root.querySelectorAll('.settings-panel:not([hidden])');
    expect(tabs.map(tab => tab.textContent?.trim())).toEqual([
      'tuneGeneral', 'auto_awesomeAI Model', 'smartphoneAndroid Devices', 'computerSystem & Environment'
    ]);
    expect(visiblePanels().length).toBe(1);
    expect(visiblePanels()[0].id).toBe('settings-panel-general');
    expect(visiblePanels()[0].querySelector('app-windows-startup')).not.toBeNull();
    tabs[1].click(); harness.detectChanges();
    expect(visiblePanels()[0].id).toBe('settings-panel-models');
    settings.geminiKeyInput.set('unsaved-test-value');
    settings.isGeminiKeyEdited.set(true);
    tabs[2].click(); harness.detectChanges();
    expect(visiblePanels()[0].id).toBe('settings-panel-android');
    tabs[1].click(); harness.detectChanges();
    expect(settings.geminiKeyInput()).toBe('unsaved-test-value');
    tabs[3].click(); harness.detectChanges();
    expect(visiblePanels()[0].id).toBe('settings-panel-system');
    expect(root.querySelector('.settings-close')?.getAttribute('aria-label')).toBe('Close Settings');
  });

  it('supports roving keyboard focus in settings tabs', async () => {
    const harness = await RouterTestingHarness.create();
    const settings = await harness.navigateByUrl('/settings', HomeComponent);
    const tabs = [...harness.routeNativeElement!.querySelectorAll<HTMLButtonElement>('[role="tab"]')];
    tabs[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    harness.detectChanges();
    expect(settings.settingsTab()).toBe('models');
    expect(tabs[1].getAttribute('aria-selected')).toBe('true');
    expect(tabs[1].tabIndex).toBe(0);
    expect(tabs[0].tabIndex).toBe(-1);
    tabs[1].dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true }));
    harness.detectChanges();
    expect(settings.settingsTab()).toBe('system');
  });

  it('shows the launch banner only in System & Environment when ready', async () => {
    const harness = await RouterTestingHarness.create();
    const settings = await harness.navigateByUrl('/settings', HomeComponent);
    const ready = spyOn(settings, 'isReady').and.returnValue(true);
    const root = harness.routeNativeElement!;
    for (const tab of ['general', 'models', 'android'] as const) {
      settings.settingsTab.set(tab);
      harness.detectChanges();
      expect(root.querySelector('.ready-banner-footer')).toBeNull();
    }
    settings.settingsTab.set('system');
    harness.detectChanges();
    expect(root.querySelector('.ready-banner-footer .btn-proceed-launch')).not.toBeNull();
    ready.and.returnValue(false);
    harness.detectChanges();
    expect(root.querySelector('.ready-banner-footer')).toBeNull();
  });
});

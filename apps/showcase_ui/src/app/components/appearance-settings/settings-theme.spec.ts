import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { routes } from '../../app.routes';
import { HomeComponent } from '../../pages/home/home.component';
import { UI_PREFERENCES_STORAGE_KEY, UiPreferencesService } from '../../services/ui-preferences.service';

describe('Settings theme colors', () => {
  beforeEach(() => {
    localStorage.removeItem(UI_PREFERENCES_STORAGE_KEY);
    TestBed.configureTestingModule({providers:[provideRouter(routes),provideHttpClient(),provideHttpClientTesting()]});
  });
  afterEach(() => {
    localStorage.removeItem(UI_PREFERENCES_STORAGE_KEY);
    document.documentElement.dataset['theme']='light';
  });

  it('switches card, label and choice colors together without recoloring the white toggle thumb', async () => {
    const harness = await RouterTestingHarness.create();
    const page = await harness.navigateByUrl('/settings', HomeComponent);
    const preferences = TestBed.inject(UiPreferencesService);
    const root = harness.routeNativeElement!;
    preferences.setTheme('dark'); harness.detectChanges();
    const style = (selector:string) => getComputedStyle(root.querySelector(selector)!);
    expect(style('.appearance-card').backgroundColor).toBe('rgb(18, 24, 36)');
    expect(style('.preference-label').color).toBe('rgb(241, 245, 249)');
    expect(style('.choices label:not(.selected)').backgroundColor).toBe('rgb(18, 24, 36)');
    expect(style('.choices label.selected').backgroundColor).toBe('rgb(23, 42, 70)');
    expect(style('app-windows-startup section').backgroundColor).toBe('rgb(18, 24, 36)');
    expect(style('app-windows-startup p').color).toBe('rgb(148, 163, 184)');
    expect(style('app-windows-startup .switch-thumb').backgroundColor).toBe('rgb(255, 255, 255)');
    preferences.setTheme('light'); harness.detectChanges();
    expect(style('app-windows-startup section').backgroundColor).toBe('rgb(255, 255, 255)');
    expect(style('.preference-label').color).toBe('rgb(15, 23, 42)');
  });

  it('themes the model card, textbox, and restart confirmation', async () => {
    const harness = await RouterTestingHarness.create();
    const page = await harness.navigateByUrl('/settings', HomeComponent);
    TestBed.inject(HttpTestingController).expectOne('/api/settings/model').flush({provider:'openai',default_model:'test',fallback_model:'backup',fallback_provider:'openai',base_url:'',fallback_url:'',version:'test',keys_configured:{},node_overrides:[]});
    page.settingsTab.set('models');
    TestBed.inject(UiPreferencesService).setTheme('dark'); harness.detectChanges();
    const root = harness.routeNativeElement!;
    expect(getComputedStyle(root.querySelector('.model-editor')!).backgroundColor).toBe('rgb(18, 24, 36)');
    expect(getComputedStyle(root.querySelector('.model-editor input')!).color).toBe('rgb(241, 245, 249)');
    await harness.fixture.whenStable();
    root.querySelector<HTMLFormElement>('.model-editor form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
    harness.detectChanges();
    expect(getComputedStyle(root.querySelector('.confirm-dialog')!).backgroundColor).toBe('rgb(18, 24, 36)');
  });

  it('themes Home composer, descriptors and navigation without affecting Light', async () => {
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl('/', HomeComponent);
    const preferences = TestBed.inject(UiPreferencesService);
    const root = harness.routeNativeElement!;
    root.querySelector<HTMLElement>('.composer-card')!.style.transition = 'none';
    preferences.setTheme('dark'); harness.detectChanges();
    const style = (selector:string) => getComputedStyle(root.querySelector(selector)!);
    expect(style('.composer-card').backgroundColor).toBe('rgb(18, 24, 36)');
    expect(style('.composer-model-descriptor').backgroundColor).toBe('rgb(32, 42, 58)');
    expect(style('.desc-line').color).toBe('rgb(203, 213, 225)');
    expect(style('.model-toggle-btn.active').backgroundColor).toBe('rgb(38, 51, 72)');
    preferences.setTheme('light'); harness.detectChanges();
    expect(style('.composer-card').backgroundColor).not.toBe('rgb(18, 24, 36)');
  });
});

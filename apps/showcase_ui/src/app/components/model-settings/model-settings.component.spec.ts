import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ModelSettingsComponent } from './model-settings.component';

describe('Model settings editor', () => {
  const data = {provider:'openai',default_model:'primary',fallback_model:'backup',fallback_provider:'openai',base_url:'https://proxy.example/v1',fallback_url:'',version:'v1',keys_configured:{openai:true},config_path:'config/artemis.jsonc',env_path:'.env',node_overrides:[]};
  function setup() {
    TestBed.configureTestingModule({imports:[ModelSettingsComponent],providers:[provideHttpClient(),provideHttpClientTesting()]});
    const fixture = TestBed.createComponent(ModelSettingsComponent);
    const http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http.expectOne('/api/settings/model').flush(data);
    fixture.detectChanges();
    return {fixture,http,component:fixture.componentInstance};
  }
  it('loads model settings with a blank secret input', () => {
    const {component,http,fixture} = setup();
    expect(component.draft.default_model).toBe('primary');
    expect(component.apiKey).toBe('');
    expect(fixture.nativeElement.querySelector('input[type="password"]')).not.toBeNull();
    http.verify();
  });
  it('warns before any save or restart and allows cancel', () => {
    const {component,http,fixture} = setup();
    component.confirmSave({invalid:false} as any);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alertdialog"]').textContent).toContain('restart');
    http.expectNone(req=>req.method==='PUT');
    fixture.nativeElement.querySelector('.buttons button').click();
    expect(component.confirming()).toBeFalse();
    http.verify();
  });
  it('uses readable textbox text and a visible border', () => {
    const {fixture,http} = setup();
    const input = fixture.nativeElement.querySelector('input[name="defaultModel"]') as HTMLInputElement;
    const style = getComputedStyle(input);
    expect(style.fontSize).toBe('14px');
    expect(style.fontWeight).toBe('400');
    expect(style.color).toBe('rgb(15, 23, 42)');
    expect(style.borderTopWidth).toBe('1px');
    expect(style.borderTopColor).toBe('rgb(148, 163, 184)');
    expect(style.opacity).toBe('1');
    http.verify();
  });
  it('saves only after confirmation and keeps the draft on a busy conflict', () => {
    const {component,http} = setup();
    component.draft.default_model='new-model';
    component.save();
    const request=http.expectOne('/api/settings/model');
    expect(request.request.body).toEqual(jasmine.objectContaining({default_model:'new-model',api_key:null,confirm_restart:true,expected_version:'v1'}));
    request.flush({detail:'Wait until idle'}, {status:409,statusText:'Conflict'});
    expect(component.error()).toBe('Wait until idle');
    expect(component.draft.default_model).toBe('new-model');
    expect(component.busy()).toBeFalse();
    http.verify();
  });
  it('waits for a new server PID before reporting restart success', fakeAsync(() => {
    const {component,http,fixture} = setup();
    component.save();
    http.expectOne('/api/settings/model').flush({status:'restarting',previous_pid:100});
    tick(2500);
    http.expectOne('/api/system/server-status').flush({current_pid:100});
    expect(component.busy()).toBeTrue();
    tick(1500);
    http.expectOne('/api/system/server-status').flush({current_pid:101});
    http.expectOne('/api/settings/model').flush({...data,version:'v2'});
    expect(component.busy()).toBeFalse();
    expect(component.message()).toContain('restarted');
    fixture.destroy(); http.verify();
  }));
  it('clears typed credentials and URL when changing providers', () => {
    const {component,http} = setup();
    component.apiKey='unsaved-secret';
    component.draft.provider='google'; component.providerChanged();
    expect(component.apiKey).toBe('');
    expect(component.draft.base_url).toBe(''); http.verify();
  });
});

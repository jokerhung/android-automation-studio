import { TestBed } from '@angular/core/testing';
import { AppearanceSettingsComponent } from './appearance-settings.component';
import { UI_PREFERENCES_STORAGE_KEY } from '../../services/ui-preferences.service';

describe('AppearanceSettingsComponent', () => {
  beforeEach(() => {
    localStorage.removeItem(UI_PREFERENCES_STORAGE_KEY);
    TestBed.configureTestingModule({ imports: [AppearanceSettingsComponent] });
  });

  afterEach(() => localStorage.removeItem(UI_PREFERENCES_STORAGE_KEY));

  it('renders accessible EN/VI and Light/Dark controls and persists changes', () => {
    const fixture = TestBed.createComponent(AppearanceSettingsComponent);
    fixture.detectChanges();
    const inputs = fixture.nativeElement.querySelectorAll('input') as NodeListOf<HTMLInputElement>;
    expect(inputs.length).toBe(4);
    expect(fixture.nativeElement.querySelectorAll('fieldset legend').length).toBe(2);
    expect(fixture.nativeElement.textContent).toContain('English');
    expect(fixture.nativeElement.textContent).toContain('Tiếng Việt');
    expect(fixture.nativeElement.textContent).not.toContain('added separately');
    expect(fixture.nativeElement.textContent).toContain('Changes the ARTEMIS web interface immediately without reloading.');
    inputs[1].click();
    fixture.detectChanges();
    expect(document.documentElement.lang).toBe('vi');
    expect(fixture.nativeElement.querySelector('[role="status"]').textContent).toContain('Đã áp dụng Tiếng Việt và đã lưu');
    inputs[3].click();
    fixture.detectChanges();
    expect(document.documentElement.dataset['theme']).toBe('dark');
    expect(JSON.parse(localStorage.getItem(UI_PREFERENCES_STORAGE_KEY)!)).toEqual({ version: 1, language: 'vi', theme: 'dark' });
  });

  it('renders all control copy from the active translation catalog', () => {
    const fixture = TestBed.createComponent(AppearanceSettingsComponent);
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('input[value="vi"]') as HTMLInputElement).click();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Giao diện & Ngôn ngữ');
    expect(fixture.nativeElement.textContent).toContain('Đổi ngay ngôn ngữ giao diện web ARTEMIS mà không cần tải lại trang.');
    expect(fixture.nativeElement.textContent).toContain('Sáng');
    expect(fixture.nativeElement.textContent).toContain('Tối');
  });

  it('announces honestly when persistence fails', () => {
    const fixture = TestBed.createComponent(AppearanceSettingsComponent);
    fixture.detectChanges();
    spyOn(localStorage, 'setItem').and.throwError('quota');
    (fixture.nativeElement.querySelector('input[value="dark"]') as HTMLInputElement).click();
    fixture.detectChanges();
    expect(document.documentElement.dataset['theme']).toBe('dark');
    expect(fixture.nativeElement.querySelector('[aria-live="polite"]').textContent).toContain('could not be saved');
  });
});

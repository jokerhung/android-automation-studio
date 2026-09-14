import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { TranslationKey } from '../../core/i18n/en';
import { TranslationService } from '../../core/i18n/translation.service';
import { UiLanguage, UiPreferencesService, UiTheme } from '../../services/ui-preferences.service';

@Component({
  selector: 'app-appearance-settings',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './appearance-settings.component.html',
  styleUrl: './appearance-settings.component.scss'
})
export class AppearanceSettingsComponent {
  readonly preferences = inject(UiPreferencesService);
  readonly i18n = inject(TranslationService);
  private readonly statusKey = signal<TranslationKey | null>(null);
  readonly status = computed(() => {
    const key = this.statusKey();
    return key ? this.i18n.translate(key) : '';
  });

  chooseLanguage(language: UiLanguage): void {
    if (language === this.preferences.language()) return;
    const result = this.preferences.setLanguage(language);
    this.statusKey.set(result.persisted ? 'appearance.savedLanguage' : 'appearance.sessionLanguage');
  }

  chooseTheme(theme: UiTheme): void {
    if (theme === this.preferences.theme()) return;
    const result = this.preferences.setTheme(theme);
    if (theme === 'dark') {
      this.statusKey.set(result.persisted ? 'appearance.savedDark' : 'appearance.sessionDark');
    } else {
      this.statusKey.set(result.persisted ? 'appearance.savedLight' : 'appearance.sessionLight');
    }
  }
}

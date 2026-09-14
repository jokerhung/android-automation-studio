import { parseUiPreferences } from './app/services/ui-preferences.service';

describe('UI preference bootstrap contract', () => {
  it('keeps runtime validation aligned with bootstrap defaults and enums', async () => {
    const source = await (await fetch('/ui-preferences-bootstrap.js')).text();
    expect(source).toContain("'artemis.ui.preferences.v1'");
    expect(source).toContain('value.version === 1');
    expect(source).toContain("value.language === 'en' || value.language === 'vi'");
    expect(source).toContain("value.theme === 'light' || value.theme === 'dark'");
    expect(parseUiPreferences(null)).toEqual({ version: 1, language: 'en', theme: 'light' });
  });
});

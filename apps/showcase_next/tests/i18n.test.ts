import { describe,expect,it } from 'vitest';
import { translate } from '@/lib/i18n/translate';
describe('i18n',()=>{
  it('uses Vietnamese when available',()=>expect(translate('vi','nav.home')).toBe('Trang chủ'));
  it('falls back to English for missing Vietnamese keys',()=>expect(translate('vi','app.name')).toBe('AAS'));
  it('renders nullish interpolation as empty and keeps missing placeholders',()=>{expect(translate('en','home.characterCount',{count:null})).toBe(' characters');expect(translate('en','home.characterCount')).toBe('{{count}} characters');});
});

(function () {
  'use strict';
  var key = 'artemis.ui.preferences.v1';
  var language = 'en';
  var theme = 'light';
  try {
    var raw = window.localStorage.getItem(key);
    if (raw !== null) {
      var value = JSON.parse(raw);
      if (value && typeof value === 'object' && value.version === 1) {
        if (value.language === 'en' || value.language === 'vi') language = value.language;
        if (value.theme === 'light' || value.theme === 'dark') theme = value.theme;
      }
    }
  } catch (_) {
    // Defaults remain usable when localStorage is blocked or malformed.
  }
  document.documentElement.lang = language;
  document.documentElement.setAttribute('data-theme', theme);
}());

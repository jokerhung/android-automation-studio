'use client';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';

import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from 'react';
import { PreferencesPanel } from '@/components/preferences-panel';
import { useAppPreferences } from '@/app/providers';
import {
  settingsApi,
  type ModelProvider,
  type ModelSettings,
  type StartupStatus,
} from './api';

const errorText = (error: unknown, fallback: string) =>
  error instanceof Error ? error.message : fallback;

export function GeneralSettings() {
  const { t } = useAppPreferences();
  const [status, setStatus] = useState<StartupStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    settingsApi.startup(controller.signal).then(setStatus).catch((reason: unknown) => {
      if (!controller.signal.aborted) {
        setError(errorText(reason, t('settings.startup.loadError')));
      }
    });
    return () => controller.abort();
  }, [t]);

  async function toggle() {
    if (!status || busy) return;
    setBusy(true);
    setError('');
    try {
      setStatus(await settingsApi.setStartup(!status.enabled));
    } catch (reason) {
      setError(errorText(reason, t('settings.startup.changeError')));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="settingsStack">
      <header className="generalHeading"><h2>{t('settings.general')}</h2><p>{t('settings.generalDescription')}</p></header>
      <PreferencesPanel />
      <section className="card settingsSection">
        <div className="settingRow">
          <div>
            <h2>{t('settings.startup.title')}</h2>
            <p>{t('settings.startup.body')}</p>
          </div>
          <Switch aria-label={t('settings.startup.title')} checked={status?.enabled ?? false} disabled={!status?.supported || busy || !status} onCheckedChange={()=>void toggle()} className="startupSwitch"/>
        </div>
        {!status && !error && <p role="status">{t('settings.startup.loading')}</p>}
        {status?.supported === false && <p>{t('settings.startup.windowsOnly')}</p>}
        {status?.enabled && (
          <p>{t('settings.startup.enabled',{port:status.port ? ` on port ${status.port}` : ''})}</p>
        )}
        {error && <p role="alert" className="inlineError">{error}</p>}
      </section>
    </div>
  );
}

type ModelDraft = {
  provider: ModelProvider;
  default_model: string;
  fallback_model: string;
  base_url: string;
  fallback_url: string;
};

const blankDraft: ModelDraft = {
  provider: 'openai',
  default_model: '',
  fallback_model: '',
  base_url: '',
  fallback_url: '',
};

const providers: Array<[ModelProvider, string]> = [
  ['openai', 'OpenAI'],
  ['google', 'Google Gemini'],
  ['anthropic', 'Anthropic'],
  ['openrouter', 'OpenRouter'],
  ['xai', 'xAI'],
  ['custom', 'Custom'],
  ['ollama', 'Ollama'],
  ['vllm', 'vLLM'],
];

export function ModelSettingsPanel() {
  const { t } = useAppPreferences();
  const [saved, setSaved] = useState<ModelSettings | null>(null);
  const [draft, setDraft] = useState<ModelDraft>(blankDraft);
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const lifetime = useRef<AbortController | null>(null);
  const restoreFocus = useRef<string | null>(null);

  function apply(value: ModelSettings) {
    setSaved(value);
    setDraft({
      provider: value.provider,
      default_model: value.default_model,
      fallback_model: value.fallback_model,
      base_url: value.base_url ?? '',
      fallback_url: value.fallback_url ?? '',
    });
    setApiKey('');
  }

  async function load(signal?: AbortSignal) {
    setLoading(true);
    setError('');
    try {
      apply(await settingsApi.model(signal));
      queueMicrotask(() => {
        const name = restoreFocus.current;
        if (name) document.querySelector<HTMLElement>(`[name="${name}"]`)?.focus();
      });
    } catch (reason) {
      if (!signal?.aborted) {
        setError(errorText(reason, 'Unable to load model settings.'));
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }

  // This load is intentionally mount-only so unrelated rerenders cannot reset a dirty draft.
  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    void load(controller.signal);
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setMessage('');
    if (!draft.default_model.trim() || !draft.fallback_model.trim()) {
      setError(t('settings.models.required'));
      return;
    }
    setConfirming(true);
  }

  async function reconnect(previousPid: number) {
    for (let attempt = 0; attempt < 60 && !lifetime.current?.signal.aborted; attempt += 1) {
      await new Promise<void>((resolve) => {
        window.setTimeout(resolve, attempt === 0 ? 2500 : 1500);
      });
      if (lifetime.current?.signal.aborted) return;
      try {
        const state = await settingsApi.serverStatus(lifetime.current?.signal);
        if (state.current_pid && state.current_pid !== previousPid) {
          setMessage('ARTEMIS restarted and reconnected.');
          await load(lifetime.current?.signal);
          return;
        }
      } catch {
        // The server is expected to be temporarily unavailable during restart.
      }
    }
    setError('ARTEMIS did not reconnect within 90 seconds. Check the server and reload.');
    setMessage('');
  }

  async function save() {
    if (!saved || busy) return;
    restoreFocus.current = (document.activeElement as HTMLInputElement | null)?.name || 'defaultModel';
    setConfirming(false);
    setBusy(true);
    setError('');
    setMessage('Saving and restarting…');
    try {
      const result = await settingsApi.saveModel(
        {
          ...draft,
          api_key: apiKey || null,
          expected_version: saved.version,
          confirm_restart: true,
        },
        lifetime.current?.signal,
      );
      setApiKey('');
      if (result.status !== 'restarting' || typeof result.previous_pid !== 'number') {
        setMessage('');
        setError(result.message || 'Saved, but ARTEMIS must be restarted manually.');
        return;
      }
      setMessage('Restarting ARTEMIS; reconnecting…');
      await reconnect(result.previous_pid);
    } catch (reason) {
      if (!lifetime.current?.signal.aborted) {
        setMessage('');
        setError(errorText(reason, 'Unable to save model settings.'));
      }
    } finally {
      if (!lifetime.current?.signal.aborted) setBusy(false);
    }
  }

  return (
    <section className="card settingsSection" aria-labelledby="models-heading">
      <h2 id="models-heading">{t('settings.models.title')}</h2>
      <p>{t('settings.models.body')}</p>
      {loading && !saved && <p role="status">{t('settings.models.loading')}</p>}
      {saved && (
        <form onSubmit={submit} noValidate>
          <fieldset disabled={busy}>
            <label>
              {t('settings.models.provider')}
              <select
                name="provider"
                value={draft.provider}
                onChange={(event) => {
                  setDraft({
                    ...draft,
                    provider: event.target.value as ModelProvider,
                    base_url: '',
                    fallback_url: '',
                  });
                  setApiKey('');
                }}
              >
                {providers.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
              </select>
            </label>
            <div className="fieldGrid">
              <label>
                {t('settings.models.default')}
                <input
                  name="defaultModel"
                  required
                  maxLength={200}
                  value={draft.default_model}
                  onChange={(event) => setDraft({ ...draft, default_model: event.target.value })}
                />
              </label>
              <label>
                {t('settings.models.fallback')}
                <input
                  name="fallbackModel"
                  required
                  maxLength={200}
                  value={draft.fallback_model}
                  onChange={(event) => setDraft({ ...draft, fallback_model: event.target.value })}
                />
              </label>
            </div>
            <label>
              {t('settings.models.apiKey')}
              <small>{saved.keys_configured[draft.provider] ? t('settings.models.configured') : t('settings.models.notConfigured')}</small>
              <input
                name="apiKey"
                type="password"
                autoComplete="new-password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder={t('settings.models.credential')}
              />
            </label>
            {draft.provider !== 'google' && (
              <div className="fieldGrid">
                <label>
                  {t('settings.models.baseUrl')}
                  <input
                    name="baseUrl"
                    value={draft.base_url}
                    onChange={(event) => setDraft({ ...draft, base_url: event.target.value })}
                  />
                </label>
                <label>
                  {t('settings.models.fallbackUrl')}
                  <input
                    name="fallbackUrl"
                    value={draft.fallback_url}
                    onChange={(event) => setDraft({ ...draft, fallback_url: event.target.value })}
                  />
                </label>
              </div>
            )}
            <Button variant="outline" className="primaryButton" type="submit">{t('settings.models.save')}</Button>
          </fieldset>
        </form>
      )}
      {error && <p role="alert" className="inlineError">{error}</p>}
      {message && <p role="status" className="inlineSuccess">{message}</p>}
      {confirming && (
        <div className="modalBackdrop">
          <section role="alertdialog" aria-modal="true" aria-labelledby="restart-title" className="confirmCard">
            <h2 id="restart-title">{t('settings.models.confirmTitle')}</h2>
            <p>{t('settings.models.confirmBody')}</p>
            <div className="buttonRow">
              <Button variant="outline" type="button" onClick={() => setConfirming(false)}>{t('settings.models.cancel')}</Button>
              <Button variant="outline" type="button" className="primaryButton" onClick={save}>{t('settings.models.saveNow')}</Button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

'use client';
import { Button } from '@/components/ui/button';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useAppPreferences } from '@/app/providers';
import {
  settingsApi,
  type AdbEndpoint,
  type EmulatorState,
  type ReadinessReport,
} from './api';

const errorText = (error: unknown, fallback: string) =>
  error instanceof Error ? error.message : fallback;

const POLLED_EMULATOR_STATUSES: EmulatorState['status'][] = [
  'starting',
  'waiting_for_adb',
  'booting',
];

const isEmulatorStarting = (state: EmulatorState | null) =>
  Boolean(state && POLLED_EMULATOR_STATUSES.includes(state.status));

type ActionResult = {
  report?: ReadinessReport | undefined;
  message?: string | undefined;
  endpoint?: AdbEndpoint | undefined;
};

function useReadiness() {
  const { t } = useAppPreferences();
  const [report, setReport] = useState<ReadinessReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const active = useRef<AbortController | null>(null);

  const refresh = useCallback(async (force = false) => {
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setLoading(true);
    setError('');
    try {
      const next = await settingsApi.readiness(force, controller.signal);
      setReport((current) => !current || next.timestamp >= current.timestamp ? next : current);
    } catch (reason) {
      if (!controller.signal.aborted) {
        setError(errorText(reason, t('settings.system.readinessError')));
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void refresh();
    const onFocus = () => void refresh();
    window.addEventListener('focus', onFocus);
    return () => {
      active.current?.abort();
      window.removeEventListener('focus', onFocus);
    };
  }, [refresh]);

  return { report, setReport, loading, error, setError, refresh };
}

export function AndroidSettingsPanel() {
  const { t } = useAppPreferences();
  const { report, setReport, loading, error, setError, refresh } = useReadiness();
  const [endpoint, setEndpoint] = useState<AdbEndpoint | null>(null);
  const [host, setHost] = useState('127.0.0.1');
  const [port, setPort] = useState(5037);
  const [deviceHost, setDeviceHost] = useState('');
  const [devicePort, setDevicePort] = useState(5555);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [emulator, setEmulator] = useState<EmulatorState | null>(null);
  const lifetime = useRef<AbortController | null>(null);
  const emulatorRequest = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    settingsApi.adbStatus(controller.signal).then((result) => {
      setEndpoint(result.endpoint);
      setHost(result.endpoint.host);
      setPort(result.endpoint.port);
    }).catch(() => undefined);
    settingsApi.emulatorStatus(controller.signal).then(setEmulator).catch(() => undefined);
    return () => {
      controller.abort();
      emulatorRequest.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (!isEmulatorStarting(emulator)) return;

    let disposed = false;
    let timer: number | undefined;
    let inFlight = false;

    const cancelPoll = () => {
      if (timer !== undefined) {
        window.clearTimeout(timer);
        timer = undefined;
      }
      emulatorRequest.current?.abort();
      emulatorRequest.current = null;
      inFlight = false;
    };

    const poll = async () => {
      if (disposed || document.hidden || inFlight) return;
      inFlight = true;
      const controller = new AbortController();
      emulatorRequest.current = controller;
      try {
        const state = await settingsApi.emulatorStatus(controller.signal);
        if (disposed || controller.signal.aborted) return;
        setEmulator(state);
        if (state.status === 'ready') void refresh(true);
      } catch (reason) {
        if (!disposed && !controller.signal.aborted) {
          setError(errorText(reason, t('settings.android.monitorError')));
        }
      } finally {
        if (emulatorRequest.current === controller) {
          emulatorRequest.current = null;
          inFlight = false;
          schedule();
        }
      }
    };

    const schedule = () => {
      if (!disposed && !document.hidden && timer === undefined && !inFlight) {
        timer = window.setTimeout(() => {
          timer = undefined;
          void poll();
        }, 1000);
      }
    };

    const onVisibilityChange = () => {
      if (document.hidden) {
        cancelPoll();
      } else {
        void poll();
      }
    };

    schedule();
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      disposed = true;
      cancelPoll();
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [emulator, refresh, setError, t]);

  const adbProbe = report?.probes.find((probe) => probe.id === 'android_adb');
  const devices = Array.isArray(adbProbe?.metadata.devices)
    ? adbProbe.metadata.devices as Array<{ serial: string; state: string; model?: string }>
    : [];
  const avds = Array.isArray(adbProbe?.metadata.installed_avds)
    ? adbProbe.metadata.installed_avds as string[]
    : [];

  async function run(action: () => Promise<ActionResult>) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const result = await action();
      if (result.report) setReport(result.report);
      if (result.endpoint) setEndpoint(result.endpoint);
      setNotice(result.message || t('settings.android.updated'));
    } catch (reason) {
      setError(errorText(reason, t('settings.android.operationError')));
    } finally {
      setBusy(false);
    }
  }

  async function configureServer(mode: 'probe' | 'connect' | 'local') {
    await run(async () => {
      const response = mode === 'probe'
        ? await settingsApi.probeAdb(host, port)
        : mode === 'connect'
          ? await settingsApi.connectAdb(host, port)
          : await settingsApi.useLocalAdb();
      return {
        report: response.report,
        message: response.connection_result.message,
        endpoint: response.connection_result.endpoint,
      };
    });
  }

  async function launch(name: string) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const state = await settingsApi.launchEmulator(name, lifetime.current?.signal);
      setEmulator(state);
      if (state.status === 'ready') await refresh(true);
    } catch (reason) {
      if (!lifetime.current?.signal.aborted) {
        setError(errorText(reason, t('settings.android.launchError')));
      }
    } finally {
      if (!lifetime.current?.signal.aborted) setBusy(false);
    }
  }

  async function stopEmulator() {
    emulatorRequest.current?.abort();
    await run(async () => {
      await settingsApi.stopEmulator(lifetime.current?.signal);
      setEmulator((current) => current ? {
        ...current,
        status: 'stopped',
        stage_message: t('settings.android.emulatorStopped'),
        can_retry: true,
      } : current);
      return { message: t('settings.android.emulatorStopped') };
    });
  }

  async function dismissEmulator() {
    await run(async () => {
      await settingsApi.dismissEmulator(lifetime.current?.signal);
      setEmulator(null);
      return { message: t('settings.android.emulatorDismissed') };
    });
  }

  return (
    <div className="settingsStack">
      <section className="card settingsSection">
        <h2>{t('settings.android.adbServer')}</h2>
        <p>{t('settings.android.adbServerBody')}</p>
        <div className="fieldGrid">
          <label>
            {t('settings.android.host')}
            <input value={host} onChange={(event) => setHost(event.target.value)} />
          </label>
          <label>
            {t('settings.android.port')}
            <input type="number" min={1} max={65535} value={port} onChange={(event) => setPort(Number(event.target.value))} />
          </label>
        </div>
        <p>{t('settings.android.active')}: {endpoint ? `${endpoint.mode} · ${endpoint.socket}` : t('settings.android.loading')}</p>
        <div className="buttonRow">
          <Button variant="outline" type="button" disabled={busy} onClick={() => configureServer('probe')}>{t('settings.android.testEndpoint')}</Button>
          <Button variant="outline" type="button" disabled={busy} className="primaryButton" onClick={() => configureServer('connect')}>{t('settings.android.useRemote')}</Button>
          <Button variant="outline" type="button" disabled={busy} onClick={() => configureServer('local')}>{t('settings.android.useLocal')}</Button>
        </div>
      </section>

      <section className="card settingsSection">
        <div className="sectionHeading">
          <div>
            <h2>{t('settings.android.devices')}</h2>
            <p>{t('settings.android.devicesBody')}</p>
          </div>
          <Button variant="outline" type="button" disabled={busy || loading} onClick={() => refresh(true)}>{t('settings.android.recheck')}</Button>
        </div>
        <div className="fieldGrid">
          <label>
            {t('settings.android.wirelessHost')}
            <input value={deviceHost} onChange={(event) => setDeviceHost(event.target.value)} placeholder="192.168.1.20" />
          </label>
          <label>
            {t('settings.android.wirelessPort')}
            <input type="number" value={devicePort} onChange={(event) => setDevicePort(Number(event.target.value))} />
          </label>
        </div>
        <div className="buttonRow">
          <Button variant="outline"
            type="button"
            disabled={busy || !deviceHost}
            onClick={() => run(async () => {
              const response = await settingsApi.connectDevice(deviceHost, devicePort);
              return { report: response.report, message: t('settings.android.wirelessRequested') };
            })}
          >
            {t('settings.android.connectDevice')}
          </Button>
          <Button variant="outline"
            type="button"
            disabled={busy}
            onClick={() => run(async () => {
              const response = await settingsApi.restartAdb();
              return {
                report: response.report,
                message: endpoint?.mode === 'remote' ? t('settings.android.devicesRefreshed') : t('settings.android.adbRestarted'),
              };
            })}
          >
            {endpoint?.mode === 'remote' ? t('settings.android.refreshDevices') : t('settings.android.restartAdb')}
          </Button>
        </div>
        <div className="deviceList">
          {devices.map((device) => (
            <Button variant="outline"
              type="button"
              key={device.serial}
              disabled={busy || device.state !== 'device'}
              className={report?.active_device?.serial === device.serial ? 'device active' : 'device'}
              onClick={() => run(async () => {
                const response = await settingsApi.selectDevice(device.serial);
                return {
                  report: response.report,
                  message: t('settings.android.selectedDevice', { device: device.model || device.serial }),
                };
              })}
            >
              <strong>{device.model || device.serial}</strong>
              <small>{device.serial} · {device.state}</small>
            </Button>
          ))}
        </div>
        {!devices.length && !loading && <p>{t('settings.android.noDevices')}</p>}
      </section>

      <section className="card settingsSection">
        <h2>{t('settings.android.emulator')}</h2>
        <p>{t('settings.android.emulatorBody')}</p>
        <div className="deviceList">
          {avds.map((name) => (
            <Button variant="outline" type="button" key={name} disabled={busy} onClick={() => launch(name)}>{name}</Button>
          ))}
        </div>
        {!avds.length && <p>{t('settings.android.noAvds')}</p>}
        {emulator && emulator.status !== 'idle' && (
          <div className="progressCard">
            <strong>{emulator.avd_name || t('settings.android.emulatorFallback')} · {emulator.status}</strong>
            <progress max={100} value={emulator.progress_percent} />
            <p>{emulator.stage_message}</p>
            {emulator.status === 'failed' && emulator.error && (
              <p role="alert" className="inlineError">{emulator.error}</p>
            )}
            {emulator.logs.length > 0 && (
              <pre aria-label={t('settings.android.emulatorLogs')}>{emulator.logs.join('\n')}</pre>
            )}
            <div className="buttonRow">
              {isEmulatorStarting(emulator) && (
                <Button variant="outline" type="button" disabled={busy} onClick={stopEmulator}>
                  {t('settings.android.stopEmulator')}
                </Button>
              )}
              {emulator.status === 'failed' && emulator.can_retry && emulator.avd_name && (
                <Button variant="outline"
                  type="button"
                  className="primaryButton"
                  disabled={busy}
                  onClick={() => launch(emulator.avd_name!)}
                >
                  {t('settings.android.retryLaunch')}
                </Button>
              )}
              {['failed', 'stopped'].includes(emulator.status) && (
                <Button variant="outline" type="button" disabled={busy} onClick={dismissEmulator}>
                  {t('settings.android.dismiss')}
                </Button>
              )}
            </div>
          </div>
        )}
      </section>
      {error && <p role="alert" className="inlineError">{error}</p>}
      {notice && <p role="status" className="inlineSuccess">{notice}</p>}
    </div>
  );
}

export function SystemSettingsPanel() {
  const { t } = useAppPreferences();
  const { report, loading, error, refresh } = useReadiness();
  const [localSettingsUrl, setLocalSettingsUrl] = useState('');
  useEffect(() => {
    if (!['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname)) {
      setLocalSettingsUrl(`http://localhost${window.location.port ? `:${window.location.port}` : ''}/settings/?tab=system`);
    }
  }, []);
  return (
    <div className="settingsStack">
      <section className="card settingsSection" aria-live="polite">
        <h2>{t('settings.setup.title')}</h2>
        <p>{t('settings.setup.body')}</p>
        <div className="sectionHeading">
          <Link className="secondaryButton" href="/settings/?tab=models">{t('settings.setup.models')}</Link>
          <Link className="secondaryButton" href="/settings/?tab=android">{t('settings.setup.android')}</Link>
        </div>
        {localSettingsUrl && <p>{t('settings.setup.localOnly')} <code>{localSettingsUrl}</code></p>}
        {error && report && <p role="status">{t('settings.setup.stale')} {new Date(report.timestamp * 1000).toLocaleString()}</p>}
      </section>
      <section className="card settingsSection">
        <div className="sectionHeading">
          <div>
            <h2>{t('settings.system.diagnostics')}</h2>
            <p>{t('settings.system.diagnosticsBody')}</p>
          </div>
          <Button variant="outline" type="button" disabled={loading} onClick={() => refresh(true)}>{t('settings.system.runDiagnostics')}</Button>
        </div>
        {loading && !report && <p role="status">{t('settings.system.checking')}</p>}
        <div className="probeList">
          {report?.probes.map((probe) => (
            <article key={probe.id} className={`probe ${probe.status}`}>
              <div><strong>{probe.title}</strong><span>{probe.status}</span></div>
              <p>{probe.summary}</p>
              <small>{probe.description}</small>
              {probe.actions.map((action, index) => (
                <div key={`${probe.id}-${index}`} className="probeAction">
                  <strong>{action.label}:</strong> {action.payload}
                </div>
              ))}
            </article>
          ))}
        </div>
        {error && <p role="alert" className="inlineError">{error}</p>}
      </section>
      {report?.overall_ready && (
        <section className="readyCta">
          <div>
            <h2>{t('settings.system.ready')}</h2>
            <p>{t('settings.system.readyBody')}</p>
          </div>
          <Link className="primaryButton" href="/">{t('settings.system.launchTask')}</Link>
        </section>
      )}
    </div>
  );
}

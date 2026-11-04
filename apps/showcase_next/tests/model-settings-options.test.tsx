import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { AppProviders } from '@/app/providers';
import { ModelSettingsPanel } from '@/features/settings/general-model-panels';

const response = (value: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(value), {
  status, headers: { 'content-type': 'application/json' },
}));

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

function mockModels(defaultModel: string, fallbackModel: string, empty = false, failure = false) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
    const url = String(input);
    if (url === '/api/settings/model/available') {
      return failure ? response({ detail: 'Endpoint unavailable' }, 502) : response({
        default_models: empty ? [] : ['primary-a', 'primary-b'],
        fallback_models: empty ? [] : ['backup-a', 'backup-b'],
      });
    }
    if (url === '/api/settings/model' && init?.method === 'PUT') {
      return response({ status: 'saved_restart_failed', message: 'Saved for test' });
    }
    if (url === '/api/settings/model') {
      return response({
        provider: 'openai', default_model: defaultModel, fallback_model: fallbackModel,
        fallback_provider: 'openai', base_url: '', fallback_url: '',
        version: '1', keys_configured: { openai: true }, node_overrides: [],
      });
    }
    throw new Error(url);
  });
}

it.each([
  ['obsolete-primary', 'obsolete-backup', '', ''],
  ['primary-a', 'obsolete-backup', 'primary-a', ''],
  ['obsolete-primary', 'backup-a', '', 'backup-a'],
  ['primary-a', 'backup-a', 'primary-a', 'backup-a'],
])('fetch renders dropdowns and retains only available selections (%s, %s)', async (
  oldPrimary, oldBackup, expectedPrimary, expectedBackup,
) => {
  const fetch = mockModels(oldPrimary, oldBackup);
  const user = userEvent.setup();
  render(<AppProviders><ModelSettingsPanel /></AppProviders>);
  await screen.findByLabelText('Default model');
  await user.click(screen.getByRole('button', { name: 'Fetch models' }));
  const primary = await screen.findByRole('combobox', { name: 'Default model' });
  const backup = screen.getByRole('combobox', { name: 'Fallback model' });
  expect(primary).toHaveValue(expectedPrimary);
  expect(backup).toHaveValue(expectedBackup);
  expect(within(primary).getAllByRole('option').map(option => option.textContent)).toEqual([
    'Select a model', 'primary-a', 'primary-b',
  ]);
  expect(within(backup).getAllByRole('option').map(option => option.textContent)).toEqual([
    'Select a model', 'backup-a', 'backup-b',
  ]);
  if (!expectedPrimary || !expectedBackup) {
    await user.click(screen.getByRole('button', { name: 'Save and restart' }));
    expect(screen.getByRole('alert')).toHaveTextContent(/required/i);
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  }
  expect(fetch.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(0);
  await user.selectOptions(primary, 'primary-b');
  await user.selectOptions(backup, 'backup-b');
  await user.click(screen.getByRole('button', { name: 'Save and restart' }));
  await user.click(screen.getByRole('button', { name: 'Save and restart now' }));
  await waitFor(() => expect(fetch.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(1));
  const mutation = fetch.mock.calls.find(([, init]) => init?.method === 'PUT');
  expect(JSON.parse(String(mutation?.[1]?.body))).toMatchObject({
    default_model: 'primary-b', fallback_model: 'backup-b',
  });
});

it('an empty fetched list clears obsolete models and prevents saving', async () => {
  const fetch = mockModels('obsolete-primary', 'obsolete-backup', true);
  render(<AppProviders><ModelSettingsPanel /></AppProviders>);
  await screen.findByLabelText('Default model');
  await userEvent.click(screen.getByRole('button', { name: 'Fetch models' }));
  const primary = await screen.findByRole('combobox', { name: 'Default model' });
  expect(primary).toHaveValue('');
  expect(within(primary).getAllByRole('option')).toHaveLength(1);
  await userEvent.click(screen.getByRole('button', { name: 'Save and restart' }));
  expect(screen.getByRole('alert')).toHaveTextContent(/required/i);
  expect(fetch.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(0);
});

it('a failed fetch retains existing models', async () => {
  mockModels('existing-primary', 'existing-backup', false, true);
  render(<AppProviders><ModelSettingsPanel /></AppProviders>);
  await screen.findByLabelText('Default model');
  await userEvent.click(screen.getByRole('button', { name: 'Fetch models' }));
  await screen.findByRole('alert');
  expect(screen.getByLabelText('Default model')).toHaveValue('existing-primary');
  expect(screen.getByLabelText('Fallback model')).toHaveValue('existing-backup');
});

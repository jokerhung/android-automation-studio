import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DeleteFilteredHistory } from '@/features/workspace/components/delete-filtered-history';
import { translate } from '@/lib/i18n/translate';

vi.mock('@/app/providers', () => ({ useAppPreferences: () => ({ t: (key: Parameters<typeof translate>[1], params?: Record<string, string | number>) => translate('vi', key, params) }) }));
afterEach(() => vi.restoreAllMocks());
describe('Delete filtered history', () => {
  it('confirms and deletes only the supplied completed history, excluding active tasks', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const remove = vi.fn().mockResolvedValue({ status: 'success' });
    const done = vi.fn();
    render(<DeleteFilteredHistory sessions={[{ session_id: 'a', status: 'completed' }, { session_id: 'b', status: 'failed' }, { session_id: 'active', status: 'running' }]} deleteSession={remove} onDeleted={done}/>);
    fireEvent.click(screen.getByRole('button', { name: 'Xóa' }));
    await waitFor(() => expect(done).toHaveBeenCalledWith(['a', 'b']));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('2 phiên'));
    expect(remove.mock.calls).toEqual([['a'], ['b']]);
    expect(screen.getByRole('status')).toHaveTextContent('Đã xóa 2 phiên.');
  });
  it('does not send mutations when confirmation is cancelled', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    const remove = vi.fn();
    render(<DeleteFilteredHistory sessions={[{ session_id: 'a', status: 'completed' }]} deleteSession={remove} onDeleted={vi.fn()}/>);
    fireEvent.click(screen.getByRole('button', { name: 'Xóa' }));
    expect(remove).not.toHaveBeenCalled();
  });
  it('reports partial failures and does not retry a failed deletion automatically', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const remove = vi.fn().mockRejectedValueOnce(new Error('failed')).mockResolvedValueOnce({});
    const done = vi.fn();
    render(<DeleteFilteredHistory sessions={[{ session_id: 'a', status: 'failed' }, { session_id: 'b', status: 'completed' }]} deleteSession={remove} onDeleted={done}/>);
    fireEvent.click(screen.getByRole('button', { name: 'Xóa' }));
    await waitFor(() => expect(done).toHaveBeenCalledWith(['b']));
    expect(remove).toHaveBeenCalledTimes(2);
    expect(screen.getByRole('status')).toHaveTextContent('không thể xóa 1 phiên');
  });
  it('disables deletion for an empty filtered list', () => {
    render(<DeleteFilteredHistory sessions={[]} deleteSession={vi.fn()} onDeleted={vi.fn()}/>);
    expect(screen.getByRole('button', { name: 'Xóa' })).toBeDisabled();
  });
});

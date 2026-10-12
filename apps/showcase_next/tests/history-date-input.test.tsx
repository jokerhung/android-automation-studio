import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { HistoryDateInput, formatHistoryDate, parseHistoryDate } from '@/features/workspace/components/history-date-input';

describe('History dates in dd/MM/yyyy', () => {
  it('formats and parses dates without changing month/day order', () => {
    expect(formatHistoryDate('2026-10-03')).toBe('03/10/2026');
    expect(parseHistoryDate('03/10/2026')).toBe('2026-10-03');
    expect(parseHistoryDate('29/02/2024')).toBe('2024-02-29');
    expect(parseHistoryDate('29/02/2026')).toBeNull();
    expect(parseHistoryDate('31/04/2026')).toBeNull();
    expect(parseHistoryDate('10/3/2026')).toBeNull();
    expect(parseHistoryDate('')).toBe('');
  });
  it('displays the requested format and emits only valid ISO dates for filtering', () => {
    const onChange = vi.fn();
    render(<HistoryDateInput label="Từ ngày" value="2026-10-03" invalid={false} onChange={onChange}/>);
    const field = screen.getByRole('textbox', { name: 'Từ ngày' });
    expect(field).toHaveValue('03/10/2026');
    fireEvent.change(field, { target: { value: '12/10/2026' } });
    expect(onChange).toHaveBeenLastCalledWith('2026-10-12');
    onChange.mockClear();
    fireEvent.change(field, { target: { value: '31/02/2026' } });
    expect(onChange).not.toHaveBeenCalled();
    expect(field).toHaveAttribute('aria-invalid', 'true');
    fireEvent.blur(field);
    expect(field).toHaveValue('03/10/2026');
  });
  it('updates displayed text from the calendar selection and supports clearing', () => {
    const onChange = vi.fn();
    render(<HistoryDateInput label="Đến ngày" value="2026-10-03" invalid={false} onChange={onChange}/>);
    fireEvent.change(screen.getByLabelText('Đến ngày (dd/MM/yyyy)'), { target: { value: '2026-11-05' } });
    expect(screen.getByRole('textbox')).toHaveValue('05/11/2026');
    expect(onChange).toHaveBeenLastCalledWith('2026-11-05');
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '' } });
    expect(onChange).toHaveBeenLastCalledWith('');
  });
});

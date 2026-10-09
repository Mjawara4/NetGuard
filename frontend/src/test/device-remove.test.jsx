import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../api', () => ({
    default: { get: vi.fn(), post: vi.fn(() => Promise.resolve({ data: {} })), put: vi.fn(), delete: vi.fn() },
}));

import api from '../api';
import Devices from '../pages/Devices.jsx';

const LIVE = { id: 'dev-1', name: 'Counter Router', ip_address: '10.13.13.3', device_type: 'router', is_active: true, site_id: 's1' };
const GONE = { id: 'dev-2', name: 'Old Shop', ip_address: '10.13.13.9', device_type: 'router', is_active: false, site_id: 's1', archived_at: '2026-10-09T00:00:00' };

beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockImplementation((url, cfg) => {
        if (url === '/inventory/devices') return Promise.resolve({ data: cfg?.params?.archived ? [GONE] : [LIVE] });
        return Promise.resolve({ data: [] });
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.spyOn(window, 'alert').mockImplementation(() => {});
});
afterEach(() => vi.restoreAllMocks());

describe('removing a router', () => {
    it('tells the owner when the router was kept because it has payments', async () => {
        api.delete.mockResolvedValue({ data: { result: 'archived', payments: 13 } });
        render(<MemoryRouter><Devices /></MemoryRouter>);
        await screen.findAllByText('Counter Router');
        fireEvent.click(screen.getAllByRole('button', { name: /^del(ete)?$/i })[0]);
        await waitFor(() => expect(window.alert).toHaveBeenCalledWith(expect.stringMatching(/13 completed payments.*history was kept/i)));
    });

    it('says nothing extra when the device was simply deleted', async () => {
        api.delete.mockResolvedValue({ data: { result: 'deleted', payments: 0 } });
        render(<MemoryRouter><Devices /></MemoryRouter>);
        await screen.findAllByText('Counter Router');
        fireEvent.click(screen.getAllByRole('button', { name: /^del(ete)?$/i })[0]);
        await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/inventory/devices/dev-1'));
        expect(window.alert).not.toHaveBeenCalled();
    });

    it('lists removed routers and can restore one', async () => {
        render(<MemoryRouter><Devices /></MemoryRouter>);
        expect(await screen.findByText('Removed routers (1)')).toBeTruthy();
        expect(screen.getByText('Old Shop')).toBeTruthy();
        fireEvent.click(screen.getByRole('button', { name: 'Restore' }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith('/inventory/devices/dev-2/restore'));
    });
});

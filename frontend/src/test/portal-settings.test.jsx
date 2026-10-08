import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import PortalSettings from '../components/PortalSettings';
import api from '../api';

vi.mock('../api', () => ({ default: { get: vi.fn(), post: vi.fn() } }));

const DEVICE = { id: '11111111-1111-1111-1111-111111111111', device_type: 'router' };

const serve = ({ mode = 'custom', status = { directory: 'test', login_page: 'custom', has_backup: false } } = {}) => {
    api.get.mockImplementation((url) => {
        if (url.endsWith('/portal-config')) return Promise.resolve({ data: { mode, button_html: '<a>Buy WiFi</a>' } });
        if (url.endsWith('/portal/status')) return status ? Promise.resolve({ data: status }) : Promise.reject(new Error('offline'));
        return Promise.reject(new Error(`unexpected ${url}`));
    });
};

describe('PortalSettings', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        api.post.mockResolvedValue({ data: { status: 'saved' } });
    });
    afterEach(() => vi.restoreAllMocks());

    it('treats the login page as the owner\'s until they choose otherwise', async () => {
        serve();
        render(<PortalSettings device={DEVICE} />);
        expect(await screen.findByRole('button', { name: 'My own portal' })).toHaveAttribute('aria-pressed', 'true');
        expect(screen.getByRole('button', { name: 'NetGuard portal' })).toHaveAttribute('aria-pressed', 'false');
    });

    it('never assumes NetGuard\'s portal when the setting cannot be loaded', async () => {
        api.get.mockRejectedValue(new Error('offline'));
        render(<PortalSettings device={DEVICE} />);
        await waitFor(() => expect(screen.getByRole('button', { name: 'My own portal' })).toHaveAttribute('aria-pressed', 'true'));
        expect(screen.getByRole('button', { name: 'NetGuard portal' })).toHaveAttribute('aria-pressed', 'false');
    });

    it('says what the router is serving, and from which folder', async () => {
        serve();
        render(<PortalSettings device={DEVICE} />);
        expect(await screen.findByText(/serving your own login page/i)).toBeInTheDocument();
        expect(screen.getByText('test/login.html')).toBeInTheDocument();
    });

    it('does not replace the login page unless the owner confirms', async () => {
        serve();
        const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
        render(<PortalSettings device={DEVICE} />);
        fireEvent.click(await screen.findByRole('button', { name: 'NetGuard portal' }));
        expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/replace/i));
        expect(api.post).not.toHaveBeenCalled();
    });

    it('switches to NetGuard\'s portal once confirmed', async () => {
        serve();
        vi.spyOn(window, 'confirm').mockReturnValue(true);
        render(<PortalSettings device={DEVICE} />);
        fireEvent.click(await screen.findByRole('button', { name: 'NetGuard portal' }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith(`/hotspot/${DEVICE.id}/portal-mode`, { mode: 'netguard' }));
        await waitFor(() => expect(screen.getByRole('button', { name: 'NetGuard portal' })).toHaveAttribute('aria-pressed', 'true'));
    });

    it('shows the router\'s reason when a change is refused', async () => {
        serve();
        api.post.mockRejectedValue({ response: { data: { detail: 'The router did not return your login page, so nothing was changed' } } });
        render(<PortalSettings device={DEVICE} />);
        fireEvent.click(await screen.findByRole('button', { name: 'Add Buy button to my page' }));
        expect(await screen.findByRole('status')).toHaveTextContent(/nothing was changed/);
    });

    it('offers to bring the owner\'s page back only when the router has a copy', async () => {
        serve({ mode: 'netguard', status: { directory: 'hotspot', login_page: 'netguard', has_backup: true } });
        render(<PortalSettings device={DEVICE} />);
        expect(await screen.findByRole('button', { name: 'Restore my page' })).toBeEnabled();
    });

    it('disables restore when there is nothing of the owner\'s to restore', async () => {
        serve({ mode: 'netguard', status: { directory: 'hotspot', login_page: 'netguard', has_backup: false } });
        render(<PortalSettings device={DEVICE} />);
        await screen.findByText(/serving NetGuard's login page/i);
        expect(screen.getByRole('button', { name: 'Restore my page' })).toBeDisabled();
    });
});

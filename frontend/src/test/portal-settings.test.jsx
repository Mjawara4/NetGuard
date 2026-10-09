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

    it('lists the router\'s portal folders and lets the owner pick one', async () => {
        serve({ status: { directory: 'hotspot', login_page: 'custom', has_backup: false, folders: ['hotspot', 'test'], chosen_directory: '', attention: null } });
        render(<PortalSettings device={DEVICE} />);
        const picker = await screen.findByLabelText('Portal folder');
        expect(picker).toHaveValue('hotspot');
        expect(screen.getByRole('button', { name: 'Use this folder' })).toBeDisabled();
        fireEvent.change(picker, { target: { value: 'test' } });
        fireEvent.click(screen.getByRole('button', { name: 'Use this folder' }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith(`/hotspot/${DEVICE.id}/portal/folder`, { directory: 'test' }));
    });

    it('warns when the router left the folder the owner chose, with a one-click fix', async () => {
        serve({ status: { directory: 'hotspot', login_page: 'netguard', has_backup: false, folders: ['hotspot', 'test'], chosen_directory: 'test', attention: 'wrong_folder' } });
        render(<PortalSettings device={DEVICE} />);
        expect(await screen.findByRole('alert')).toHaveTextContent(/hotspot.*instead of.*test/i);
        fireEvent.click(screen.getByRole('button', { name: 'Switch back to test' }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith(`/hotspot/${DEVICE.id}/portal/folder`, { directory: 'test' }));
    });

    it('warns when NetGuard\'s page is showing on a router set to the owner\'s portal', async () => {
        serve({ status: { directory: 'hotspot', login_page: 'netguard', has_backup: false, folders: ['hotspot', 'test'], chosen_directory: '', attention: 'netguard_page' } });
        render(<PortalSettings device={DEVICE} />);
        expect(await screen.findByRole('alert')).toHaveTextContent(/NetGuard's page/i);
    });

    it('shows no warning when the router serves what the owner chose', async () => {
        serve({ status: { directory: 'test', login_page: 'custom', has_backup: true, folders: ['hotspot', 'test'], chosen_directory: 'test', attention: null } });
        render(<PortalSettings device={DEVICE} />);
        await screen.findByLabelText('Portal folder');
        expect(screen.queryByRole('alert')).toBeNull();
    });

    it('lets the owner say which hotspot to work with when the router has several', async () => {
        serve({ status: { directory: 'hotspot', login_page: 'custom', has_backup: false, folders: ['hotspot', 'test'], chosen_directory: '', attention: null,
            hotspot: 'staff', hotspots: [{ name: 'staff', interface: 'bridge-staff', directory: 'hotspot', disabled: false }, { name: 'guests', interface: 'bridge-guests', directory: 'test', disabled: false }] } });
        render(<PortalSettings device={DEVICE} />);
        const picker = await screen.findByLabelText('Hotspot');
        expect(picker).toHaveValue('staff');
        fireEvent.change(picker, { target: { value: 'guests' } });
        await waitFor(() => expect(api.post).toHaveBeenCalledWith(`/hotspot/${DEVICE.id}/portal/hotspot`, { name: 'guests' }));
    });

    it('shows no hotspot chooser on a router with one hotspot', async () => {
        serve({ status: { directory: 'test', login_page: 'custom', has_backup: false, folders: ['test'], chosen_directory: '', attention: null,
            hotspot: 'netguard', hotspots: [{ name: 'netguard', interface: 'bridge-hotspot', directory: 'test', disabled: false }] } });
        render(<PortalSettings device={DEVICE} />);
        await screen.findByLabelText('Portal folder');
        expect(screen.queryByLabelText('Hotspot')).toBeNull();
    });

    it('says the router is offline instead of showing nothing', async () => {
        api.get.mockImplementation((url) => {
            if (url.endsWith('/portal-config')) return Promise.resolve({ data: { mode: 'custom', button_html: '' } });
            return Promise.reject({ response: { status: 503, data: { detail: 'NetGuard could not reach this router.' } } });
        });
        render(<PortalSettings device={DEVICE} />);
        expect(await screen.findByText(/can't reach this router/i)).toBeInTheDocument();
    });
});

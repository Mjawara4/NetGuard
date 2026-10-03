import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';

vi.mock('../api', () => ({
    default: { get: vi.fn(), post: vi.fn() },
}));

import api from '../api';
import OnboardWizard from '../components/OnboardWizard';

const SCRIPT = { device_id: 'd1', site_slug: 'shop', script: '{ /system identity set name=shop }', api_username: 'netguard', api_password: 'AbcDefGhiJklMnoPqrStuv23', recovery_password: 'RecRecRecRecRecRecRec23', warnings: [] };

beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockImplementation((url) => {
        if (url.includes('/inventory/sites')) return Promise.resolve({ data: [{ id: 's1', name: 'Home' }] });
        if (url.includes('/monitoring/metrics')) return Promise.resolve({ data: [] });
        return Promise.resolve({ data: [] });
    });
    api.post.mockImplementation((url) => {
        if (url === '/inventory/devices') return Promise.resolve({ data: { id: 'd1', name: 'Shop' } });
        if (url.endsWith('/provision-wireguard')) return Promise.resolve({ data: { mikrotik_script: 'wg' } });
        if (url.endsWith('/provision-script')) return Promise.resolve({ data: SCRIPT });
        return Promise.resolve({ data: {} });
    });
    Object.assign(navigator, { clipboard: { writeText: vi.fn(() => Promise.resolve()) } });
});

async function walkToScript() {
    render(<OnboardWizard onClose={() => {}} onComplete={() => {}} />);
    fireEvent.change(screen.getByTestId('wiz-name'), { target: { value: 'Shop' } });
    fireEvent.click(screen.getByRole('button', { name: /add router/i }));
    await screen.findByText(/get the router ready/i);
    fireEvent.click(screen.getByRole('button', { name: /router is ready/i }));
    await screen.findByText(/turn on the vpn/i);
    fireEvent.click(screen.getByRole('button', { name: /turn on vpn/i }));
    await screen.findByText(/get your setup file/i);
    fireEvent.click(screen.getByRole('button', { name: /get script/i }));
    await screen.findByTestId('wiz-api-pw');
}

describe('onboarding wizard', () => {
    it('creates the device, then the tunnel, then the script in order', async () => {
        await walkToScript();
        const posts = api.post.mock.calls.map(([u]) => u);
        expect(posts[0]).toBe('/inventory/devices');
        expect(posts[1]).toBe('/inventory/devices/d1/provision-wireguard');
        expect(posts[2]).toBe('/inventory/devices/d1/provision-script');
    });

    it('generates the script without rotating (reuse is the default)', async () => {
        await walkToScript();
        const call = api.post.mock.calls.find(([u]) => u.endsWith('/provision-script'));
        expect(call[2].params.rotate).toBe(false);
    });

    it('shows both secrets once, with a save-now warning', async () => {
        await walkToScript();
        expect(screen.getByTestId('wiz-api-pw').textContent).toBe(SCRIPT.api_password);
        expect(screen.getByText(/shown once/i)).toBeTruthy();
        expect(screen.getByText(new RegExp(SCRIPT.recovery_password))).toBeTruthy();
    });

    it('displays the generated script, not just the download button', async () => {
        await walkToScript();
        expect(screen.getByTestId('wiz-script').textContent).toBe(SCRIPT.script);
    });

    it('prefills the WiFi name from the router name', async () => {
        render(<OnboardWizard onClose={() => {}} onComplete={() => {}} />);
        fireEvent.change(screen.getByTestId('wiz-name'), { target: { value: 'Serrekunda Shop!' } });
        fireEvent.click(screen.getByRole('button', { name: /add router/i }));
        await screen.findByText(/get the router ready/i);
        fireEvent.click(screen.getByRole('button', { name: /router is ready/i }));
        fireEvent.click(screen.getByRole('button', { name: /turn on vpn/i }));
        const slug = await screen.findByTestId('wiz-slug');
        expect(slug.value).toBe('serrekunda-shop');
    });

    it('reaches the verify step and polls for reachability', async () => {
        await walkToScript();
        fireEvent.click(screen.getByRole('button', { name: /^next$/i }));
        await screen.findByText(/apply it to the router/i);
        fireEvent.click(screen.getByRole('button', { name: /applied it/i }));
        await screen.findByTestId('wiz-reach');
        await waitFor(() => expect(api.get.mock.calls.some(([u]) => u.includes('/monitoring/metrics'))).toBe(true));
    });

    it('surfaces a real error if the device cannot be created', async () => {
        api.post.mockImplementationOnce(() => Promise.reject({ response: { data: { detail: 'No site' } } }));
        render(<OnboardWizard onClose={() => {}} onComplete={() => {}} />);
        fireEvent.change(screen.getByTestId('wiz-name'), { target: { value: 'X' } });
        fireEvent.click(screen.getByRole('button', { name: /add router/i }));
        expect(await screen.findByRole('alert')).toBeTruthy();
    });
});

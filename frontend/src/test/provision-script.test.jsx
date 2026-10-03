import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../api', () => ({
    default: {
        get: vi.fn(),
        post: vi.fn(),
        put: vi.fn(() => Promise.resolve({ data: {} })),
        delete: vi.fn(() => Promise.resolve({ data: {} })),
    },
}));

import api from '../api';
import Devices from '../pages/Devices.jsx';

const DEVICE = { id: 'dev-1', name: 'Counter Router', ip_address: '10.10.0.2', device_type: 'router', is_active: true, site_id: 's1' };
const RESULT = {
    device_id: 'dev-1',
    site_slug: 'counter-router',
    script: ':do { /system identity set name=counter-router } on-error={}',
    api_username: 'netguard',
    api_password: 'API-SECRET-111',
    recovery_password: 'RECOVERY-SECRET-222',
    warnings: ['Credentials were rotated: earlier scripts are stale.', 'The netguard user is API-only (no ssh).'],
};

const reject = (status, detail) => Promise.reject({ response: { status, data: { detail } }, message: 'Request failed' });

async function openModal() {
    render(<MemoryRouter><Devices /></MemoryRouter>);
    fireEvent.click((await screen.findAllByText('Counter Router'))[0]);
    fireEvent.click(await screen.findByRole('button', { name: /get setup script/i }));
}
const generate = () => fireEvent.click(screen.getByRole('button', { name: /^get script$/i }));
// Rotation is deliberately two clicks: a link, then a confirmation.
const generateRotating = async () => {
    fireEvent.click(screen.getByRole('button', { name: /replace the password/i }));
    await screen.findByTestId('rotate-confirm');
    fireEvent.click(screen.getByRole('button', { name: /yes, replace it/i }));
};
const scriptCalls = () => api.post.mock.calls.filter(([url]) => url.endsWith('/provision-script'));

beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockImplementation((url) => Promise.resolve({ data: url.includes('/inventory/devices') ? [DEVICE] : [] }));
    api.post.mockResolvedValue({ data: RESULT });
    Object.assign(navigator, { clipboard: { writeText: vi.fn(() => Promise.resolve()) } });
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:x');
    globalThis.URL.revokeObjectURL = vi.fn();
});

describe('router setup script', () => {
    it('warns about rotation BEFORE anything is fetched, and fetches nothing on open', async () => {
        await openModal();
        expect(screen.getByText(/replaces this router's passwords/i)).toBeTruthy();
        expect(scriptCalls()).toHaveLength(0);
    });

    it('POSTs once with slug and timezone, then shows script and both secrets with a shown-once warning', async () => {
        await openModal();
        generate();
        await screen.findByTestId('script-body');
        expect(scriptCalls()).toHaveLength(1);
        const [url, body, cfg] = scriptCalls()[0];
        expect(url).toBe('/inventory/devices/dev-1/provision-script');
        expect(body).toBeNull();
        expect(cfg.params).toEqual({ site_slug: 'counter-router', timezone: 'Africa/Banjul', rotate: false });
        expect(screen.getByTestId('script-body').textContent).toBe(RESULT.script);
        expect(screen.getByTestId('api-password').textContent).toBe('API-SECRET-111');
        expect(screen.getByTestId('recovery-password').textContent).toBe('RECOVERY-SECRET-222');
        expect(screen.getByText(/shown only once/i)).toBeTruthy();
        expect(screen.getByText(/Recovery login/)).toBeTruthy();
        expect(screen.getByText(/NetGuard API password/)).toBeTruthy();
        RESULT.warnings.forEach((w) => expect(screen.getByText(w)).toBeTruthy());
        expect(screen.getByText(/connection will drop/i)).toBeTruthy();
        expect(screen.getByText(/10\.15\.x/)).toBeTruthy();
        expect(screen.getByText(/remote or unattended install/i)).toBeTruthy();
        expect(screen.getByText(/paste the whole thing in one go/i)).toBeTruthy();
    });

    it('never copies or downloads on its own; only on explicit clicks', async () => {
        await openModal();
        generate();
        await screen.findByTestId('script-body');
        expect(navigator.clipboard.writeText).not.toHaveBeenCalled();
        expect(URL.createObjectURL).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole('button', { name: /copy script/i }));
        await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith(RESULT.script));
        let anchor = null;
        const realClick = HTMLAnchorElement.prototype.click;
        HTMLAnchorElement.prototype.click = function () { anchor = { download: this.download, href: this.href }; };
        try {
            fireEvent.click(screen.getByRole('button', { name: /download \.rsc/i }));
        } finally {
            HTMLAnchorElement.prototype.click = realClick;
        }
        expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
        const blob = URL.createObjectURL.mock.calls[0][0];
        expect(await new Promise((res) => { const r = new FileReader(); r.onload = () => res(r.result); r.readAsText(blob); })).toBe(RESULT.script);
        expect(anchor.download).toBe('netguard-counter-router.rsc');
        expect(anchor.href).toBe('blob:x');
    });

    it('renders the remedy for 409, not the raw error', async () => {
        api.post.mockImplementation(() => reject(409, 'WireGuard not provisioned for this device'));
        await openModal();
        generate();
        expect(await screen.findByText(/provision wireguard for this router first/i)).toBeTruthy();
        expect(screen.queryByText(/WireGuard not provisioned for this device/)).toBeNull();
        expect(screen.queryByTestId('script-body')).toBeNull();
    });

    it('explains 403 as an admin-only action', async () => {
        api.post.mockImplementation(() => reject(403, 'requires an organisation admin'));
        await openModal();
        generate();
        expect(await screen.findByText(/cannot generate setup scripts/i)).toBeTruthy();
        expect(screen.getByText(/organisation admins and super admins/i)).toBeTruthy();
    });

    it('shows the server message for a 400 and blocks a bad slug client-side', async () => {
        api.post.mockImplementation(() => reject(400, 'site_slug must be 2-32 chars'));
        await openModal();
        generate();
        expect(await screen.findByText(/site_slug must be 2-32 chars/)).toBeTruthy();
        fireEvent.change(screen.getByLabelText(/site name on the router/i), { target: { value: '-bad-' } });
        expect(screen.getByRole('button', { name: /^get script$/i }).disabled).toBe(true);
    });

    it('discards the secrets when the modal closes', async () => {
        await openModal();
        generate();
        await screen.findByTestId('api-password');
        fireEvent.keyDown(window, { key: 'Escape' });
        await waitFor(() => expect(screen.queryByTestId('api-password')).toBeNull());
        expect(screen.queryByText('RECOVERY-SECRET-222')).toBeNull();
    });
});

describe('downloaded file keeps its .rsc extension', () => {
    it('uses a MIME type the browser will not rename', async () => {
        // A text/plain blob makes Chrome append .txt, producing
        // netguard-<slug>.rsc.txt -- which RouterOS /import will not accept.
        // Observed on a real install.
        await openModal();
        generate();
        await screen.findByTestId('script-body');
        const realClick = HTMLAnchorElement.prototype.click;
        HTMLAnchorElement.prototype.click = function () {};
        try {
            fireEvent.click(screen.getByRole('button', { name: /download \.rsc/i }));
        } finally {
            HTMLAnchorElement.prototype.click = realClick;
        }
        const blob = URL.createObjectURL.mock.calls[0][0];
        expect(blob.type).toBe('application/octet-stream');
    });
});

describe('reuse versus rotate', () => {
    it('the default click does NOT rotate, so an earlier download stays valid', async () => {
        await openModal();
        generate();
        await screen.findByTestId('script-body');
        const [, , cfg] = scriptCalls()[0];
        expect(cfg.params.rotate).toBe(false);
    });

    it('rotating is a separate, explicit click', async () => {
        await openModal();
        await generateRotating();
        await screen.findByTestId('script-body');
        const [, , cfg] = scriptCalls()[0];
        expect(cfg.params.rotate).toBe(true);
    });

    it('passes a real boolean, never the click event', async () => {
        // onClick hands the event in as the first argument, so a bare
        // onClick={handleGenerateScript} would make rotate truthy every time.
        await openModal();
        generate();
        await screen.findByTestId('script-body');
        const [, , cfg] = scriptCalls()[0];
        expect(typeof cfg.params.rotate).toBe('boolean');
    });

    it('shows the admin password and says when it actually applies', async () => {
        // It is always returned now; the SCRIPT decides whether to apply it,
        // because only the router can tell a factory reset from a configured
        // box. The UI has to say so, or the value reads as a promise it is not.
        await openModal();
        generate();
        await screen.findByTestId('script-body');
        expect(screen.getByTestId('recovery-password').textContent).toBe(RESULT.recovery_password);
        expect(screen.getByText(/only if this router is new or factory-reset/i)).toBeTruthy();
        // admin is the operator's; the UI must say NetGuard never sets it.
        expect(screen.getByText(/never set by NetGuard/i)).toBeTruthy();
    });
});

describe('rotation is the exceptional action, not the easy one', () => {
    // A real operator clicked "Generate NEW credentials" three times in a row
    // believing it was the ordinary way to get a script. Each click invalidated
    // the file from the click before. The two buttons sat side by side, the
    // destructive one carried no confirmation, and the safe one did.
    it('does not rotate on the first click of the rotate control', async () => {
        await openModal();
        fireEvent.click(screen.getByRole('button', { name: /replace the password/i }));
        expect(scriptCalls()).toHaveLength(0);
    });

    it('asks what rotation will break before doing it', async () => {
        await openModal();
        fireEvent.click(screen.getByRole('button', { name: /replace the password/i }));
        const warn = await screen.findByTestId('rotate-confirm');
        expect(warn.textContent).toMatch(/earlier|previous|stop working|no longer/i);
    });

    it('rotates only on the second, explicit confirmation', async () => {
        await openModal();
        fireEvent.click(screen.getByRole('button', { name: /replace the password/i }));
        await screen.findByTestId('rotate-confirm');
        fireEvent.click(screen.getByRole('button', { name: /yes, replace it/i }));
        await screen.findByTestId('script-body');
        const [, , cfg] = scriptCalls()[0];
        expect(cfg.params.rotate).toBe(true);
    });

    it('the safe path is still a single click', async () => {
        await openModal();
        generate();
        await screen.findByTestId('script-body');
        const [, , cfg] = scriptCalls()[0];
        expect(cfg.params.rotate).toBe(false);
    });

    it('rotation can be backed out of', async () => {
        await openModal();
        fireEvent.click(screen.getByRole('button', { name: /replace the password/i }));
        await screen.findByTestId('rotate-confirm');
        fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
        expect(screen.queryByTestId('rotate-confirm')).toBeNull();
        expect(scriptCalls()).toHaveLength(0);
    });
});

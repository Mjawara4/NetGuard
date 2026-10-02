/**
 * Why a device reads N/A.
 *
 * On a real install every API-sourced field (CPU, memory, uptime, linked
 * clients) showed N/A while the router pinged fine. The cause was that the
 * `netguard` password on the router and the one NetGuard stored had drifted
 * apart, so the API login was rejected -- but nothing in the UI said so, and
 * N/A reads identically to "router is offline" and to "never polled".
 *
 * The metrics are already fetched; `api_reachable` sits alongside cpu_usage in
 * the same response. These tests pin that the card explains itself.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
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

const DEVICE = { id: 'dev-1', name: 'Counter Router', ip_address: '10.13.13.3', device_type: 'router', is_active: true, site_id: 's1' };

const metric = (type, value, meta) => ({ metric_type: type, value, meta_data: meta || {}, time: '2026-10-02T03:00:00Z' });

function mountWith(metrics) {
    api.get.mockImplementation((url) => {
        if (url.includes('/monitoring/metrics/latest')) return Promise.resolve({ data: metrics });
        if (url.includes('/inventory/devices')) return Promise.resolve({ data: [DEVICE] });
        return Promise.resolve({ data: [] });
    });
    render(<MemoryRouter><Devices /></MemoryRouter>);
}

async function openDevice() {
    fireEvent.click((await screen.findAllByText('Counter Router'))[0]);
}

beforeEach(() => {
    vi.clearAllMocks();
    api.post.mockResolvedValue({ data: {} });
});

describe('explaining an unreachable API', () => {
    it('says the credentials do not match when the router answers but the API login fails', async () => {
        mountWith([metric('status', 1), metric('latency', 33.1), metric('api_reachable', 0)]);
        await openDevice();
        const note = await screen.findByTestId('api-credential-mismatch');
        expect(note.textContent).toMatch(/password/i);
        // It must name the remedy, not just the symptom.
        expect(note.textContent).toMatch(/setup script/i);
    });

    it('does not blame credentials when the router itself is down', async () => {
        mountWith([metric('status', 0), metric('api_reachable', 0)]);
        await openDevice();
        expect(screen.queryByTestId('api-credential-mismatch')).toBeNull();
        expect((await screen.findByTestId('api-offline')).textContent).toMatch(/offline|unreachable|not responding/i);
    });

    it('stays quiet when the API is working', async () => {
        mountWith([metric('status', 1), metric('api_reachable', 1), metric('cpu_usage', 4.2)]);
        await openDevice();
        expect(screen.queryByTestId('api-credential-mismatch')).toBeNull();
        expect(screen.queryByTestId('api-offline')).toBeNull();
    });

    it('stays quiet when the API has never been polled', async () => {
        // No api_reachable metric at all: a brand-new device, not a broken one.
        mountWith([metric('status', 1)]);
        await openDevice();
        expect(screen.queryByTestId('api-credential-mismatch')).toBeNull();
        expect(screen.queryByTestId('api-offline')).toBeNull();
    });

    it('treats a missing status metric as reachable rather than guessing offline', async () => {
        // ICMP may not have been recorded yet while the API has. Attributing the
        // failure to the router being down would send the installer after a
        // cable when the real cause is the password.
        mountWith([metric('api_reachable', 0)]);
        await openDevice();
        expect(await screen.findByTestId('api-credential-mismatch')).toBeTruthy();
    });
});

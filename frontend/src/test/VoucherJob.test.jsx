import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import React from 'react';

// Background voucher-generation job polling (Task 5).
//
// The batch endpoint now returns 202 + { job_id, status, count } instead of
// the generated vouchers, and progress is polled from GET /hotspot/jobs/{id}.
// These tests cover: submitting the form stores the job id, progress renders
// (and keeps updating on the poll interval) while the job runs, a completed
// job's vouchers reach the print view unchanged, a failed job still
// surfaces whatever partial vouchers it produced, resuming an in-flight job
// found in localStorage on mount (the screen-lock/reload regression guard),
// and the History tab rendering from GET /batches instead of the /users
// cache.
vi.mock('../api', () => ({
    default: {
        get: vi.fn(() => Promise.resolve({ data: [] })),
        post: vi.fn(() => Promise.resolve({ data: {} })),
        put: vi.fn(() => Promise.resolve({ data: {} })),
        delete: vi.fn(() => Promise.resolve({ data: {} })),
    },
}));

import api from '../api';
import Hotspot from '../pages/Hotspot/index.jsx';

const DEVICE_ID = 'device-1';
const JOB_KEY = `hotspot_voucher_job_${DEVICE_ID}`;

const DEVICES_RESPONSE = [
    { id: DEVICE_ID, name: 'Core Router', ip_address: '10.0.0.1', device_type: 'router' },
];

// Everything prefetchAll/fetchData asks for on mount, shaped just enough
// that nothing throws. Individual tests layer job/batches responses on top.
function installDefaultApiMocks({ jobs = {}, batches = [] } = {}) {
    api.get.mockImplementation((url) => {
        if (url.includes('/inventory/devices')) {
            return Promise.resolve({ data: DEVICES_RESPONSE });
        }
        const jobMatch = url.match(/\/hotspot\/jobs\/([^/?]+)/);
        if (jobMatch) {
            const job = jobs[jobMatch[1]];
            return Promise.resolve({ data: job || { job_id: jobMatch[1], status: 'queued', count: 0, created: 0, vouchers: [] } });
        }
        if (url.includes('/batches')) {
            return Promise.resolve({ data: batches });
        }
        if (url.includes('/summary')) {
            return Promise.resolve({ data: { active_count: 0, total_vouchers: 0, total_data_mb: 0, profile_distribution: [], stale: false } });
        }
        if (url.includes('/system-info')) {
            return Promise.resolve({ data: { cpu_load: 1, free_memory: 100, total_memory: 200, uptime: '1h' } });
        }
        if (url.includes('/voucher-template')) {
            return Promise.resolve({ data: null });
        }
        if (url.includes('/reports')) {
            return Promise.resolve({ data: { data: [] } });
        }
        // /users, /active, /profiles, /logs all just need an array.
        return Promise.resolve({ data: [] });
    });
    api.post.mockImplementation(() => Promise.resolve({ data: {} }));
}

async function renderHotspotOnDevice() {
    const utils = render(<Hotspot />);
    await waitFor(() => {
        expect(api.get).toHaveBeenCalledWith(expect.stringContaining(`/hotspot/${DEVICE_ID}/summary`));
    });
    return utils;
}

function goToGenerator() {
    fireEvent.click(screen.getByRole('button', { name: /Generator/i }));
}

function goToHistory() {
    fireEvent.click(screen.getByRole('button', { name: /Batches/i }));
}

// The Print Preview overlay and the hidden (print-only) area both render
// every voucher, so a plain getByText legitimately matches twice -- assert
// against however many matches exist rather than assuming there is one.
function expectVoucherRendered(username) {
    expect(screen.getAllByText(username).length).toBeGreaterThan(0);
}

describe('Voucher generation background job', () => {
    beforeEach(() => {
        vi.resetAllMocks();
        localStorage.clear();
        installDefaultApiMocks();
    });

    it('stores the returned job_id in localStorage under a device-scoped key on submit', async () => {
        api.post.mockImplementation(() => Promise.resolve({ data: { job_id: 'job-store', status: 'queued', count: 10 } }));

        await renderHotspotOnDevice();
        goToGenerator();

        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: /Generate Hotspot Vouchers/i }));
        });

        await waitFor(() => {
            expect(localStorage.getItem(JOB_KEY)).toBe('job-store');
        });
    });

    it('renders progress ("N / count") while running, and keeps updating on the poll interval', async () => {
        await renderHotspotOnDevice();
        goToGenerator();

        // Mutable so the mocked GET reflects new progress once the poll
        // interval ticks again, without re-registering the mock.
        const jobState = { job_id: 'job-poll', status: 'running', count: 100, created: 10, vouchers: [] };
        api.get.mockImplementation((url) => {
            if (url.includes('/hotspot/jobs/job-poll')) return Promise.resolve({ data: { ...jobState } });
            if (url.includes('/inventory/devices')) return Promise.resolve({ data: DEVICES_RESPONSE });
            if (url.includes('/batches')) return Promise.resolve({ data: [] });
            if (url.includes('/summary')) return Promise.resolve({ data: { active_count: 0, total_vouchers: 0, total_data_mb: 0, profile_distribution: [], stale: false } });
            if (url.includes('/system-info')) return Promise.resolve({ data: { cpu_load: 1, free_memory: 100, total_memory: 200, uptime: '1h' } });
            if (url.includes('/voucher-template')) return Promise.resolve({ data: null });
            if (url.includes('/reports')) return Promise.resolve({ data: { data: [] } });
            return Promise.resolve({ data: [] });
        });
        api.post.mockImplementation(() => Promise.resolve({ data: { job_id: 'job-poll', status: 'queued', count: 100 } }));

        vi.useFakeTimers();
        try {
            fireEvent.click(screen.getByRole('button', { name: /Generate Hotspot Vouchers/i }));

            // The submit POST and the poll's first (immediate) GET are both
            // microtask-resolved promises, not timers -- advancing by 0ms
            // under the async fake-timer API drains them in lockstep.
            await act(async () => {
                await vi.advanceTimersByTimeAsync(0);
            });
            expect(screen.getByText((_, node) => node?.textContent === '10 / 100')).toBeInTheDocument();

            // The router/worker made more progress server-side; advancing past
            // one interval tick should pick it up without any user action.
            jobState.created = 43;
            await act(async () => {
                await vi.advanceTimersByTimeAsync(3000);
            });
            expect(screen.getByText((_, node) => node?.textContent === '43 / 100')).toBeInTheDocument();
        } finally {
            vi.useRealTimers();
        }
    });

    it('on complete, renders the job vouchers ready to print', async () => {
        const vouchers = [
            { username: 'user01', password: 'pass01' },
            { username: 'user02', password: 'pass02' },
        ];
        installDefaultApiMocks({
            jobs: { 'job-done': { job_id: 'job-done', status: 'complete', count: 2, created: 2, vouchers } },
        });
        api.post.mockImplementation(() => Promise.resolve({ data: { job_id: 'job-done', status: 'queued', count: 2 } }));

        await renderHotspotOnDevice();
        goToGenerator();

        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: /Generate Hotspot Vouchers/i }));
        });

        await waitFor(() => {
            expect(screen.getByText('Ready to export 2 vouchers')).toBeInTheDocument();
        });
        expectVoucherRendered('user01');
        expectVoucherRendered('user02');
        // Terminal state shown to the operator -- the stored job id is cleared.
        expect(localStorage.getItem(JOB_KEY)).toBeNull();
    });

    it('REGRESSION GUARD: resumes polling a job_id already in localStorage on mount (screen-lock / reload safety)', async () => {
        localStorage.setItem(JOB_KEY, 'job-resume');
        installDefaultApiMocks({
            jobs: { 'job-resume': { job_id: 'job-resume', status: 'running', count: 50, created: 12, vouchers: [] } },
        });

        await renderHotspotOnDevice();

        // The component must poll the resumed job on its own -- no form
        // submission happens in this test.
        await waitFor(() => {
            expect(api.get).toHaveBeenCalledWith(expect.stringContaining('/hotspot/jobs/job-resume'));
        });

        goToGenerator();

        await waitFor(() => {
            expect(screen.getByText((_, node) => node?.textContent === '12 / 50')).toBeInTheDocument();
        });
    });

    it('a failed job renders its partial vouchers rather than discarding them', async () => {
        const vouchers = [
            { username: 'part01', password: 'pw1' },
            { username: 'part02', password: 'pw2' },
        ];
        installDefaultApiMocks({
            jobs: { 'job-failed': { job_id: 'job-failed', status: 'failed', count: 10, created: 2, vouchers } },
        });
        api.post.mockImplementation(() => Promise.resolve({ data: { job_id: 'job-failed', status: 'queued', count: 10 } }));

        await renderHotspotOnDevice();
        goToGenerator();

        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: /Generate Hotspot Vouchers/i }));
        });

        await waitFor(() => {
            expect(screen.getAllByText('part01').length).toBeGreaterThan(0);
        });
        expectVoucherRendered('part02');
        // Honest short/failed disclosure: 2 of the 10 requested actually exist.
        expect(screen.getByText((_, node) => node?.textContent === '2 / 10 created before job failed')).toBeInTheDocument();
        expect(localStorage.getItem(JOB_KEY)).toBeNull();
    });

    it('the History tab fetches and renders batches from GET /batches', async () => {
        installDefaultApiMocks({
            batches: [
                {
                    id: 'batch-1',
                    name: 'Batch-user | 2026-01-01 10:00:00',
                    displayName: 'user',
                    count: 5,
                    profile: 'default',
                    timeLimit: '1h',
                    date: '2026-01-01 10:00',
                    status: 'complete',
                    vouchers: [{ username: 'h1', password: 'p1' }],
                    data: [{ username: 'h1', password: 'p1' }],
                },
                {
                    id: 'batch-legacy',
                    name: 'Batch-legacy | 2025-01-01 09:00:00',
                    displayName: 'legacy',
                    count: 3,
                    profile: 'default',
                    timeLimit: '',
                    date: '2025-01-01 09:00',
                    status: null,
                    vouchers: [{ username: 'l1', password: 'p1' }],
                    data: [{ username: 'l1', password: 'p1' }],
                },
            ],
        });

        await renderHotspotOnDevice();
        goToHistory();

        await waitFor(() => {
            expect(api.get).toHaveBeenCalledWith(expect.stringContaining(`/hotspot/${DEVICE_ID}/batches`));
        });

        await waitFor(() => {
            expect(screen.getByText('user')).toBeInTheDocument();
        });
        expect(screen.getByText('legacy')).toBeInTheDocument();
        // New row shows its status; legacy row (status: null) renders with no badge.
        expect(screen.getByText('complete')).toBeInTheDocument();
    });
});

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act, within } from '@testing-library/react';
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
    fireEvent.click(screen.getByRole('button', { name: /Books/i }));
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
            fireEvent.click(screen.getByRole('button', { name: /Print \d+ vouchers/i }));
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
            fireEvent.click(screen.getByRole('button', { name: /Print \d+ vouchers/i }));

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
            fireEvent.click(screen.getByRole('button', { name: /Print \d+ vouchers/i }));
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

    it('CRITICAL: a stale job_id that 404s clears the job, stops polling, and re-enables Generate', async () => {
        localStorage.setItem(JOB_KEY, 'job-stale');
        let jobPollCount = 0;
        api.get.mockImplementation((url) => {
            if (url.includes('/hotspot/jobs/job-stale')) {
                jobPollCount += 1;
                return Promise.reject({ response: { status: 404, data: { detail: 'Job not found' } } });
            }
            if (url.includes('/inventory/devices')) return Promise.resolve({ data: DEVICES_RESPONSE });
            if (url.includes('/batches')) return Promise.resolve({ data: [] });
            if (url.includes('/summary')) return Promise.resolve({ data: { active_count: 0, total_vouchers: 0, total_data_mb: 0, profile_distribution: [], stale: false } });
            if (url.includes('/system-info')) return Promise.resolve({ data: { cpu_load: 1, free_memory: 100, total_memory: 200, uptime: '1h' } });
            if (url.includes('/voucher-template')) return Promise.resolve({ data: null });
            if (url.includes('/reports')) return Promise.resolve({ data: { data: [] } });
            return Promise.resolve({ data: [] });
        });
        // jsdom's window.alert throws "not implemented" unless stubbed; the
        // fix reuses alert() as its operator-facing message, so stub it here
        // the same way a real browser would just show it.
        const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});

        await renderHotspotOnDevice();

        // A single 404 is treated as "this job is confirmed gone" -- cleared
        // immediately, no need to tolerate repeated failures first.
        await waitFor(() => {
            expect(localStorage.getItem(JOB_KEY)).toBeNull();
        });
        expect(alertSpy).toHaveBeenCalled();

        goToGenerator();
        await waitFor(() => {
            expect(screen.getByRole('button', { name: /Print \d+ vouchers/i })).not.toBeDisabled();
        });

        // The interval must actually be stopped, not just the state cleared --
        // give it well past one 3s tick and confirm no further polling happened.
        const pollsAtClear = jobPollCount;
        await new Promise((resolve) => setTimeout(resolve, 50));
        expect(jobPollCount).toBe(pollsAtClear);

        alertSpy.mockRestore();
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
            fireEvent.click(screen.getByRole('button', { name: /Print \d+ vouchers/i }));
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
        // New row shows its status badge...
        expect(screen.getByText('complete')).toBeInTheDocument();
        // ...but the legacy row (status: null -- there are 21 of these in
        // production) renders with NO badge at all, same as before this
        // feature existed. Scope the check to that row's own name block
        // (badge and displayName are siblings there) so a badge elsewhere
        // on the page can't make this pass by accident.
        const legacyNameBlock = screen.getByText('legacy').parentElement;
        expect(within(legacyNameBlock).queryByText(/complete|failed|running|queued/i)).not.toBeInTheDocument();
        expect(legacyNameBlock.querySelector('span')).toBeNull();
    });
});

// ---------------------------------------------------------------------------
// C1 -- a job stuck at "running"/"queued" forever returns HTTP 200 on every
// poll, so neither the 404 path nor the transient-failure-counter path above
// ever fires. The stall timeout (VOUCHER_JOB_STALL_MS, 3 minutes in
// index.jsx) and the manual Dismiss control are the two independent escapes
// for that case.
// ---------------------------------------------------------------------------
describe('C1: stuck-job stall detection and manual dismiss', () => {
    beforeEach(() => {
        vi.resetAllMocks();
        localStorage.clear();
        installDefaultApiMocks();
    });

    // The stall check only looks at `created`, so `status` can stay
    // "running" (or "queued") throughout every poll in these tests -- the
    // job never reports a terminal state or an error, exactly like the real
    // bug (worker gone, backend unreachable at the last report, or simply
    // not running).
    function installStuckJobMocks(jobId, { created = 12, count = 50 } = {}) {
        api.get.mockImplementation((url) => {
            if (url.includes(`/hotspot/jobs/${jobId}`)) {
                return Promise.resolve({ data: { job_id: jobId, status: 'running', count, created, vouchers: [] } });
            }
            if (url.includes('/inventory/devices')) return Promise.resolve({ data: DEVICES_RESPONSE });
            if (url.includes('/batches')) return Promise.resolve({ data: [] });
            if (url.includes('/summary')) return Promise.resolve({ data: { active_count: 0, total_vouchers: 0, total_data_mb: 0, profile_distribution: [], stale: false } });
            if (url.includes('/system-info')) return Promise.resolve({ data: { cpu_load: 1, free_memory: 100, total_memory: 200, uptime: '1h' } });
            if (url.includes('/voucher-template')) return Promise.resolve({ data: null });
            if (url.includes('/reports')) return Promise.resolve({ data: { data: [] } });
            return Promise.resolve({ data: [] });
        });
    }

    // Flush chained promise -> setState -> effect -> promise cycles under
    // fake timers (fetchDevices -> setSelectedDevice -> prefetchAll +
    // resume-job effect, each themselves awaiting mocked axios calls). A
    // single advanceTimersByTimeAsync(0) only drains one microtask round;
    // a handful of repeats settles the whole mount chain without needing any
    // real wall-clock time to pass.
    async function flushMicrotasks(rounds = 6) {
        for (let i = 0; i < rounds; i++) {
            // eslint-disable-next-line no-await-in-loop
            await act(async () => {
                await vi.advanceTimersByTimeAsync(0);
            });
        }
    }

    it('CRITICAL: a job stuck "running" with unchanging created is abandoned after the stall timeout -- polling stops, the stored id is cleared, and Generate re-enables', async () => {
        localStorage.setItem(JOB_KEY, 'job-stuck');
        installStuckJobMocks('job-stuck', { created: 12, count: 50 });
        const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});

        vi.useFakeTimers();
        try {
            render(<Hotspot />);
            await flushMicrotasks();
            // Resumed on mount, same as the reload/screen-lock regression guard.
            expect(localStorage.getItem(JOB_KEY)).toBe('job-stuck');

            const pollsBeforeStall = api.get.mock.calls.filter(([url]) => url.includes('/hotspot/jobs/job-stuck')).length;
            expect(pollsBeforeStall).toBeGreaterThan(0);

            // `created` never advances on any subsequent tick. Fast-forward
            // well past the 3-minute stall timeout.
            await act(async () => {
                await vi.advanceTimersByTimeAsync(3 * 60 * 1000 + 15000);
            });

            expect(localStorage.getItem(JOB_KEY)).toBeNull();
            expect(alertSpy).toHaveBeenCalled();

            // Polling actually stopped, not just the state cleared: no more
            // calls after one further interval tick.
            const pollsAtGiveUp = api.get.mock.calls.filter(([url]) => url.includes('/hotspot/jobs/job-stuck')).length;
            await act(async () => {
                await vi.advanceTimersByTimeAsync(5000);
            });
            expect(api.get.mock.calls.filter(([url]) => url.includes('/hotspot/jobs/job-stuck')).length).toBe(pollsAtGiveUp);

            fireEvent.click(screen.getByRole('button', { name: /Generator/i }));
            expect(screen.getByRole('button', { name: /Print \d+ vouchers/i })).not.toBeDisabled();
        } finally {
            vi.useRealTimers();
            alertSpy.mockRestore();
        }
    });

    it('a job that IS progressing must NOT be abandoned, even well past the stall timeout wall-clock duration', async () => {
        localStorage.setItem(JOB_KEY, 'job-healthy');
        let pollCount = 0;
        api.get.mockImplementation((url) => {
            if (url.includes('/hotspot/jobs/job-healthy')) {
                // `created` advances on every single poll -- this job is
                // healthy and must survive indefinitely regardless of how
                // much wall-clock time the stall timeout would otherwise
                // allow.
                pollCount += 1;
                return Promise.resolve({ data: { job_id: 'job-healthy', status: 'running', count: 1000, created: pollCount, vouchers: [] } });
            }
            if (url.includes('/inventory/devices')) return Promise.resolve({ data: DEVICES_RESPONSE });
            if (url.includes('/batches')) return Promise.resolve({ data: [] });
            if (url.includes('/summary')) return Promise.resolve({ data: { active_count: 0, total_vouchers: 0, total_data_mb: 0, profile_distribution: [], stale: false } });
            if (url.includes('/system-info')) return Promise.resolve({ data: { cpu_load: 1, free_memory: 100, total_memory: 200, uptime: '1h' } });
            if (url.includes('/voucher-template')) return Promise.resolve({ data: null });
            if (url.includes('/reports')) return Promise.resolve({ data: { data: [] } });
            return Promise.resolve({ data: [] });
        });
        const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});

        vi.useFakeTimers();
        try {
            render(<Hotspot />);
            await flushMicrotasks();
            expect(localStorage.getItem(JOB_KEY)).toBe('job-healthy');

            // Same fast-forward as the stuck-job test above -- well past the
            // 3-minute stall timeout -- but this job keeps making progress on
            // every tick, so it must still be tracked afterward.
            await act(async () => {
                await vi.advanceTimersByTimeAsync(3 * 60 * 1000 + 15000);
            });

            expect(localStorage.getItem(JOB_KEY)).toBe('job-healthy');
            expect(alertSpy).not.toHaveBeenCalled();

            fireEvent.click(screen.getByRole('button', { name: /Generator/i }));
            // Still running, so the submit button reads "Printing…" rather
            // than its idle label -- match either so this doesn't hinge on
            // which one is showing, only on it being disabled.
            expect(screen.getByRole('button', { name: /Print \d+ vouchers|Printing/i })).toBeDisabled();
        } finally {
            vi.useRealTimers();
            alertSpy.mockRestore();
        }
    });

    it('a queued job that stays queued well past the stall timeout must NOT be abandoned (single-worker queue depth is normal, not a stall)', async () => {
        localStorage.setItem(JOB_KEY, 'job-queued-behind-a-big-one');
        api.get.mockImplementation((url) => {
            if (url.includes('/hotspot/jobs/job-queued-behind-a-big-one')) {
                // Never leaves "queued" -- there is a single voucher-worker
                // and qty is unbounded, so a large job ahead of this one in
                // the queue can legitimately hold it here for minutes.
                // `created` stays 0 throughout, which looks identical to a
                // genuinely stuck job from this response shape alone -- that
                // is exactly why "queued" must never count toward the stall
                // timeout (see Fix 1 above the stall check in index.jsx).
                return Promise.resolve({ data: { job_id: 'job-queued-behind-a-big-one', status: 'queued', count: 500, created: 0, vouchers: [] } });
            }
            if (url.includes('/inventory/devices')) return Promise.resolve({ data: DEVICES_RESPONSE });
            if (url.includes('/batches')) return Promise.resolve({ data: [] });
            if (url.includes('/summary')) return Promise.resolve({ data: { active_count: 0, total_vouchers: 0, total_data_mb: 0, profile_distribution: [], stale: false } });
            if (url.includes('/system-info')) return Promise.resolve({ data: { cpu_load: 1, free_memory: 100, total_memory: 200, uptime: '1h' } });
            if (url.includes('/voucher-template')) return Promise.resolve({ data: null });
            if (url.includes('/reports')) return Promise.resolve({ data: { data: [] } });
            return Promise.resolve({ data: [] });
        });
        const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});

        vi.useFakeTimers();
        try {
            render(<Hotspot />);
            await flushMicrotasks();
            expect(localStorage.getItem(JOB_KEY)).toBe('job-queued-behind-a-big-one');

            // Well past the stall timeout, and still "queued" (created: 0)
            // on every single tick the entire time.
            await act(async () => {
                await vi.advanceTimersByTimeAsync(3 * 60 * 1000 + 30000);
            });

            expect(localStorage.getItem(JOB_KEY)).toBe('job-queued-behind-a-big-one');
            expect(alertSpy).not.toHaveBeenCalled();
        } finally {
            vi.useRealTimers();
            alertSpy.mockRestore();
        }
    });

    it('a running job whose created is flat for a gap shorter than the stall timeout must NOT be abandoned', async () => {
        localStorage.setItem(JOB_KEY, 'job-brief-pause');
        api.get.mockImplementation((url) => {
            if (url.includes('/hotspot/jobs/job-brief-pause')) {
                // `created` never changes across this whole test -- unlike
                // the "IS progressing" test above (which advances `created`
                // on every tick and so would pass regardless of the stall
                // constant's value), this is the genuinely sensitive case:
                // a real pause with no progress, held for a duration shorter
                // than VOUCHER_JOB_STALL_MS. It must survive.
                return Promise.resolve({ data: { job_id: 'job-brief-pause', status: 'running', count: 200, created: 40, vouchers: [] } });
            }
            if (url.includes('/inventory/devices')) return Promise.resolve({ data: DEVICES_RESPONSE });
            if (url.includes('/batches')) return Promise.resolve({ data: [] });
            if (url.includes('/summary')) return Promise.resolve({ data: { active_count: 0, total_vouchers: 0, total_data_mb: 0, profile_distribution: [], stale: false } });
            if (url.includes('/system-info')) return Promise.resolve({ data: { cpu_load: 1, free_memory: 100, total_memory: 200, uptime: '1h' } });
            if (url.includes('/voucher-template')) return Promise.resolve({ data: null });
            if (url.includes('/reports')) return Promise.resolve({ data: { data: [] } });
            return Promise.resolve({ data: [] });
        });
        const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});

        vi.useFakeTimers();
        try {
            render(<Hotspot />);
            await flushMicrotasks();
            expect(localStorage.getItem(JOB_KEY)).toBe('job-brief-pause');

            // A 2:50 flat gap -- shorter than the 3-minute timeout -- must
            // survive. (This is the test that actually catches an
            // over-aggressive constant: with `created` genuinely flat the
            // whole time, lowering VOUCHER_JOB_STALL_MS below this gap makes
            // this fail -- see the report for the deliberate-lowering check.)
            await act(async () => {
                await vi.advanceTimersByTimeAsync(3 * 60 * 1000 - 10000);
            });

            expect(localStorage.getItem(JOB_KEY)).toBe('job-brief-pause');
            expect(alertSpy).not.toHaveBeenCalled();
        } finally {
            vi.useRealTimers();
            alertSpy.mockRestore();
        }
    });

    it('CRITICAL: the manual Dismiss control clears local job state and re-enables Generate, without attempting to cancel anything server-side', async () => {
        installDefaultApiMocks({
            jobs: { 'job-dismiss': { job_id: 'job-dismiss', status: 'running', count: 20, created: 3, vouchers: [] } },
        });
        api.post.mockImplementation(() => Promise.resolve({ data: { job_id: 'job-dismiss', status: 'queued', count: 20 } }));

        await renderHotspotOnDevice();
        goToGenerator();

        vi.useFakeTimers();
        try {
            fireEvent.click(screen.getByRole('button', { name: /Print \d+ vouchers/i }));
            await act(async () => {
                await vi.advanceTimersByTimeAsync(0);
            });

            expect(localStorage.getItem(JOB_KEY)).toBe('job-dismiss');
            const dismissButton = screen.getByRole('button', { name: /dismiss/i });

            fireEvent.click(dismissButton);

            expect(localStorage.getItem(JOB_KEY)).toBeNull();
            expect(screen.getByRole('button', { name: /Print \d+ vouchers/i })).not.toBeDisabled();
            // The progress panel (and its Dismiss button) is gone along with it.
            expect(screen.queryByRole('button', { name: /dismiss/i })).not.toBeInTheDocument();

            // Purely local: polling must actually have stopped, not just the
            // visible state -- no further /jobs/job-dismiss calls survive
            // one more interval tick. (No DELETE/cancel call of any kind is
            // ever made -- api.delete is never invoked by this flow either.)
            const pollsAtDismiss = api.get.mock.calls.filter(([url]) => url.includes('/hotspot/jobs/job-dismiss')).length;
            await act(async () => {
                await vi.advanceTimersByTimeAsync(5000);
            });
            expect(api.get.mock.calls.filter(([url]) => url.includes('/hotspot/jobs/job-dismiss')).length).toBe(pollsAtDismiss);
            expect(api.delete).not.toHaveBeenCalled();
        } finally {
            vi.useRealTimers();
        }
    });
});

// ---------------------------------------------------------------------------
// C2 -- version-skew during deploy in both directions.
// ---------------------------------------------------------------------------
describe('C2: version-skew safety (array legacy response, non-array generatedBatch)', () => {
    beforeEach(() => {
        vi.resetAllMocks();
        localStorage.clear();
        installDefaultApiMocks();
    });

    it('CRITICAL: an array POST response (new frontend / old backend) is handled as the legacy synchronous result -- vouchers render, no job id stored, no polling', async () => {
        const legacyVouchers = [
            { username: 'legacy01', password: 'pw1' },
            { username: 'legacy02', password: 'pw2' },
        ];
        api.post.mockImplementation(() => Promise.resolve({ data: legacyVouchers }));

        await renderHotspotOnDevice();
        goToGenerator();

        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: /Print \d+ vouchers/i }));
        });

        await waitFor(() => {
            expect(screen.getByText('Ready to export 2 vouchers')).toBeInTheDocument();
        });
        expectVoucherRendered('legacy01');
        expectVoucherRendered('legacy02');

        // No job was ever created for this response, so nothing must be
        // stored or polled -- the bug this guards against is storing the
        // literal string "undefined" and polling "/hotspot/jobs/undefined".
        expect(localStorage.getItem(JOB_KEY)).toBeNull();
        expect(api.get.mock.calls.some(([url]) => url.includes('/hotspot/jobs/'))).toBe(false);
    });

    it('CRITICAL: a non-array generatedBatch (e.g. a malformed job vouchers field) renders empty instead of throwing', async () => {
        installDefaultApiMocks({
            jobs: { 'job-bad-shape': { job_id: 'job-bad-shape', status: 'complete', count: 2, created: 2, vouchers: { not: 'an array' } } },
        });
        api.post.mockImplementation(() => Promise.resolve({ data: { job_id: 'job-bad-shape', status: 'queued', count: 2 } }));

        await renderHotspotOnDevice();
        goToGenerator();

        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: /Print \d+ vouchers/i }));
        });

        // Renders as an empty batch instead of crashing on
        // "generatedBatch.map is not a function".
        await waitFor(() => {
            expect(screen.getByText('Ready to export 0 vouchers')).toBeInTheDocument();
        });
    });
});

// ---------------------------------------------------------------------------
// I3 -- an enqueue failure (status: "failed" + detail, from a 202 response,
// not an HTTP error) must surface the detail and never start polling.
// ---------------------------------------------------------------------------
describe('I3: enqueue-failure detail surfaced, no polling started', () => {
    beforeEach(() => {
        vi.resetAllMocks();
        localStorage.clear();
        installDefaultApiMocks();
    });

    it('a failed-enqueue POST response surfaces detail and does not poll', async () => {
        api.post.mockImplementation(() => Promise.resolve({
            data: {
                job_id: 'job-enqueue-failed',
                status: 'failed',
                count: 10,
                detail: 'Voucher batch was recorded but could not be queued for generation. Retry later.',
            },
        }));
        const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});

        await renderHotspotOnDevice();
        goToGenerator();

        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: /Print \d+ vouchers/i }));
        });

        expect(alertSpy).toHaveBeenCalledWith(expect.stringContaining('could not be queued'));
        expect(localStorage.getItem(JOB_KEY)).toBeNull();
        expect(api.get.mock.calls.some(([url]) => url.includes('/hotspot/jobs/'))).toBe(false);
        // No misleading empty print view ("Ready to export 0 vouchers").
        expect(screen.queryByText(/Ready to export/)).not.toBeInTheDocument();

        alertSpy.mockRestore();
    });
});

// ---------------------------------------------------------------------------
// I2 -- the transient-failure threshold was raised from 3 (~9s) to 10
// (~30s) because a backend restart during a deploy can easily take that
// long, and 9s was shorter than that. This proves the new threshold is
// actually in effect: fewer than 10 consecutive transient failures must NOT
// abandon a healthy job, and the reset-on-success behavior still works.
// ---------------------------------------------------------------------------
describe('I2: raised transient-failure threshold (~10 misses / ~30s)', () => {
    beforeEach(() => {
        vi.resetAllMocks();
        localStorage.clear();
        installDefaultApiMocks();
    });

    it('tolerates 9 consecutive transient (non-404) poll failures without abandoning the job, then recovers on success', async () => {
        localStorage.setItem(JOB_KEY, 'job-blip');
        let jobPollAttempt = 0;
        api.get.mockImplementation((url) => {
            if (url.includes('/hotspot/jobs/job-blip')) {
                jobPollAttempt += 1;
                if (jobPollAttempt <= 9) {
                    return Promise.reject(new Error('network blip'));
                }
                return Promise.resolve({ data: { job_id: 'job-blip', status: 'running', count: 20, created: 7, vouchers: [] } });
            }
            if (url.includes('/inventory/devices')) return Promise.resolve({ data: DEVICES_RESPONSE });
            if (url.includes('/batches')) return Promise.resolve({ data: [] });
            if (url.includes('/summary')) return Promise.resolve({ data: { active_count: 0, total_vouchers: 0, total_data_mb: 0, profile_distribution: [], stale: false } });
            if (url.includes('/system-info')) return Promise.resolve({ data: { cpu_load: 1, free_memory: 100, total_memory: 200, uptime: '1h' } });
            if (url.includes('/voucher-template')) return Promise.resolve({ data: null });
            if (url.includes('/reports')) return Promise.resolve({ data: { data: [] } });
            return Promise.resolve({ data: [] });
        });
        const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});

        vi.useFakeTimers();
        try {
            render(<Hotspot />);
            // Drive 9 failed ticks (immediate + 8 interval ticks) plus the
            // 10th, successful one -- all under one blip that's shorter than
            // the new threshold.
            for (let i = 0; i < 10; i++) {
                // eslint-disable-next-line no-await-in-loop
                await act(async () => {
                    await vi.advanceTimersByTimeAsync(3000);
                });
            }

            expect(localStorage.getItem(JOB_KEY)).toBe('job-blip');
            expect(alertSpy).not.toHaveBeenCalled();
            expect(jobPollAttempt).toBeGreaterThanOrEqual(10);
        } finally {
            vi.useRealTimers();
            alertSpy.mockRestore();
        }
    });
});

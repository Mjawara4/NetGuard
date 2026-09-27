import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';

// Every Hotspot tab renders.
//
// Task 6 split a 2,000-line `Hotspot/index.jsx` into seven panel components and
// proved the split with a throwaway test that mounted <Hotspot />, clicked all
// nine tabs and asserted no React error -- then deleted it, to avoid leaving
// uncommitted scope behind. Five of those panels (Vouchers, Active, Profiles,
// Logs, Report) had NO permanent test that they render at all, so a broken prop
// name in any of them would have shipped green: `pages-tokenised.test.jsx` only
// reads their source text, and `VoucherJob.test.jsx` only visits Generator and
// Books.
//
// This is that test, kept. Each tab is mounted fresh and asserted on content
// that only its own panel renders, with a row of real data behind it so an
// empty state cannot stand in for a working table.
vi.mock('../api', () => ({
    default: {
        get: vi.fn(() => Promise.resolve({ data: [] })),
        post: vi.fn(() => Promise.resolve({ data: {} })),
        put: vi.fn(() => Promise.resolve({ data: {} })),
        delete: vi.fn(() => Promise.resolve({ data: {} })),
    },
}));

// SalesForecast (the AI Forecast tab) calls `axios` directly rather than the
// shared `api` client, so it needs its own mock -- otherwise the tab renders
// its "Failed to load forecast data." branch and the chart path, which is what
// the Task 8 hex migration touched, is never exercised.
vi.mock('axios', () => ({
    default: {
        get: vi.fn(() =>
            Promise.resolve({
                data: {
                    forecast: [
                        { date: '2026-09-28', predicted_sales: 400 },
                        { date: '2026-09-29', predicted_sales: 450 },
                    ],
                    trend_analysis: 'Sales are trending up.',
                },
            }),
        ),
    },
}));

import api from '../api';
import Hotspot from '../pages/Hotspot/index.jsx';

const DEVICE_ID = 'device-1';
const DEVICES = [{ id: DEVICE_ID, name: 'Core Router', ip_address: '10.0.0.1', device_type: 'router' }];

const USER_ROW = {
    '.id': '*1',
    name: 'vch-aa11bb',
    password: 'pw-aa11bb',
    profile: 'day-pass',
    comment: 'Batch-VCH | 2026-09-27 14:02',
    'limit-uptime': '1h',
    disabled: 'false',
};
const ACTIVE_ROW = {
    '.id': '*2',
    user: 'vch-cc22dd',
    address: '10.5.50.14',
    'mac-address': 'AA:BB:CC:DD:EE:FF',
    uptime: '12m',
    'session-time-left': '48m',
};
const PROFILE_ROW = {
    '.id': '*3',
    name: 'week',
    'rate-limit': '5M/5M',
    'shared-users': '1',
    price: 100,
    active_users: 2,
};
// `user_info` is required: LogsPanel filters on it unconditionally, and the
// router endpoint always sets it (hotspot.py:1583 defaults it to "system").
const LOG_ROW = {
    time: '14:02:11',
    topics: 'hotspot,info',
    user_info: 'vch-aa11bb',
    message: 'vch-aa11bb logged in',
};
const REPORT_DATA = {
    total_revenue: 1200,
    total_sold: 12,
    daily_stats: [{ date: '2026-09-27', revenue: 1200, count: 12 }],
    profile_stats: [{ profile: 'day-pass', count: 9, revenue: 900 }],
    data: [
        {
            username: 'vch-aa11bb',
            profile: 'day-pass',
            price: 100,
            created_at: '2026-09-27 14:02:11',
            uptime: '12m',
            status: 'used',
        },
    ],
};

function installApiMocks() {
    api.get.mockImplementation((url) => {
        if (url.includes('/inventory/devices')) return Promise.resolve({ data: DEVICES });
        if (url.includes('/summary')) {
            return Promise.resolve({
                data: {
                    active_count: 1,
                    total_vouchers: 12,
                    total_data_mb: 340,
                    profile_distribution: [{ profile: 'day-pass', count: 9 }],
                    stale: false,
                },
            });
        }
        if (url.includes('/system-info')) {
            return Promise.resolve({ data: { cpu_load: 7, free_memory: 100, total_memory: 256, uptime: '3d 4h' } });
        }
        if (url.includes('/voucher-template')) return Promise.resolve({ data: null });
        if (url.includes('/reports')) return Promise.resolve({ data: REPORT_DATA });
        if (url.includes('/batches')) {
            return Promise.resolve({ data: [{ comment: USER_ROW.comment, total: 1, unused: 1, profile: 'day-pass' }] });
        }
        if (url.includes('/active')) return Promise.resolve({ data: [ACTIVE_ROW] });
        if (url.includes('/profiles')) return Promise.resolve({ data: [PROFILE_ROW] });
        if (url.includes('/logs')) return Promise.resolve({ data: [LOG_ROW] });
        if (url.includes('/users')) return Promise.resolve({ data: [USER_ROW] });
        return Promise.resolve({ data: [] });
    });
    api.post.mockImplementation(() => Promise.resolve({ data: {} }));
}

async function mountOnDevice() {
    const utils = render(<Hotspot />);
    await waitFor(() => {
        expect(api.get).toHaveBeenCalledWith(expect.stringContaining(`/hotspot/${DEVICE_ID}/summary`));
    });
    return utils;
}

// React reports a render that threw through console.error ("The above error
// occurred in the <X> component"). Without this, a panel that throws inside an
// effect could still leave the tab button on screen and look like a pass.
let errorSpy;
beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    installApiMocks();
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
});
afterEach(() => {
    errorSpy.mockRestore();
});

function reactErrors() {
    return errorSpy.mock.calls
        .map((args) => args.map((a) => (a && a.stack ? a.stack : String(a))).join(' '))
        .filter((text) => /The above error occurred|Consider adding an error boundary|Cannot read propert|is not a function|is not iterable/.test(text));
}

// label -> text that ONLY that tab's panel renders.
const TABS = [
    { label: 'Active', panel: 'ActivePanel', expect: ['Online Users', '10.5.50.14'] },
    { label: 'Vouchers', panel: 'UsersPanel', expect: ['Voucher Database', 'vch-aa11bb'] },
    { label: 'Books', panel: 'BooksPanel', expect: ['Voucher Books'] },
    { label: 'Logs', panel: 'LogsPanel', expect: ['System Logs', 'vch-aa11bb logged in'] },
    // 'Total Income' alone was too weak: it is a static table header that
    // renders even with no rows behind it. The transaction username proves a
    // row actually reached the table.
    { label: 'Report', panel: 'ReportsPanel', expect: ['Total Vouchers', 'vch-aa11bb', 'day-pass'] },
    { label: 'AI Forecast', panel: 'SalesForecast', expect: ['Forecast Visualization'] },
    { label: 'Profiles', panel: 'ProfilesPanel', expect: ['Hotspot User Profiles', 'week'] },
    { label: 'Generator', panel: 'GeneratorPanel', expect: ['Print a Book', 'Token Quantity'] },
    { label: 'Templates', panel: 'template editor', expect: ['Header Text', 'Primary Color'] },
];

describe('every Hotspot tab renders its panel', () => {
    it('the landing (Dashboard) tab renders the router summary', async () => {
        await mountOnDevice();
        await waitFor(() => expect(screen.getAllByText('CPU Load').length).toBeGreaterThan(0));
        expect(screen.getAllByText('Router Uptime').length).toBeGreaterThan(0);
        expect(reactErrors()).toEqual([]);
    });

    for (const tab of TABS) {
        it(`the ${tab.label} tab renders ${tab.panel}`, async () => {
            await mountOnDevice();
            fireEvent.click(screen.getByRole('button', { name: new RegExp(tab.label, 'i') }));
            for (const text of tab.expect) {
                await waitFor(() => {
                    expect(screen.getAllByText(new RegExp(text, 'i')).length).toBeGreaterThan(0);
                });
            }
            expect(reactErrors()).toEqual([]);
        });
    }

    // Task 6's throwaway, as it was written: one mount, every tab clicked in
    // sequence, nothing thrown. It catches what the per-tab tests above cannot
    // -- a panel that only breaks once another tab has already run its effects.
    it('clicking through all nine tabs in one session throws nothing', async () => {
        await mountOnDevice();
        for (const tab of TABS) {
            fireEvent.click(screen.getByRole('button', { name: new RegExp(tab.label, 'i') }));
            await waitFor(() => {
                expect(screen.getAllByText(new RegExp(tab.expect[0], 'i')).length).toBeGreaterThan(0);
            });
        }
        expect(reactErrors()).toEqual([]);
        // …and the tab bar itself survived the whole walk.
        expect(screen.getByRole('button', { name: /Dashboard/i })).toBeInTheDocument();
    });
});

import { describe, it, expect, vi } from 'vitest';

vi.mock('../api', () => ({
    default: {
        get: vi.fn(() => Promise.resolve({ data: [] })),
        post: vi.fn(() => Promise.resolve({ data: {} })),
        put: vi.fn(() => Promise.resolve({ data: {} })),
        delete: vi.fn(() => Promise.resolve({ data: {} })),
    },
}));

// Every route target in src/App.jsx. If a route is added to App.jsx it must
// be added here too.
const routeModules = {
    Login: () => import('../pages/Login.jsx'),
    Signup: () => import('../pages/Signup.jsx'),
    Settings: () => import('../pages/Settings.jsx'),
    Dashboard: () => import('../pages/Dashboard.jsx'),
    Sites: () => import('../pages/Sites.jsx'),
    Devices: () => import('../pages/Devices.jsx'),
    NetworkMap: () => import('../pages/NetworkMap.jsx'),
    Reports: () => import('../pages/Reports.jsx'),
    Hotspot: () => import('../pages/Hotspot/index.jsx'),
    AdminDashboard: () => import('../pages/AdminDashboard.jsx'),
};

describe('route modules', () => {
    for (const [name, load] of Object.entries(routeModules)) {
        it(`${name} loads and exports a component`, async () => {
            const mod = await load();
            expect(mod.default).toBeTypeOf('function');
        });
    }
});

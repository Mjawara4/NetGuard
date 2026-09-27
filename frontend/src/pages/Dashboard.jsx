import React, { useEffect, useState } from 'react';
import api from '../api';
import { Link } from 'react-router-dom';
import { AlertCircle, CheckCircle, Server, Activity, Zap, RefreshCw } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { PageHeader, Card, Badge, Skeleton } from '../components/ui';
import ResponsiveTable from '../components/ResponsiveTable';

export default function Dashboard() {
    const [alerts, setAlerts] = useState([]);
    const [devices, setDevices] = useState([]);
    const [metrics, setMetrics] = useState([]);
    const [hotspotData, setHotspotData] = useState({ count: 0, topUsers: [], health: 0 });
    const [loading, setLoading] = useState(true);
    const [lastUpdated, setLastUpdated] = useState(null);
    const [selectedRouterId, setSelectedRouterId] = useState(null);
    const [routers, setRouters] = useState([]);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 15000);
        return () => clearInterval(interval);
    }, [selectedRouterId]);

    const fetchData = async () => {
        try {
            // Fetch all independent data sources in parallel
            const [statsResult, alertsResult, devicesResult] = await Promise.allSettled([
                api.get('/monitoring/dashboard-stats'),
                api.get('/monitoring/alerts'),
                api.get('/inventory/devices'),
            ]);

            if (statsResult.status === 'fulfilled') {
                const s = statsResult.value.data;
                setHotspotData({ count: s.active_users, topUsers: s.top_consumption, health: s.system_health });
            }

            const alertsData = alertsResult.status === 'fulfilled' ? alertsResult.value.data : [];
            const devicesData = devicesResult.status === 'fulfilled' ? devicesResult.value.data : [];
            setAlerts(alertsData);
            setDevices(devicesData);

            const activeRouters = devicesData.filter(d => d.device_type === 'router' && d.is_active);
            setRouters(activeRouters);

            // Fetch metrics for selected router (depends on devices result)
            const targetRouterId = selectedRouterId || activeRouters[0]?.id;
            if (targetRouterId) {
                try {
                    const metricsRes = await api.get(`/monitoring/metrics/latest?device_id=${targetRouterId}&limit=20&metric_type=cpu_usage`);
                    const realMetrics = metricsRes.data
                        .sort((a, b) => new Date(a.time) - new Date(b.time))
                        .map(m => ({ time: new Date(m.time).getTime(), value: m.value }));
                    if (realMetrics.length > 0) {
                        setMetrics(realMetrics);
                    } else {
                        useMockMetrics();
                    }
                } catch {
                    useMockMetrics();
                }
            } else {
                useMockMetrics();
            }
        } catch (e) {
            console.error(e);
            useMockMetrics();
        } finally {
            setLoading(false);
            setLastUpdated(new Date());
        }
    };

    const useMockMetrics = () => {
        const now = Date.now();
        const mockMetrics = Array.from({ length: 20 }, (_, i) => ({
            time: now - (20 - i) * 60000,
            value: Math.floor(Math.random() * 100) + 10
        }));
        setMetrics(mockMetrics);
    };

    const handleRefresh = () => {
        setLoading(true);
        fetchData();
    };

    const triggerAgent = async (agentName) => {
        try {
            await api.post('/agents/trigger', { agent_name: agentName });
            alert(`Triggered ${agentName} agent successfully!`);
        } catch (err) {
            console.error(err);
            alert(`Failed to trigger ${agentName}`);
        }
    };

    const criticalAlerts = alerts.filter(a => a.severity === 'critical' && a.status === 'open');
    const openAlerts = alerts.filter(a => a.status === 'open');
    const offlineDevices = devices.filter(d => !d.is_active);

    return (
        <div className="page-container">
            <div className="content-max space-y-8">
                <PageHeader
                    title="Network"
                    accent="Dashboard"
                    subtitle="Real-time intelligence and security insights."
                >
                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4">
                        <Card padding="px-5 py-3" className="flex items-center gap-4 flex-1">
                            <div className="p-2.5 bg-signal-600/10 dark:bg-signal-600/20 text-signal-600 dark:text-signal-300 rounded-md flex-shrink-0">
                                <Activity size={20} />
                            </div>
                            <div>
                                <div className="text-xs text-ink-500 dark:text-ink-400 font-medium">Active users</div>
                                <div className="text-xl font-bold text-ink-900 dark:text-ink-50">{hotspotData.count}</div>
                            </div>
                        </Card>
                        <Card padding="px-5 py-3" className="flex items-center gap-4 flex-1">
                            <div className="p-2.5 bg-up/10 dark:bg-up/20 text-up dark:text-ink-50 rounded-md flex-shrink-0">
                                <CheckCircle size={20} />
                            </div>
                            <div>
                                <div className="text-xs text-ink-500 dark:text-ink-400 font-medium">System health</div>
                                <div className="text-xl font-bold text-up dark:text-ink-100">{hotspotData.health}%</div>
                            </div>
                        </Card>
                    </div>
                </PageHeader>

                {/* Critical Alert Banner */}
                {criticalAlerts.length > 0 && (
                    <div className="bg-down/10 dark:bg-down/20 border border-down/20 dark:border-down/30 rounded-md p-4 flex items-start gap-3 animate-in fade-in slide-in-from-top-4 duration-300">
                        <div className="p-2 bg-down/20 dark:bg-down/30 rounded-md text-down dark:text-ink-50 flex-shrink-0">
                            <Zap size={20} />
                        </div>
                        <div className="flex-1">
                            <h3 className="font-semibold text-ink-900 dark:text-ink-50 text-sm">
                                {criticalAlerts.length} critical alert{criticalAlerts.length > 1 ? 's' : ''} requiring immediate attention
                            </h3>
                            <div className="mt-1 space-y-1">
                                {criticalAlerts.slice(0, 3).map((alert, i) => (
                                    <p key={i} className="text-xs text-ink-900 dark:text-ink-50 font-medium">• {alert.message}</p>
                                ))}
                                {criticalAlerts.length > 3 && (
                                    <p className="text-xs text-ink-900 dark:text-ink-50 font-medium">+{criticalAlerts.length - 3} more</p>
                                )}
                            </div>
                        </div>
                        <Link to="/reports" className="text-xs font-semibold text-ink-900 dark:text-ink-50 hover:underline flex-shrink-0">
                            View all
                        </Link>
                    </div>
                )}

                {/* Statistics Grid */}
                {loading ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                        <Skeleton className="h-32" />
                        <Skeleton className="h-32" />
                        <Skeleton className="h-32" />
                    </div>
                ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                        <Card padding="p-6" icon={Server} className="relative group">
                            <h3 className="text-ink-500 dark:text-ink-400 text-xs font-medium mb-1">Infrastructure</h3>
                            <p className="text-3xl font-bold text-ink-900 dark:text-ink-50">{devices.length}</p>
                            <p className="text-sm text-ink-500 dark:text-ink-400 mt-2">Connected devices</p>
                            {offlineDevices.length > 0 && (
                                <div className="mt-2 flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-down animate-pulse" />
                                    <span className="text-xs font-medium text-down dark:text-ink-100">{offlineDevices.length} offline</span>
                                </div>
                            )}
                        </Card>

                        <Card padding="p-6" icon={AlertCircle} className="relative group">
                            <h3 className="text-ink-500 dark:text-ink-400 text-xs font-medium mb-1">Open alerts</h3>
                            <p className="text-3xl font-bold text-down dark:text-ink-100">{openAlerts.length}</p>
                            <p className="text-sm text-ink-500 dark:text-ink-400 mt-2">Requiring attention</p>
                        </Card>

                        <Card padding="p-6" className="flex items-center gap-4 col-span-1 sm:col-span-2 lg:col-span-1">
                            <div className="flex-1">
                                <h3 className="text-ink-500 dark:text-ink-400 text-xs font-medium mb-4">Quick actions</h3>
                                {/* An accent or semantic wash cannot carry its own hue as text in
                                    dark mode -- signal-300 on signal-600/20 over ink-800 is 4.21:1.
                                    The spec's wash rule applies: neutral ink text on the wash. */}
                                <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2">
                                    <button onClick={() => triggerAgent('monitor')} className="px-4 py-2 bg-signal-600/10 dark:bg-signal-600/20 text-signal-600 dark:text-ink-50 rounded-md text-xs font-semibold hover:bg-signal-600 hover:text-white transition-all text-center">Monitor</button>
                                    <button onClick={() => triggerAgent('diagnoser')} className="px-4 py-2 bg-signal-600/10 dark:bg-signal-600/20 text-signal-600 dark:text-ink-50 rounded-md text-xs font-semibold hover:bg-signal-600 hover:text-white transition-all text-center">Diagnose</button>
                                    <button onClick={() => triggerAgent('fix')} className="px-4 py-2 bg-up/10 dark:bg-up/20 text-ink-900 dark:text-ink-50 rounded-md text-xs font-semibold hover:bg-up hover:text-white transition-all text-center col-span-2 sm:col-span-1">Auto-fix</button>
                                </div>
                            </div>
                        </Card>
                    </div>
                )}

                {/* Main Content Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {/* Alerts Table - Moved up for prominence */}
                    <Card padding="" className="lg:col-span-2">
                        <div className="p-6 sm:p-8 border-b border-ink-200 dark:border-ink-700 flex items-center justify-between">
                            <h2 className="text-xl font-semibold text-ink-900 dark:text-ink-50">Security &amp; system events</h2>
                            <button onClick={async () => {
                                try {
                                    await api.post('/monitoring/alerts/clear');
                                    fetchData();
                                } catch (e) {
                                    console.error("Failed to clear alerts", e);
                                }
                            }} className="text-xs font-medium text-ink-500 dark:text-ink-400 hover:text-signal-600 dark:hover:text-signal-300 transition-colors">Clear all</button>
                        </div>
                        <div className="overflow-hidden">
                            {loading ? (
                                <div className="p-8 space-y-4">
                                    <Skeleton className="h-12" count={3} />
                                </div>
                            ) : (
                                <ResponsiveTable
                                    data={alerts}
                                    columns={[
                                        {
                                            header: 'Level',
                                            accessor: 'severity',
                                            render: (alert) => (
                                                <Badge variant={alert.severity === 'critical' ? 'critical' : 'warning'}>
                                                    {alert.severity}
                                                </Badge>
                                            )
                                        },
                                        {
                                            header: 'Message',
                                            accessor: 'message',
                                            render: (alert) => <span className="font-bold text-ink-700 dark:text-ink-200">{alert.message}</span>
                                        },
                                        {
                                            header: 'Status',
                                            accessor: 'status',
                                            render: (alert) => (
                                                <div className="flex items-center gap-2">
                                                    <div className={`w-2 h-2 rounded-full ${alert.status === 'open' ? 'bg-warn' : 'bg-up'}`}></div>
                                                    <span className="text-xs font-medium text-ink-500 dark:text-ink-400 capitalize">{alert.status}</span>
                                                </div>
                                            )
                                        },
                                        {
                                            header: 'Actions',
                                            accessor: 'actions',
                                            render: (alert) => (
                                                <div className="text-right">
                                                    {alert.status === 'open' ? (
                                                        <button onClick={() => triggerAgent('fix')} className="text-signal-600 dark:text-signal-300 font-semibold text-xs hover:underline">
                                                            Fix
                                                        </button>
                                                    ) : (
                                                        <div className="flex flex-col items-end">
                                                            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">
                                                                {alert.resolved_at ? new Date(alert.resolved_at).toLocaleTimeString() : 'Resolved'}
                                                            </span>
                                                            {alert.resolution_summary && (
                                                                <span className="text-xs text-ink-500 dark:text-ink-400 font-medium max-w-[200px] truncate" title={alert.resolution_summary}>
                                                                    {alert.resolution_summary}
                                                                </span>
                                                            )}
                                                        </div>
                                                    )}
                                                </div>
                                            )
                                        }
                                    ]}
                                    renderCard={(alert) => (
                                        <div className="flex flex-col gap-3">
                                            <div className="flex items-center justify-between">
                                                <Badge variant={alert.severity === 'critical' ? 'critical' : 'warning'}>
                                                    {alert.severity}
                                                </Badge>
                                                <div className="flex items-center gap-2">
                                                    <div className={`w-2 h-2 rounded-full ${alert.status === 'open' ? 'bg-warn' : 'bg-up'}`}></div>
                                                    <span className="text-xs font-medium text-ink-500 dark:text-ink-400 capitalize">{alert.status}</span>
                                                </div>
                                            </div>
                                            <p className="font-bold text-ink-700 dark:text-ink-200 text-sm">{alert.message}</p>
                                            <div className="flex items-center justify-between border-t border-ink-200 dark:border-ink-700 pt-3 mt-1">
                                                <span className="text-xs text-ink-500 dark:text-ink-400 font-medium">Action required</span>
                                                {alert.status === 'open' ? (
                                                    <button onClick={() => triggerAgent('fix')} className="text-signal-600 dark:text-signal-300 font-semibold text-xs hover:underline">
                                                        Fix issue
                                                    </button>
                                                ) : (
                                                    <span className="text-xs font-medium text-ink-500 dark:text-ink-400">
                                                        {alert.resolved_at ? new Date(alert.resolved_at).toLocaleTimeString() : 'Resolved'}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    )}
                                    emptyMessage="All quiet on the network front."
                                />
                            )}
                        </div>
                    </Card>

                    {/* Traffic Chart */}
                    <Card padding="p-8">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 gap-4">
                            <div>
                                <h2 className="text-xl font-semibold text-ink-900 dark:text-ink-50">CPU performance</h2>
                                {lastUpdated && (
                                    <p className="text-xs text-ink-500 dark:text-ink-400 font-medium mt-1">
                                        Last updated: {lastUpdated.toLocaleTimeString()}
                                    </p>
                                )}
                            </div>
                            <div className="flex items-center gap-3">
                                {routers.length > 0 && (
                                    <select
                                        value={selectedRouterId || ''}
                                        onChange={(e) => setSelectedRouterId(e.target.value || null)}
                                        className="text-xs font-medium text-ink-900 dark:text-ink-100 bg-ink-50 dark:bg-ink-900 border border-ink-200 dark:border-ink-700 rounded-sm px-3 py-2 outline-none focus:ring-2 focus:ring-signal-500"
                                    >
                                        <option value="">All routers (auto)</option>
                                        {routers.map(r => (
                                            <option key={r.id} value={r.id}>{r.name}</option>
                                        ))}
                                    </select>
                                )}
                                <button
                                    onClick={handleRefresh}
                                    className="p-2 bg-ink-50 dark:bg-ink-900 rounded-md hover:bg-signal-600/10 dark:hover:bg-signal-600/20 text-ink-500 dark:text-ink-400 hover:text-signal-600 dark:hover:text-signal-300 transition-all"
                                    title="Refresh now"
                                >
                                    <RefreshCw size={16} />
                                </button>
                                <div className="flex items-center gap-2">
                                    <span className="w-3 h-3 bg-signal-500 rounded-full"></span>
                                    <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Real-time</span>
                                </div>
                            </div>
                        </div>
                        <div className="h-64">
                            {loading ? (
                                <Skeleton className="h-full" />
                            ) : (
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={metrics}>
                                        <defs>
                                            {/* Recharts takes literal colours, so these are the token
                                                hex values: signal-600, ink-100 and ink-400. They cannot
                                                carry a dark: variant -- a pre-existing limitation of
                                                every chart colour on this page, unchanged here. */}
                                            <linearGradient id="colorTraffic" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#7C3E9C" stopOpacity={0.1} />
                                                <stop offset="95%" stopColor="#7C3E9C" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#ECEFEE" />
                                        <XAxis dataKey="time" hide />
                                        <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#939E9A' }} />
                                        <Tooltip
                                            contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }}
                                            labelFormatter={(t) => new Date(t).toLocaleTimeString()}
                                        />
                                        <Area type="monotone" dataKey="value" stroke="#7C3E9C" strokeWidth={3} fillOpacity={1} fill="url(#colorTraffic)" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            )}
                        </div>
                    </Card>

                    {/* Top Users */}
                    <Card>
                        <h2 className="text-xl font-semibold text-ink-900 dark:text-ink-50 mb-8">Top consumption</h2>
                        {loading ? (
                            <div className="space-y-4">
                                <Skeleton className="h-16" count={4} />
                            </div>
                        ) : (
                            <div className="space-y-4 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
                                {hotspotData.topUsers.map((u, i) => (
                                    <div key={i} className="flex items-center justify-between p-4 bg-ink-50 dark:bg-ink-900 rounded-md hover:bg-signal-600/10 dark:hover:bg-signal-600/20 transition-colors group">
                                        <div className="flex items-center gap-3 overflow-hidden">
                                            <div className="w-10 h-10 bg-white dark:bg-ink-800 rounded-md shadow-sm flex items-center justify-center font-bold text-signal-600 dark:text-signal-300 flex-shrink-0">
                                                {u.user?.[0]?.toUpperCase() || 'M'}
                                            </div>
                                            <div className="overflow-hidden">
                                                <div className="font-bold text-ink-900 dark:text-ink-50 truncate">{u.user || u.mac}</div>
                                                <div className="text-xs text-ink-500 dark:text-ink-400 font-medium truncate">{u.ip}</div>
                                            </div>
                                        </div>
                                        <div className="text-right flex-shrink-0 ml-2">
                                            <div className="font-bold text-ink-900 dark:text-ink-50">{((u.bytes_in + u.bytes_out) / (1024 * 1024)).toFixed(1)} MB</div>
                                            <div className="text-xs text-ink-500 dark:text-ink-400 font-medium">Total usage</div>
                                        </div>
                                    </div>
                                ))}
                                {hotspotData.topUsers.length === 0 && (
                                    <div className="text-center py-10 text-ink-500 dark:text-ink-400 font-medium">No activity captured yet.</div>
                                )}
                            </div>
                        )}
                    </Card>
                </div>
            </div>
        </div>
    );
}

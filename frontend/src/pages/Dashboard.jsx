import React, { useEffect, useState } from 'react';
import api from '../api';
import { Link } from 'react-router-dom';
import { AlertCircle, CheckCircle, Server, Activity, Zap, RefreshCw } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { PageHeader, StatCard, Badge, Skeleton } from '../components/ui';
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
            try {
                const statsRes = await api.get('/monitoring/dashboard-stats');
                setHotspotData({
                    count: statsRes.data.active_users,
                    topUsers: statsRes.data.top_consumption,
                    health: statsRes.data.system_health
                });
            } catch (e) {
                console.error("Failed to fetch dashboard stats", e);
            }

            const alertsRes = await api.get('/monitoring/alerts');
            const devicesRes = await api.get('/inventory/devices');
            setAlerts(alertsRes.data);
            setDevices(devicesRes.data);

            const activeRouters = devicesRes.data.filter(d => d.device_type === 'router' && d.is_active);
            setRouters(activeRouters);

            // Pick router to chart: selected > first > none
            const targetRouterId = selectedRouterId || (activeRouters[0]?.id);
            if (targetRouterId) {
                const metricsRes = await api.get(`/monitoring/metrics/latest?device_id=${targetRouterId}&limit=20&metric_type=cpu_usage`);
                const realMetrics = metricsRes.data.sort((a, b) => new Date(a.time) - new Date(b.time)).map(m => ({
                    time: new Date(m.time).getTime(),
                    value: m.value
                }));
                if (realMetrics.length > 0) {
                    setMetrics(realMetrics);
                } else {
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
                        <div className="bg-white dark:bg-gray-800 px-5 py-3 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 flex items-center gap-4 flex-1">
                            <div className="p-2.5 bg-blue-50 dark:bg-blue-900/20 text-blue-600 rounded-xl flex-shrink-0">
                                <Activity size={20} />
                            </div>
                            <div>
                                <div className="text-[10px] uppercase text-gray-400 dark:text-gray-500 font-bold tracking-widest">Active Users</div>
                                <div className="text-xl font-black text-gray-900 dark:text-white">{hotspotData.count}</div>
                            </div>
                        </div>
                        <div className="bg-white dark:bg-gray-800 px-5 py-3 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 flex items-center gap-4 flex-1">
                            <div className="p-2.5 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 rounded-xl flex-shrink-0">
                                <CheckCircle size={20} />
                            </div>
                            <div>
                                <div className="text-[10px] uppercase text-gray-400 dark:text-gray-500 font-bold tracking-widest">System Health</div>
                                <div className="text-xl font-black text-emerald-600">{hotspotData.health}%</div>
                            </div>
                        </div>
                    </div>
                </PageHeader>

                {/* Critical Alert Banner */}
                {criticalAlerts.length > 0 && (
                    <div className="bg-red-50 dark:bg-red-900/10 border border-red-100 dark:border-red-900/30 rounded-2xl p-4 flex items-start gap-3 animate-in fade-in slide-in-from-top-4 duration-300">
                        <div className="p-2 bg-red-100 dark:bg-red-900/30 rounded-xl text-red-600 flex-shrink-0">
                            <Zap size={20} />
                        </div>
                        <div className="flex-1">
                            <h3 className="font-black text-red-800 dark:text-red-300 text-sm uppercase tracking-wider">
                                {criticalAlerts.length} Critical Alert{criticalAlerts.length > 1 ? 's' : ''} Requiring Immediate Attention
                            </h3>
                            <div className="mt-1 space-y-1">
                                {criticalAlerts.slice(0, 3).map((alert, i) => (
                                    <p key={i} className="text-xs text-red-700 dark:text-red-400 font-medium">• {alert.message}</p>
                                ))}
                                {criticalAlerts.length > 3 && (
                                    <p className="text-xs text-red-600 dark:text-red-400 font-bold">+{criticalAlerts.length - 3} more</p>
                                )}
                            </div>
                        </div>
                        <Link to="/reports" className="text-xs font-black text-red-600 dark:text-red-400 uppercase tracking-widest hover:underline flex-shrink-0">
                            View All
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
                        <div className="bg-white dark:bg-gray-800 p-6 rounded-3xl shadow-sm border border-gray-100 dark:border-gray-700 relative overflow-hidden group">
                            <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity pointer-events-none">
                                <Server size={80} />
                            </div>
                            <h3 className="text-gray-400 dark:text-gray-500 text-xs font-bold uppercase tracking-widest mb-1">Infrastructure</h3>
                            <p className="text-3xl font-black text-gray-900 dark:text-white">{devices.length}</p>
                            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">Connected Devices</p>
                            {offlineDevices.length > 0 && (
                                <div className="mt-2 flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                                    <span className="text-xs font-bold text-red-600">{offlineDevices.length} offline</span>
                                </div>
                            )}
                        </div>

                        <div className="bg-white dark:bg-gray-800 p-6 rounded-3xl shadow-sm border border-gray-100 dark:border-gray-700 relative overflow-hidden group">
                            <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity pointer-events-none">
                                <AlertCircle size={80} />
                            </div>
                            <h3 className="text-gray-400 dark:text-gray-500 text-xs font-bold uppercase tracking-widest mb-1">Open Alerts</h3>
                            <p className="text-3xl font-black text-red-600">{openAlerts.length}</p>
                            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">Requiring Attention</p>
                        </div>

                        <div className="bg-white dark:bg-gray-800 p-6 rounded-3xl shadow-sm border border-gray-100 dark:border-gray-700 flex items-center gap-4 col-span-1 sm:col-span-2 lg:col-span-1">
                            <div className="flex-1">
                                <h3 className="text-gray-400 dark:text-gray-500 text-xs font-bold uppercase tracking-widest mb-4">Quick Actions</h3>
                                <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2">
                                    <button onClick={() => triggerAgent('monitor')} className="px-4 py-2 bg-blue-50 dark:bg-blue-900/20 text-blue-600 rounded-xl text-xs font-bold hover:bg-blue-600 hover:text-white transition-all text-center">Monitor</button>
                                    <button onClick={() => triggerAgent('diagnoser')} className="px-4 py-2 bg-purple-50 dark:bg-purple-900/20 text-purple-600 rounded-xl text-xs font-bold hover:bg-purple-600 hover:text-white transition-all text-center">Diagnose</button>
                                    <button onClick={() => triggerAgent('fix')} className="px-4 py-2 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 rounded-xl text-xs font-bold hover:bg-emerald-600 hover:text-white transition-all text-center col-span-2 sm:col-span-1">Auto-Fix</button>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Main Content Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {/* Alerts Table - Moved up for prominence */}
                    <div className="lg:col-span-2 bg-white dark:bg-gray-800 rounded-3xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
                        <div className="p-6 sm:p-8 border-b border-gray-50 dark:border-gray-700 flex items-center justify-between">
                            <h2 className="text-xl font-black text-gray-900 dark:text-white">Security & System Events</h2>
                            <button onClick={async () => {
                                try {
                                    await api.post('/monitoring/alerts/clear');
                                    fetchData();
                                } catch (e) {
                                    console.error("Failed to clear alerts", e);
                                }
                            }} className="text-[10px] font-bold text-gray-400 uppercase hover:text-blue-600 transition-colors">Clear All</button>
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
                                            render: (alert) => <span className="font-bold text-gray-700 dark:text-gray-200">{alert.message}</span>
                                        },
                                        {
                                            header: 'Status',
                                            accessor: 'status',
                                            render: (alert) => (
                                                <div className="flex items-center gap-2">
                                                    <div className={`w-2 h-2 rounded-full ${alert.status === 'open' ? 'bg-orange-500' : 'bg-emerald-500'}`}></div>
                                                    <span className="text-xs font-bold text-gray-500 dark:text-gray-400 capitalize">{alert.status}</span>
                                                </div>
                                            )
                                        },
                                        {
                                            header: 'Actions',
                                            accessor: 'actions',
                                            render: (alert) => (
                                                <div className="text-right">
                                                    {alert.status === 'open' ? (
                                                        <button onClick={() => triggerAgent('fix')} className="text-blue-600 font-black text-xs uppercase tracking-widest hover:underline">
                                                            Fix
                                                        </button>
                                                    ) : (
                                                        <div className="flex flex-col items-end">
                                                            <span className="text-xs font-bold text-gray-400 dark:text-gray-500">
                                                                {alert.resolved_at ? new Date(alert.resolved_at).toLocaleTimeString() : 'Resolved'}
                                                            </span>
                                                            {alert.resolution_summary && (
                                                                <span className="text-[10px] text-emerald-600 font-medium max-w-[200px] truncate" title={alert.resolution_summary}>
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
                                                    <div className={`w-2 h-2 rounded-full ${alert.status === 'open' ? 'bg-orange-500' : 'bg-emerald-500'}`}></div>
                                                    <span className="text-xs font-bold text-gray-500 dark:text-gray-400 capitalize">{alert.status}</span>
                                                </div>
                                            </div>
                                            <p className="font-bold text-gray-700 dark:text-gray-200 text-sm">{alert.message}</p>
                                            <div className="flex items-center justify-between border-t dark:border-gray-700 pt-3 mt-1">
                                                <span className="text-xs text-gray-400 dark:text-gray-500 font-medium">Action Required</span>
                                                {alert.status === 'open' ? (
                                                    <button onClick={() => triggerAgent('fix')} className="text-blue-600 font-black text-xs uppercase tracking-widest hover:underline">
                                                        Fix Issue
                                                    </button>
                                                ) : (
                                                    <span className="text-xs font-bold text-gray-400 dark:text-gray-500">
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
                    </div>

                    {/* Traffic Chart */}
                    <div className="bg-white dark:bg-gray-800 p-8 rounded-3xl shadow-sm border border-gray-100 dark:border-gray-700">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 gap-4">
                            <div>
                                <h2 className="text-xl font-black text-gray-900 dark:text-white">CPU Performance</h2>
                                {lastUpdated && (
                                    <p className="text-[10px] text-gray-400 dark:text-gray-500 font-bold uppercase tracking-wider mt-1">
                                        Last updated: {lastUpdated.toLocaleTimeString()}
                                    </p>
                                )}
                            </div>
                            <div className="flex items-center gap-3">
                                {routers.length > 0 && (
                                    <select
                                        value={selectedRouterId || ''}
                                        onChange={(e) => setSelectedRouterId(e.target.value || null)}
                                        className="text-xs font-bold text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
                                    >
                                        <option value="">All Routers (Auto)</option>
                                        {routers.map(r => (
                                            <option key={r.id} value={r.id}>{r.name}</option>
                                        ))}
                                    </select>
                                )}
                                <button
                                    onClick={handleRefresh}
                                    className="p-2 bg-gray-50 dark:bg-gray-900 rounded-xl hover:bg-blue-50 dark:hover:bg-blue-900/20 text-gray-500 hover:text-blue-600 transition-all"
                                    title="Refresh now"
                                >
                                    <RefreshCw size={16} />
                                </button>
                                <div className="flex items-center gap-2">
                                    <span className="w-3 h-3 bg-blue-500 rounded-full"></span>
                                    <span className="text-xs font-bold text-gray-400 uppercase">Real-time</span>
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
                                            <linearGradient id="colorTraffic" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.1} />
                                                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f1f1" />
                                        <XAxis dataKey="time" hide />
                                        <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#94a3b8' }} />
                                        <Tooltip
                                            contentStyle={{ borderRadius: '16px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }}
                                            labelFormatter={(t) => new Date(t).toLocaleTimeString()}
                                        />
                                        <Area type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={3} fillOpacity={1} fill="url(#colorTraffic)" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            )}
                        </div>
                    </div>

                    {/* Top Users */}
                    <div className="bg-white dark:bg-gray-800 p-6 sm:p-8 rounded-3xl shadow-sm border border-gray-100 dark:border-gray-700">
                        <h2 className="text-xl font-black text-gray-900 dark:text-white mb-8">Top Consumption</h2>
                        {loading ? (
                            <div className="space-y-4">
                                <Skeleton className="h-16" count={4} />
                            </div>
                        ) : (
                            <div className="space-y-4 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
                                {hotspotData.topUsers.map((u, i) => (
                                    <div key={i} className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-900 rounded-2xl hover:bg-blue-50 dark:hover:bg-blue-900/10 transition-colors group">
                                        <div className="flex items-center gap-3 overflow-hidden">
                                            <div className="w-10 h-10 bg-white dark:bg-gray-800 rounded-xl shadow-sm flex items-center justify-center font-bold text-blue-600 flex-shrink-0">
                                                {u.user?.[0]?.toUpperCase() || 'M'}
                                            </div>
                                            <div className="overflow-hidden">
                                                <div className="font-bold text-gray-900 dark:text-white truncate">{u.user || u.mac}</div>
                                                <div className="text-xs text-gray-400 dark:text-gray-500 font-medium truncate">{u.ip}</div>
                                            </div>
                                        </div>
                                        <div className="text-right flex-shrink-0 ml-2">
                                            <div className="font-black text-gray-900 dark:text-white">{((u.bytes_in + u.bytes_out) / (1024 * 1024)).toFixed(1)} MB</div>
                                            <div className="text-[10px] text-gray-400 dark:text-gray-500 uppercase font-bold tracking-tighter">Total Usage</div>
                                        </div>
                                    </div>
                                ))}
                                {hotspotData.topUsers.length === 0 && (
                                    <div className="text-center py-10 text-gray-400 dark:text-gray-500 font-medium">No activity captured yet.</div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

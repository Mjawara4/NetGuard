import React, { useEffect, useState } from 'react';
import api from '../api';
import { Link } from 'react-router-dom';
import { AlertCircle, CheckCircle, Server, Activity } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import ResponsiveTable from '../components/ResponsiveTable';

export default function Dashboard() {
    const [alerts, setAlerts] = useState([]);
    const [devices, setDevices] = useState([]);
    const [metrics, setMetrics] = useState([]);
    const [hotspotData, setHotspotData] = useState({ count: 0, topUsers: [], health: 0 });

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 5000);
        return () => clearInterval(interval);
    }, []);

    const fetchData = async () => {
        try {
            // 1. Aggregated Dashboard Stats (Health, Users, Top Consumption)
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

            // 2. CPU Metrics for Graph (First Active Router)
            const routers = devicesRes.data.filter(d => d.device_type === 'router' && d.is_active);
            if (routers.length > 0) {
                const routerId = routers[0].id;
                const metricsRes = await api.get(`/monitoring/metrics/latest?device_id=${routerId}&limit=20&metric_type=cpu_usage`);

                // Sort by time ascending for graph
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

    const triggerAgent = async (agentName) => {
        try {
            await api.post('/agents/trigger', { agent_name: agentName });
            alert(`Triggered ${agentName} agent successfully!`);
        } catch (err) {
            console.error(err);
            alert(`Failed to trigger ${agentName}`);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 flex flex-col pt-4 sm:pt-8 px-4 sm:px-6 lg:px-10 pb-12">
            {/* Page Header */}
            <div className="max-w-7xl mx-auto w-full mb-8 sm:mb-10">
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                    <div>
                        <h1 className="text-3xl sm:text-4xl font-black text-gray-900 tracking-tight leading-none">
                            Network <span className="text-blue-600">Dashboard</span>
                        </h1>
                        <p className="text-gray-500 mt-2 font-medium text-sm sm:text-base">Real-time intelligence and security insights.</p>
                    </div>

                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4">
                        <div className="bg-white px-5 py-3 rounded-2xl shadow-sm border border-gray-100 flex items-center gap-4 flex-1">
                            <div className="p-2.5 bg-blue-50 text-blue-600 rounded-xl flex-shrink-0">
                                <Activity size={20} />
                            </div>
                            <div>
                                <div className="text-[10px] uppercase text-gray-400 font-bold tracking-widest">Active Users</div>
                                <div className="text-xl font-black text-gray-900">{hotspotData.count}</div>
                            </div>
                        </div>
                        <div className="bg-white px-5 py-3 rounded-2xl shadow-sm border border-gray-100 flex items-center gap-4 flex-1">
                            <div className="p-2.5 bg-emerald-50 text-emerald-600 rounded-xl flex-shrink-0">
                                <CheckCircle size={20} />
                            </div>
                            <div>
                                <div className="text-[10px] uppercase text-gray-400 font-bold tracking-widest">System Health</div>
                                <div className="text-xl font-black text-emerald-600">{hotspotData.health}%</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div className="max-w-7xl mx-auto w-full space-y-8">
                {/* Statistics Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                    <div className="bg-white p-6 rounded-3xl shadow-sm border border-gray-100 relative overflow-hidden group">
                        <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
                            <Server size={80} />
                        </div>
                        <h3 className="text-gray-400 text-xs font-bold uppercase tracking-widest mb-1">Infrastructure</h3>
                        <p className="text-3xl font-black text-gray-900">{devices.length}</p>
                        <p className="text-sm text-gray-500 mt-2">Connected Devices</p>
                    </div>

                    <div className="bg-white p-6 rounded-3xl shadow-sm border border-gray-100 relative overflow-hidden group">
                        <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
                            <AlertCircle size={80} />
                        </div>
                        <h3 className="text-gray-400 text-xs font-bold uppercase tracking-widest mb-1">Open Alerts</h3>
                        <p className="text-3xl font-black text-red-600">{alerts.filter(a => a.status === 'open').length}</p>
                        <p className="text-sm text-gray-500 mt-2">Requiring Attention</p>
                    </div>

                    <div className="bg-white p-6 rounded-3xl shadow-sm border border-gray-100 flex items-center gap-4 col-span-1 sm:col-span-2 lg:col-span-1">
                        <div className="flex-1">
                            <h3 className="text-gray-400 text-xs font-bold uppercase tracking-widest mb-4">Quick Actions</h3>
                            <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2">
                                <button onClick={() => triggerAgent('monitor')} className="px-4 py-2 bg-blue-50 text-blue-600 rounded-xl text-xs font-bold hover:bg-blue-600 hover:text-white transition-all text-center">Monitor</button>
                                <button onClick={() => triggerAgent('diagnoser')} className="px-4 py-2 bg-purple-50 text-purple-600 rounded-xl text-xs font-bold hover:bg-purple-600 hover:text-white transition-all text-center">Diagnose</button>
                                <button onClick={() => triggerAgent('fix')} className="px-4 py-2 bg-emerald-50 text-emerald-600 rounded-xl text-xs font-bold hover:bg-emerald-600 hover:text-white transition-all text-center col-span-2 sm:col-span-1">Auto-Fix</button>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Main Content Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {/* Traffic Chart */}
                    <div className="bg-white p-8 rounded-3xl shadow-sm border border-gray-100">
                        <div className="flex items-center justify-between mb-8">
                            <h2 className="text-xl font-black text-gray-900">CPU Performance</h2>
                            <div className="flex items-center gap-2">
                                <span className="w-3 h-3 bg-blue-500 rounded-full"></span>
                                <span className="text-xs font-bold text-gray-400 uppercase">Real-time</span>
                            </div>
                        </div>
                        <div className="h-64">
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
                        </div>
                    </div>

                    {/* Top Users */}
                    <div className="bg-white p-6 sm:p-8 rounded-3xl shadow-sm border border-gray-100">
                        <h2 className="text-xl font-black text-gray-900 mb-8">Top Consumption</h2>
                        <div className="space-y-4 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
                            {hotspotData.topUsers.map((u, i) => (
                                <div key={i} className="flex items-center justify-between p-4 bg-gray-50 rounded-2xl hover:bg-blue-50 transition-colors group">
                                    <div className="flex items-center gap-3 overflow-hidden">
                                        <div className="w-10 h-10 bg-white rounded-xl shadow-sm flex items-center justify-center font-bold text-blue-600 flex-shrink-0">
                                            {u.user?.[0]?.toUpperCase() || 'M'}
                                        </div>
                                        <div className="overflow-hidden">
                                            <div className="font-bold text-gray-900 truncate">{u.user || u.mac}</div>
                                            <div className="text-xs text-gray-400 font-medium truncate">{u.ip}</div>
                                        </div>
                                    </div>
                                    <div className="text-right flex-shrink-0 ml-2">
                                        <div className="font-black text-gray-900">{((u.bytes_in + u.bytes_out) / (1024 * 1024)).toFixed(1)} MB</div>
                                        <div className="text-[10px] text-gray-400 uppercase font-bold tracking-tighter">Total Usage</div>
                                    </div>
                                </div>
                            ))}
                            {hotspotData.topUsers.length === 0 && (
                                <div className="text-center py-10 text-gray-400 font-medium">No activity captured yet.</div>
                            )}
                        </div>
                    </div>

                    {/* Alerts Table */}
                    <div className="lg:col-span-2 bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
                        <div className="p-6 sm:p-8 border-b border-gray-50 flex items-center justify-between">
                            <h2 className="text-xl font-black text-gray-900">Security & System Events</h2>
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
                            <ResponsiveTable
                                data={alerts}
                                columns={[
                                    {
                                        header: 'Level',
                                        accessor: 'severity',
                                        render: (alert) => (
                                            <span className={`px-3 py-1 text-[10px] font-black uppercase rounded-lg ${alert.severity === 'critical' ? 'bg-red-100 text-red-600' : 'bg-yellow-100 text-yellow-600'}`}>
                                                {alert.severity}
                                            </span>
                                        )
                                    },
                                    {
                                        header: 'Message',
                                        accessor: 'message',
                                        render: (alert) => <span className="font-bold text-gray-700">{alert.message}</span>
                                    },
                                    {
                                        header: 'Status',
                                        accessor: 'status',
                                        render: (alert) => (
                                            <div className="flex items-center gap-2">
                                                <div className={`w-2 h-2 rounded-full ${alert.status === 'open' ? 'bg-orange-500' : 'bg-emerald-500'}`}></div>
                                                <span className="text-xs font-bold text-gray-500 capitalize">{alert.status}</span>
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
                                                        <span className="text-xs font-bold text-gray-400">
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
                                            <span className={`px-3 py-1 text-[10px] font-black uppercase rounded-lg ${alert.severity === 'critical' ? 'bg-red-100 text-red-600' : 'bg-yellow-100 text-yellow-600'}`}>
                                                {alert.severity}
                                            </span>
                                            <div className="flex items-center gap-2">
                                                <div className={`w-2 h-2 rounded-full ${alert.status === 'open' ? 'bg-orange-500' : 'bg-emerald-500'}`}></div>
                                                <span className="text-xs font-bold text-gray-500 capitalize">{alert.status}</span>
                                            </div>
                                        </div>
                                        <p className="font-bold text-gray-700 text-sm">{alert.message}</p>
                                        <div className="flex items-center justify-between border-t pt-3 mt-1">
                                            <span className="text-xs text-gray-400 font-medium">Action Required</span>
                                            {alert.status === 'open' ? (
                                                <button onClick={() => triggerAgent('fix')} className="text-blue-600 font-black text-xs uppercase tracking-widest hover:underline">
                                                    Fix Issue
                                                </button>
                                            ) : (
                                                <span className="text-xs font-bold text-gray-400">
                                                    {alert.resolved_at ? new Date(alert.resolved_at).toLocaleTimeString() : 'Resolved'}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                )}
                                emptyMessage="All quiet on the network front."
                            />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

import React, { useEffect, useState } from 'react';
import api from '../api';
import { Link } from 'react-router-dom';
import { AreaChart, Area, BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Calendar, Download } from 'lucide-react';

export default function Reports() {
    const [devices, setDevices] = useState([]);
    const [selectedDevice, setSelectedDevice] = useState('');
    const [timeRange, setTimeRange] = useState('24h');
    const [loading, setLoading] = useState(false);
    const [metrics, setMetrics] = useState({
        cpu: [],
        traffic: [],
        clients: []
    });

    useEffect(() => {
        fetchDevices();
    }, []);

    useEffect(() => {
        if (selectedDevice) {
            fetchReports();
        }
    }, [selectedDevice, timeRange]);

    const fetchDevices = async () => {
        try {
            const res = await api.get('/inventory/devices');
            setDevices(res.data);
            if (res.data.length > 0) setSelectedDevice(res.data[0].id);
        } catch (e) {
            console.error(e);
        }
    };

    const fetchReports = async () => {
        setLoading(true);
        try {
            // Calculate start time
            const end = new Date();
            const start = new Date();
            if (timeRange === '1h') start.setHours(end.getHours() - 1);
            if (timeRange === '24h') start.setHours(end.getHours() - 24);
            if (timeRange === '7d') start.setDate(end.getDate() - 7);

            const startStr = start.toISOString();
            const endStr = end.toISOString();

            // Fetch CPU
            const cpuRes = await api.get(`/monitoring/metrics/history?device_id=${selectedDevice}&metric_type=cpu_usage&start_time=${startStr}&end_time=${endStr}`);
            const trafficRes = await api.get(`/monitoring/metrics/history?device_id=${selectedDevice}&metric_type=hotspot_traffic&start_time=${startStr}&end_time=${endStr}`);

            setMetrics({
                cpu: formatData(cpuRes.data),
                traffic: formatData(trafficRes.data),
                clients: [] // Omitted for brevity
            });
        } catch (e) {
            console.error("Failed to fetch reports", e);
        } finally {
            setLoading(false);
        }
    };

    const formatData = (data) => {
        return data.map(d => ({
            time: new Date(d.time).toLocaleString(),
            value: d.value
        }));
    };

    return (
        <div className="min-h-screen bg-gray-50 pt-4 sm:pt-8 px-4 sm:px-6 lg:px-10 pb-12">
            <div className="max-w-7xl mx-auto">
                <div className="mb-8">
                    <h1 className="text-3xl sm:text-4xl font-black text-gray-900 tracking-tight leading-none">
                        Network <span className="text-blue-600">Analytics</span>
                    </h1>
                    <p className="text-gray-500 mt-2 font-medium text-sm sm:text-base">Insights and historical telemetry data.</p>
                </div>

                <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-4 sm:p-6 mb-8 flex flex-col sm:flex-row gap-4 items-center">
                    <div className="flex items-center gap-3 w-full sm:w-auto">
                        <span className="font-bold text-[10px] uppercase tracking-widest text-gray-400">Device</span>
                        <select className="flex-1 sm:w-64 bg-gray-50 border-none rounded-xl px-4 py-2.5 font-bold text-sm focus:ring-2 focus:ring-blue-500 transition-all" value={selectedDevice} onChange={e => setSelectedDevice(e.target.value)}>
                            {devices.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                        </select>
                    </div>
                    <div className="flex bg-gray-50 rounded-xl p-1.5 w-full sm:w-auto overflow-x-auto no-scrollbar">
                        <button className={`flex-1 sm:flex-none px-4 py-2 rounded-lg text-xs font-black uppercase tracking-wider transition-all whitespace-nowrap ${timeRange === '1h' ? 'bg-white shadow-sm text-blue-600' : 'text-gray-400 hover:text-gray-600'}`} onClick={() => setTimeRange('1h')}>1H</button>
                        <button className={`flex-1 sm:flex-none px-4 py-2 rounded-lg text-xs font-black uppercase tracking-wider transition-all whitespace-nowrap ${timeRange === '24h' ? 'bg-white shadow-sm text-blue-600' : 'text-gray-400 hover:text-gray-600'}`} onClick={() => setTimeRange('24h')}>24H</button>
                        <button className={`flex-1 sm:flex-none px-4 py-2 rounded-lg text-xs font-black uppercase tracking-wider transition-all whitespace-nowrap ${timeRange === '7d' ? 'bg-white shadow-sm text-blue-600' : 'text-gray-400 hover:text-gray-600'}`} onClick={() => setTimeRange('7d')}>7D</button>
                    </div>
                </div>

                <div className="grid grid-cols-1 gap-8">
                    {loading ? (
                        <div className="bg-white rounded-3xl p-20 shadow-sm border border-gray-100 text-center">
                            <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                            <p className="font-black text-gray-400 uppercase tracking-widest text-xs animate-pulse">Aggregating telemetry...</p>
                        </div>
                    ) : (
                        <>
                            <div className="bg-white p-6 sm:p-8 rounded-3xl shadow-sm border border-gray-100 animate-in fade-in slide-in-from-bottom-4 duration-500">
                                <h3 className="font-black text-gray-900 uppercase tracking-widest text-[10px] mb-6 flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-blue-600"></div>
                                    Performance Thresholds (CPU %)
                                </h3>
                                <div className="h-[300px] sm:h-[400px]">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={metrics.cpu}>
                                            <defs>
                                                <linearGradient id="colorCpu" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                            <XAxis dataKey="time" hide />
                                            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fontWeight: 'bold', fill: '#94a3b8' }} />
                                            <Tooltip contentStyle={{ borderRadius: '16px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }} />
                                            <Area type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={4} fillOpacity={1} fill="url(#colorCpu)" name="CPU %" />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            <div className="bg-white p-6 sm:p-8 rounded-3xl shadow-sm border border-gray-100 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-150">
                                <h3 className="font-black text-gray-900 uppercase tracking-widest text-[10px] mb-6 flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
                                    Hotspot Data Throughput (MB)
                                </h3>
                                <div className="h-[300px] sm:h-[400px]">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={metrics.traffic}>
                                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                            <XAxis dataKey="time" hide />
                                            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fontWeight: 'bold', fill: '#94a3b8' }} />
                                            <Tooltip contentStyle={{ borderRadius: '16px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }} />
                                            <Bar dataKey="value" fill="#10b981" radius={[6, 6, 0, 0]} name="Traffic (MB)" />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}

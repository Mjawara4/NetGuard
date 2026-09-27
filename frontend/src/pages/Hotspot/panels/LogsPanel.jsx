import React from 'react';
import { RefreshCw, Search } from 'lucide-react';
import ResponsiveTable from '../../../components/ResponsiveTable';

export default function LogsPanel({ logs, logSearch, setLogSearch, logFilter, setLogFilter, loading, fetchData }) {
    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between bg-white dark:bg-gray-800 p-6 rounded-3xl border border-gray-100 dark:border-gray-700 shadow-sm">
                <div>
                    <h2 className="text-xl font-black text-gray-900 dark:text-white">System Logs</h2>
                    <p className="text-gray-500 dark:text-gray-400 text-sm font-medium">Real-time MikroTik hotspot event logs.</p>
                </div>
                <button onClick={fetchData} className="p-3 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-2xl hover:bg-blue-100 transition-colors">
                    <RefreshCw size={20} className={loading ? 'animate-spin' : ''} />
                </button>
            </div>
            <div className="flex flex-col md:flex-row gap-4">
                <div className="flex-1 bg-white dark:bg-gray-800 p-4 rounded-3xl border border-gray-100 dark:border-gray-700 shadow-sm flex items-center gap-4">
                    <div className="relative flex-1">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                        <input
                            type="text"
                            placeholder="Search logs (user, ip, or message)..."
                            value={logSearch}
                            onChange={(e) => setLogSearch(e.target.value)}
                            className="w-full bg-gray-50 dark:bg-gray-700 border-none rounded-2xl py-2.5 pl-12 pr-4 text-sm font-bold text-gray-700 dark:text-gray-200 outline-none focus:ring-2 focus:ring-blue-500/20"
                        />
                    </div>
                    <select
                        value={logFilter}
                        onChange={(e) => setLogFilter(e.target.value)}
                        className="bg-gray-50 dark:bg-gray-700 border-none rounded-2xl py-2.5 px-4 text-xs font-black uppercase tracking-widest text-gray-600 dark:text-gray-200 focus:ring-2 focus:ring-blue-500/20"
                    >
                        <option value="all">All Logs</option>
                        <option value="today">Today Only</option>
                        <option value="recent">Last Hour</option>
                    </select>
                </div>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-[32px] shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
                <ResponsiveTable
                    data={logs.filter(l => {
                        const matchesSearch =
                            l.user_info.toLowerCase().includes(logSearch.toLowerCase()) ||
                            l.message.toLowerCase().includes(logSearch.toLowerCase()) ||
                            l.time.toLowerCase().includes(logSearch.toLowerCase());

                        if (logFilter === 'all') return matchesSearch;

                        // RouterOS heuristic: HH:MM:SS (Today) vs MMM/DD HH:MM:SS (Older)
                        const isToday = !l.time.includes('/') && !/[a-zA-Z]/.test(l.time.split(' ')[0]);

                        if (logFilter === 'today') return matchesSearch && isToday;
                        if (logFilter === 'recent') {
                            // Heuristic: Last 10 minutes or just top 10 logs if we can't parse
                            return matchesSearch && (isToday || logs.indexOf(l) < 10);
                        }
                        return matchesSearch;
                    })}
                    columns={[
                        {
                            header: 'Time',
                            accessor: 'time',
                            render: (l) => <div className="text-xs font-mono font-bold text-gray-400">{l.time}</div>
                        },
                        {
                            header: 'Username / IP',
                            accessor: 'user_info',
                            render: (l) => (
                                <div className="flex items-center gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full bg-blue-500"></div>
                                    <div className="font-black text-gray-900 dark:text-white text-xs uppercase">{l.user_info}</div>
                                </div>
                            )
                        },
                        {
                            header: 'Event Message',
                            accessor: 'message',
                            render: (l) => <div className="text-xs font-medium text-gray-600 dark:text-gray-300 max-w-md truncate">{l.message}</div>
                        }
                    ]}
                    renderCard={(l) => (
                        <div className="space-y-2">
                            <div className="flex justify-between items-center">
                                <span className="text-[10px] font-mono font-bold text-gray-400">{l.time}</span>
                                <span className="font-black text-blue-600 dark:text-blue-400 text-[10px] uppercase bg-blue-50 dark:bg-blue-900/20 px-2 py-0.5 rounded-md">{l.user_info}</span>
                            </div>
                            <p className="text-xs font-medium text-gray-700 dark:text-gray-200 leading-relaxed">{l.message}</p>
                        </div>
                    )}
                    emptyMessage="No hotspot logs found."
                />
            </div>
        </div>
    );
}

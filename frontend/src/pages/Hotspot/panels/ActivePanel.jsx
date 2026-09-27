import React from 'react';
import { ArrowDownCircle, ArrowUpCircle, Clock, Search, Wifi } from 'lucide-react';
import ResponsiveTable from '../../../components/ResponsiveTable';

export default function ActivePanel({ activeSessions, userSearch, setUserSearch, handleKick }) {
    return (
        <div className="bg-white dark:bg-ink-800 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="p-6 sm:p-8 border-b border-ink-200 dark:border-ink-700 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h2 className="text-xl font-semibold text-ink-900 dark:text-ink-50">Online Users</h2>
                    <p className="text-ink-500 dark:text-ink-400 text-xs mt-1 font-medium">{activeSessions.length} connected</p>
                </div>
                <div className="flex items-center gap-3">
                    <div className="relative group flex-1 sm:w-64">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-ink-500 transition-colors group-focus-within:text-signal-600 dark:text-ink-400" size={16} />
                        <input
                            type="text"
                            placeholder="Search active sessions..."
                            value={userSearch}
                            onChange={(e) => setUserSearch(e.target.value)}
                            className="placeholder:text-ink-500 dark:placeholder:text-ink-400 w-full bg-ink-50 dark:bg-ink-800 border border-transparent focus:border-signal-500/30 focus:bg-white dark:focus:bg-ink-800 rounded-lg py-2 pl-10 pr-4 text-xs font-bold text-ink-900 dark:text-ink-100 outline-none transition-all shadow-inner"
                        />
                    </div>
                    <span className="inline-flex max-w-fit bg-up/10 dark:bg-up/20 text-ink-900 dark:text-ink-50 px-3 py-1.5 rounded-md text-xs font-semibold">
                        Live
                    </span>
                </div>
            </div>
            <div className="overflow-hidden">
                <ResponsiveTable
                    data={activeSessions.filter(u => u.user.toLowerCase().includes(userSearch.toLowerCase()) || (u.mac_address || '').toLowerCase().includes(userSearch.toLowerCase()) || (u.address || '').toLowerCase().includes(userSearch.toLowerCase()))}
                    columns={[
                        {
                            header: 'Identity',
                            accessor: 'user',
                            render: (u) => <div className="font-bold text-ink-900 dark:text-ink-50 text-sm">{u.user}</div>
                        },
                        {
                            header: 'Network Info',
                            accessor: 'address',
                            render: (u) => (
                                <div>
                                    <div className="text-xs text-ink-900 dark:text-ink-50 font-mono font-bold leading-none mb-1">{u.address}</div>
                                    <div className="text-xs text-ink-500 dark:text-ink-400 font-mono">{u.mac_address || 'Unknown MAC'}</div>
                                </div>
                            )
                        },
                        {
                            header: 'Traffic',
                            accessor: 'bytes',
                            render: (u) => (
                                <div className="flex items-center gap-3 text-xs font-bold font-mono">
                                    <div className="flex items-center gap-1 text-up dark:text-ink-100">
                                        <ArrowDownCircle size={12} />
                                        {(u.bytes_out / 1024 / 1024).toFixed(1)} MB
                                    </div>
                                    <div className="flex items-center gap-1 text-signal-600 dark:text-signal-300">
                                        <ArrowUpCircle size={12} />
                                        {(u.bytes_in / 1024 / 1024).toFixed(1)} MB
                                    </div>
                                </div>
                            )
                        },
                        {
                            header: 'Time Online',
                            accessor: 'uptime',
                            render: (u) => <div className="text-xs text-ink-500 dark:text-ink-400 font-mono font-bold whitespace-nowrap bg-ink-50 dark:bg-ink-800 px-2 py-1 rounded-lg">{u.uptime}</div>
                        },
                        {
                            header: 'Time Left / Limits',
                            accessor: 'remaining_time',
                            render: (u) => (
                                <div className="flex flex-col gap-1">
                                    <div className={`text-xs font-bold font-mono px-2 py-1 rounded-lg border max-w-fit ${u.remaining_time === 'UNLIM' ? 'bg-ink-50 dark:bg-ink-800 text-ink-500 dark:text-ink-400 border-ink-200 dark:border-ink-700' :
                                        u.remaining_time === '0s' ? 'bg-down/10 dark:bg-down/20 text-down dark:text-ink-50 border-down/20 dark:border-down/30' :
                                            'bg-signal-600/10 dark:bg-signal-600/20 text-ink-900 dark:text-ink-50 border-signal-600/20 dark:border-signal-600/30'
                                        }`}>
                                        {u.remaining_time}
                                    </div>
                                    {(u.limit_uptime || u.limit_bytes_total) && (
                                        <div className="text-xs text-ink-500 dark:text-ink-400 font-medium">
                                            {u.limit_uptime && <div className="font-mono">Limit: {u.limit_uptime}</div>}
                                            {u.limit_bytes_total > 0 && <div>Data: {(u.limit_bytes_total / 1024 / 1024).toFixed(0)}MB</div>}
                                        </div>
                                    )}
                                </div>
                            )
                        },
                        {
                            header: 'Interrupt',
                            accessor: 'actions',
                            render: (u) => (
                                <div className="text-right">
                                    <button onClick={() => handleKick(u.id)} className="text-down dark:text-ink-100 font-semibold text-xs hover:underline px-3 py-1.5 bg-down/10 dark:bg-down/20 rounded-lg whitespace-nowrap">
                                        Kick
                                    </button>
                                </div>
                            )
                        }
                    ]}
                    renderCard={(u) => (
                        <div className="flex flex-col gap-3">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <Wifi size={16} className="text-up dark:text-ink-100" />
                                    <span className="font-bold text-ink-900 dark:text-ink-50 text-sm">{u.user}</span>
                                </div>
                                <span className="text-xs font-mono text-ink-500 dark:text-ink-400">{u.address}</span>
                            </div>
                            <div className="flex justify-between items-center text-xs text-ink-500 dark:text-ink-400">
                                <div className="flex items-center gap-1.5">
                                    <Clock size={12} />
                                    <span>{u.uptime} online</span>
                                </div>
                                <div className={`font-bold text-xs font-mono ${u.remaining_time === 'UNLIM' ? 'text-ink-500 dark:text-ink-400' : 'text-signal-600 dark:text-signal-300'}`}>
                                    Left: {u.remaining_time}
                                </div>
                            </div>
                            <div className="flex justify-end border-t border-ink-200 dark:border-ink-700 pt-3 mt-1">
                                <button onClick={() => handleKick(u.id)} className="w-full text-center text-down dark:text-ink-100 font-semibold text-xs bg-down/10 dark:bg-down/20 py-2 rounded-lg">Interrupt session</button>
                            </div>
                        </div>
                    )}
                    emptyMessage="No active hotspot sessions detected."
                />
            </div>
        </div>
    );
}

import React from 'react';
import { ArrowDownCircle, ArrowUpCircle, Clock, Search, Wifi } from 'lucide-react';
import ResponsiveTable from '../../../components/ResponsiveTable';

export default function ActivePanel({ activeSessions, userSearch, setUserSearch, handleKick }) {
    return (
        <div className="bg-white dark:bg-gray-800 rounded-3xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="p-6 sm:p-8 border-b border-gray-50 dark:border-gray-700 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h2 className="text-xl font-black text-gray-900 dark:text-white">Online Users</h2>
                    <p className="text-gray-400 text-[10px] mt-1 font-bold uppercase tracking-widest">{activeSessions.length} Connected</p>
                </div>
                <div className="flex items-center gap-3">
                    <div className="relative group flex-1 sm:w-64">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 transition-colors group-focus-within:text-blue-500" size={16} />
                        <input
                            type="text"
                            placeholder="Search active sessions..."
                            value={userSearch}
                            onChange={(e) => setUserSearch(e.target.value)}
                            className="w-full bg-gray-50 dark:bg-gray-700 border border-transparent focus:border-blue-500/30 focus:bg-white dark:focus:bg-gray-800 rounded-2xl py-2 pl-10 pr-4 text-xs font-bold text-gray-700 dark:text-gray-200 outline-none transition-all shadow-inner uppercase tracking-wide"
                        />
                    </div>
                    <span className="inline-flex max-w-fit bg-emerald-50 text-emerald-600 px-3 py-1.5 rounded-xl text-[10px] font-black uppercase tracking-widest">
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
                            render: (u) => <div className="font-bold text-gray-900 dark:text-white text-sm">{u.user}</div>
                        },
                        {
                            header: 'Network Info',
                            accessor: 'address',
                            render: (u) => (
                                <div>
                                    <div className="text-xs text-gray-900 dark:text-white font-mono font-bold leading-none mb-1">{u.address}</div>
                                    <div className="text-[10px] text-gray-400 font-mono tracking-tighter uppercase">{u.mac_address || 'Unknown MAC'}</div>
                                </div>
                            )
                        },
                        {
                            header: 'Traffic',
                            accessor: 'bytes',
                            render: (u) => (
                                <div className="flex items-center gap-3 text-[10px] font-black uppercase tracking-tighter">
                                    <div className="flex items-center gap-1 text-emerald-600">
                                        <ArrowDownCircle size={12} />
                                        {(u.bytes_out / 1024 / 1024).toFixed(1)} MB
                                    </div>
                                    <div className="flex items-center gap-1 text-blue-600">
                                        <ArrowUpCircle size={12} />
                                        {(u.bytes_in / 1024 / 1024).toFixed(1)} MB
                                    </div>
                                </div>
                            )
                        },
                        {
                            header: 'Time Online',
                            accessor: 'uptime',
                            render: (u) => <div className="text-xs text-gray-500 dark:text-gray-400 font-bold whitespace-nowrap bg-gray-50 dark:bg-gray-700 px-2 py-1 rounded-lg">{u.uptime}</div>
                        },
                        {
                            header: 'Time Left / Limits',
                            accessor: 'remaining_time',
                            render: (u) => (
                                <div className="flex flex-col gap-1">
                                    <div className={`text-xs font-black px-2 py-1 rounded-lg border max-w-fit ${u.remaining_time === 'UNLIM' ? 'bg-gray-50 dark:bg-gray-700 text-gray-400 border-gray-100 dark:border-gray-600' :
                                        u.remaining_time === '0s' ? 'bg-red-50 dark:bg-red-900/20 text-red-600 border-red-100 dark:border-red-900/30' : 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 border-blue-100 dark:border-blue-900/30'
                                        }`}>
                                        {u.remaining_time}
                                    </div>
                                    {(u.limit_uptime || u.limit_bytes_total) && (
                                        <div className="text-[9px] text-gray-500 dark:text-gray-400 font-bold uppercase tracking-wide">
                                            {u.limit_uptime && <div>Limit: {u.limit_uptime}</div>}
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
                                    <button onClick={() => handleKick(u.id)} className="text-red-500 hover:text-red-700 font-black text-[10px] uppercase tracking-widest hover:underline px-3 py-1.5 bg-red-50 dark:bg-red-900/20 rounded-lg whitespace-nowrap">
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
                                    <Wifi size={16} className="text-emerald-500" />
                                    <span className="font-bold text-gray-900 dark:text-white text-sm">{u.user}</span>
                                </div>
                                <span className="text-[10px] font-mono text-gray-400">{u.address}</span>
                            </div>
                            <div className="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400">
                                <div className="flex items-center gap-1.5">
                                    <Clock size={12} />
                                    <span>{u.uptime} online</span>
                                </div>
                                <div className={`font-black text-[10px] uppercase ${u.remaining_time === 'UNLIM' ? 'text-gray-400' : 'text-blue-600'}`}>
                                    Left: {u.remaining_time}
                                </div>
                            </div>
                            <div className="flex justify-end border-t pt-3 mt-1">
                                <button onClick={() => handleKick(u.id)} className="w-full text-center text-red-500 font-bold text-[10px] uppercase bg-red-50 py-2 rounded-lg">Interrupt Session</button>
                            </div>
                        </div>
                    )}
                    emptyMessage="No active hotspot sessions detected."
                />
            </div>
        </div>
    );
}

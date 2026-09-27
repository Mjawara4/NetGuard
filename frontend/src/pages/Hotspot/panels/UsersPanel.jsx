import React from 'react';
import { Download, Search, Trash2, Users } from 'lucide-react';
import ResponsiveTable from '../../../components/ResponsiveTable';

export default function UsersPanel({ users, userSearch, setUserSearch, searchResults, isSearching, handleDelete, handleExportCSV, handleCleanupExpired, handleBulkDeleteByComment }) {
    return (
        <div className="bg-white dark:bg-gray-800 rounded-3xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="p-6 sm:p-8 border-b border-gray-50 dark:border-gray-700 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                <div className="flex items-center gap-4">
                    <div className="p-3 bg-blue-50 rounded-2xl">
                        <Users className="text-blue-600" size={24} />
                    </div>
                    <div>
                        <h2 className="text-xl font-black text-gray-900 dark:text-white leading-none">Voucher Database</h2>
                        <p className="text-gray-400 text-[10px] mt-1 font-bold uppercase tracking-widest">{users.length} Total Records</p>
                    </div>
                </div>

                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                    <div className="relative group flex-1 sm:w-64">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 transition-colors group-focus-within:text-blue-500" size={18} />
                        <input
                            type="text"
                            placeholder="Search vouchers..."
                            value={userSearch}
                            onChange={(e) => setUserSearch(e.target.value)}
                            className="w-full bg-gray-50 dark:bg-gray-700 border border-transparent focus:border-blue-500/30 focus:bg-white dark:focus:bg-gray-800 rounded-2xl py-2.5 pl-12 pr-4 text-sm font-bold text-gray-700 dark:text-gray-200 outline-none transition-all shadow-inner"
                        />
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={handleExportCSV}
                            className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 px-4 py-2.5 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-all active:scale-95"
                        >
                            <Download size={16} />
                            Export
                        </button>

                        <button
                            onClick={handleCleanupExpired}
                            className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-900/30 px-4 py-2.5 rounded-2xl text-[10px] font-black uppercase tracking-widest text-red-600 hover:bg-red-100 transition-all active:scale-95"
                        >
                            <Trash2 size={16} />
                            Cleanup Expired
                        </button>
                    </div>
                </div>
            </div>
            {/* Search status indicator */}
            {userSearch.trim() && (
                <div className="px-6 pt-3">
                    {isSearching ? (
                        <span className="text-[10px] font-black uppercase text-blue-500 tracking-widest animate-pulse">Searching router...</span>
                    ) : searchResults.length > 0 ? (
                        <span className="text-[10px] font-black uppercase text-emerald-500 tracking-widest">{searchResults.length} result(s) found on router</span>
                    ) : (
                        <span className="text-[10px] font-black uppercase text-gray-400 tracking-widest">No results in first {users.length} vouchers — searched router directly</span>
                    )}
                </div>
            )}
            <div className="overflow-hidden">
                <ResponsiveTable
                    data={searchResults.length > 0 ? searchResults : users.filter(u => u.name.toLowerCase().includes(userSearch.toLowerCase()) || (u.comment || '').toLowerCase().includes(userSearch.toLowerCase()))}
                    columns={[
                        {
                            header: 'Identity',
                            accessor: 'name',
                            render: (u) => (
                                <div>
                                    <div className="font-bold text-gray-900 dark:text-white text-sm flex items-center gap-2">
                                        {u.name}
                                        {u.comment && <span className="text-[8px] bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 px-1.5 py-0.5 rounded uppercase tracking-tighter">Batch: {u.comment}</span>}
                                    </div>
                                    <div className="text-[10px] text-gray-400 font-mono tracking-tighter">PWD: {u.password}</div>
                                </div>
                            )
                        },
                        {
                            header: 'Profile & Limits',
                            accessor: 'profile',
                            render: (u) => (
                                <div className="flex flex-col gap-1">
                                    <span className="max-w-fit px-3 py-1 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 rounded-lg text-[10px] font-black uppercase whitespace-nowrap">{u.profile}</span>
                                    {(u.limit_uptime || u.limit_bytes_total) && (
                                        <div className="text-[8px] text-gray-400 font-bold uppercase tracking-widest whitespace-nowrap">
                                            {u.limit_uptime && <span>Time: {u.limit_uptime}</span>}
                                            {u.limit_bytes_total > 0 && <span> • Data: {(u.limit_bytes_total / 1024 / 1024).toFixed(0)}MB</span>}
                                        </div>
                                    )}
                                </div>
                            )
                        },
                        {
                            header: 'Current Usage',
                            accessor: 'bytes_in',
                            render: (u) => (
                                <div>
                                    <div className="text-xs font-bold text-gray-700 dark:text-gray-200 whitespace-nowrap">{(u.bytes_in / 1024 / 1024).toFixed(1)} MB In</div>
                                    <div className="text-[10px] text-gray-400 font-medium whitespace-nowrap">{u.uptime || '0s'} Uptime</div>
                                </div>
                            )
                        },
                        {
                            header: 'Actions',
                            accessor: 'actions',
                            render: (u) => (
                                <div className="text-right flex items-center justify-end gap-2">
                                    {u.comment && (
                                        <button
                                            onClick={() => handleBulkDeleteByComment(u.comment)}
                                            className="text-orange-500 hover:text-orange-700 font-black text-[10px] uppercase tracking-widest hover:underline px-2 py-1 bg-orange-50 dark:bg-orange-900/20 rounded-lg whitespace-nowrap"
                                            title={`Delete all users in batch ${u.comment}`}
                                        >
                                            Del Batch
                                        </button>
                                    )}
                                    <button onClick={() => handleDelete(u.name)} className="text-red-500 hover:text-red-700 font-black text-[10px] uppercase tracking-widest hover:underline px-3 py-1.5 bg-red-50 dark:bg-red-900/20 rounded-lg whitespace-nowrap">
                                        Revoke
                                    </button>
                                </div>
                            )
                        }
                    ]}
                    renderCard={(u) => (
                        <div className="flex flex-col gap-3">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <Users size={16} className="text-blue-500" />
                                    <span className="font-bold text-gray-900 dark:text-white text-sm">{u.name}</span>
                                </div>
                                <span className="px-2 py-0.5 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 rounded-md text-[10px] font-black uppercase text-center">{u.profile}</span>
                            </div>
                            <div className="grid grid-cols-2 gap-2 text-xs text-gray-500 dark:text-gray-400">
                                <div className="bg-gray-50 dark:bg-gray-700/50 p-2 rounded-lg">
                                    <div className="text-[8px] uppercase font-bold text-gray-400">Password</div>
                                    <div className="font-mono font-bold text-gray-700 dark:text-gray-200">{u.password}</div>
                                </div>
                                <div className="bg-gray-50 dark:bg-gray-700/50 p-2 rounded-lg">
                                    <div className="text-[8px] uppercase font-bold text-gray-400">Usage</div>
                                    <div className="font-mono font-bold text-gray-700 dark:text-gray-200">{(u.bytes_in / 1024 / 1024).toFixed(1)} MB</div>
                                </div>
                            </div>
                            {(u.comment || u.limit_uptime || u.limit_bytes_total) && (
                                <div className="bg-blue-50/50 dark:bg-blue-900/20 p-2 rounded-lg text-[8px] font-bold text-gray-500 dark:text-gray-400 uppercase tracking-widest flex flex-wrap gap-2">
                                    {u.comment && <div className="bg-white dark:bg-gray-700 px-1.5 py-0.5 rounded shadow-sm border border-blue-100 dark:border-blue-900/30">Batch: {u.comment}</div>}
                                    {u.limit_uptime && <div className="bg-white dark:bg-gray-700 px-1.5 py-0.5 rounded shadow-sm border border-blue-100 dark:border-blue-900/30">Limit: {u.limit_uptime}</div>}
                                </div>
                            )}
                            <div className="flex gap-2 border-t pt-3 mt-1">
                                {u.comment && (
                                    <button onClick={() => handleBulkDeleteByComment(u.comment)} className="flex-1 text-center text-orange-500 font-bold text-[10px] uppercase bg-orange-50 dark:bg-orange-900/20 py-2 rounded-lg">Delete Batch</button>
                                )}
                                <button onClick={() => handleDelete(u.name)} className="flex-1 text-center text-red-500 font-bold text-[10px] uppercase bg-red-50 dark:bg-red-900/20 py-2 rounded-lg">Revoke Token</button>
                            </div>
                        </div>
                    )}
                    emptyMessage="Voucher database is empty."
                />
            </div>
        </div>
    );
}

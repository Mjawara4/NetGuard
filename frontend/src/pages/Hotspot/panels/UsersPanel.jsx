import React from 'react';
import { Download, Search, Trash2, Users } from 'lucide-react';
import ResponsiveTable from '../../../components/ResponsiveTable';
import { bandFor } from '../profileBand';

export default function UsersPanel({ users, userSearch, setUserSearch, searchResults, isSearching, handleDelete, handleExportCSV, handleCleanupExpired, handleBulkDeleteByComment }) {
    return (
        <div className="bg-white dark:bg-ink-800 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="p-6 sm:p-8 border-b border-ink-200 dark:border-ink-700 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                <div className="flex items-center gap-4">
                    <div className="p-3 bg-signal-600/10 rounded-lg">
                        <Users className="text-signal-600 dark:text-signal-300" size={24} />
                    </div>
                    <div>
                        <h2 className="text-xl font-semibold text-ink-900 dark:text-ink-50 leading-none">Voucher Database</h2>
                        <p className="text-ink-500 dark:text-ink-400 text-xs mt-1 font-medium">{users.length} total records</p>
                    </div>
                </div>

                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                    <div className="relative group flex-1 sm:w-64">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-ink-500 transition-colors group-focus-within:text-signal-600 dark:text-ink-400" size={18} />
                        <input
                            type="text"
                            placeholder="Search vouchers..."
                            value={userSearch}
                            onChange={(e) => setUserSearch(e.target.value)}
                            className="placeholder:text-ink-500 dark:placeholder:text-ink-400 w-full bg-ink-50 dark:bg-ink-800 border border-transparent focus:border-signal-500/30 focus:bg-white dark:focus:bg-ink-800 rounded-lg py-2.5 pl-12 pr-4 text-sm font-bold text-ink-900 dark:text-ink-100 outline-none transition-all shadow-inner"
                        />
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={handleExportCSV}
                            className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-white dark:bg-ink-800 border border-ink-200 dark:border-ink-700 px-4 py-2.5 rounded-lg text-xs font-semibold text-ink-500 dark:text-ink-100 hover:bg-ink-50 dark:hover:bg-ink-700 transition-all active:scale-95"
                        >
                            <Download size={16} />
                            Export
                        </button>

                        <button
                            onClick={handleCleanupExpired}
                            className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-down/10 dark:bg-down/20 border border-down/20 dark:border-down/30 px-4 py-2.5 rounded-lg text-xs font-semibold text-down dark:text-ink-100 hover:bg-down/20 transition-all active:scale-95"
                        >
                            <Trash2 size={16} />
                            Cleanup expired
                        </button>
                    </div>
                </div>
            </div>
            {/* Search status indicator */}
            {userSearch.trim() && (
                <div className="px-6 pt-3">
                    {isSearching ? (
                        <span className="text-xs font-semibold text-signal-600 dark:text-signal-300 animate-pulse">Searching router...</span>
                    ) : searchResults.length > 0 ? (
                        <span className="text-xs font-semibold text-up dark:text-ink-100">{searchResults.length} result(s) found on router</span>
                    ) : (
                        <span className="text-xs font-medium text-ink-500 dark:text-ink-400">No results in first {users.length} vouchers — searched router directly</span>
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
                                    <div className="font-bold text-ink-900 dark:text-ink-50 text-sm flex items-center gap-2">
                                        {u.name}
                                        {u.comment && <span className="text-xs font-medium bg-ink-100 dark:bg-ink-800 text-ink-900 dark:text-ink-400 px-1.5 py-0.5 rounded">Book: {u.comment}</span>}
                                    </div>
                                    <div className="text-xs text-ink-500 dark:text-ink-400 font-mono">Pwd: {u.password}</div>
                                </div>
                            )
                        },
                        {
                            header: 'Profile & Limits',
                            accessor: 'profile',
                            render: (u) => (
                                <div className="flex flex-col gap-1">
                                    <span className="max-w-fit inline-flex items-center gap-1.5 px-3 py-1 bg-up/10 dark:bg-up/20 text-ink-900 dark:text-ink-50 rounded-lg text-xs font-semibold whitespace-nowrap">
                                        <span className={`w-[5px] h-3 rounded-full shrink-0 ${bandFor(u.profile)}`} aria-hidden="true"></span>
                                        {u.profile}
                                    </span>
                                    {(u.limit_uptime || u.limit_bytes_total) && (
                                        <div className="text-xs text-ink-500 dark:text-ink-400 font-medium whitespace-nowrap">
                                            {u.limit_uptime && <span className="font-mono">Time: {u.limit_uptime}</span>}
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
                                    <div className="text-xs font-bold text-ink-900 dark:text-ink-100 whitespace-nowrap">{(u.bytes_in / 1024 / 1024).toFixed(1)} MB In</div>
                                    <div className="text-xs text-ink-500 dark:text-ink-400 font-mono">{u.uptime || '0s'} uptime</div>
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
                                            className="text-ink-900 dark:text-ink-50 font-semibold text-xs hover:underline px-2 py-1 bg-warn/10 dark:bg-warn/20 rounded-lg whitespace-nowrap"
                                            title={`Delete every voucher in book ${u.comment}`}
                                        >
                                            Del book
                                        </button>
                                    )}
                                    <button onClick={() => handleDelete(u.name)} className="text-down dark:text-ink-100 font-semibold text-xs hover:underline px-3 py-1.5 bg-down/10 dark:bg-down/20 rounded-lg whitespace-nowrap">
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
                                    <Users size={16} className="text-signal-600 dark:text-signal-300" />
                                    <span className="font-bold text-ink-900 dark:text-ink-50 text-sm">{u.name}</span>
                                </div>
                                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 bg-up/10 dark:bg-up/20 text-ink-900 dark:text-ink-50 rounded-md text-xs font-semibold text-center">
                                    <span className={`w-[5px] h-3 rounded-full shrink-0 ${bandFor(u.profile)}`} aria-hidden="true"></span>
                                    {u.profile}
                                </span>
                            </div>
                            <div className="grid grid-cols-2 gap-2 text-xs text-ink-500 dark:text-ink-400">
                                <div className="bg-ink-50 dark:bg-ink-800/50 p-2 rounded-lg">
                                    <div className="text-xs font-medium text-ink-500 dark:text-ink-400">Password</div>
                                    <div className="font-mono font-bold text-ink-900 dark:text-ink-100">{u.password}</div>
                                </div>
                                <div className="bg-ink-50 dark:bg-ink-800/50 p-2 rounded-lg">
                                    <div className="text-xs font-medium text-ink-500 dark:text-ink-400">Usage</div>
                                    <div className="font-mono font-bold text-ink-900 dark:text-ink-100">{(u.bytes_in / 1024 / 1024).toFixed(1)} MB</div>
                                </div>
                            </div>
                            {(u.comment || u.limit_uptime || u.limit_bytes_total) && (
                                <div className="bg-signal-600/5 dark:bg-signal-600/20 p-2 rounded-lg text-xs font-medium text-ink-900 dark:text-ink-50 flex flex-wrap gap-2">
                                    {u.comment && <div className="bg-white dark:bg-ink-800 px-1.5 py-0.5 rounded shadow-sm border border-signal-600/20 dark:border-signal-600/30">Book: {u.comment}</div>}
                                    {u.limit_uptime && <div className="bg-white dark:bg-ink-800 px-1.5 py-0.5 rounded shadow-sm border border-signal-600/20 dark:border-signal-600/30">Limit: {u.limit_uptime}</div>}
                                </div>
                            )}
                            <div className="flex gap-2 border-t border-ink-200 dark:border-ink-700 pt-3 mt-1">
                                {u.comment && (
                                    <button onClick={() => handleBulkDeleteByComment(u.comment)} className="flex-1 text-center text-ink-900 dark:text-ink-50 font-semibold text-xs bg-warn/10 dark:bg-warn/20 py-2 rounded-lg">Delete book</button>
                                )}
                                <button onClick={() => handleDelete(u.name)} className="flex-1 text-center text-down dark:text-ink-100 font-semibold text-xs bg-down/10 dark:bg-down/20 py-2 rounded-lg">Revoke token</button>
                            </div>
                        </div>
                    )}
                    emptyMessage="Voucher database is empty."
                />
            </div>
        </div>
    );
}

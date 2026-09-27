import React from 'react';
import { Activity, Clock, FileText, Plus, Search, Users } from 'lucide-react';
import ResponsiveTable from '../../../components/ResponsiveTable';

export default function ReportsPanel({ reportData, filteredReports, reportSearch, setReportSearch, reportPeriod, setReportPeriod, reportStartDate, setReportStartDate, reportEndDate, setReportEndDate, reportPage, setReportPage, selectedDevice }) {
    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Stats Controls */}
            <div className="flex flex-col md:flex-row gap-4 mb-6">
                <div className="flex-[2] bg-white dark:bg-ink-800 p-4 rounded-lg border border-ink-200 dark:border-ink-700 shadow-sm flex flex-col sm:flex-row items-center gap-4">
                    <div className="relative flex-1 w-full">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-ink-500 dark:text-ink-400" size={18} />
                        <input
                            type="text"
                            placeholder="Search sales history..."
                            value={reportSearch}
                            onChange={(e) => setReportSearch(e.target.value)}
                            className="placeholder:text-ink-500 dark:placeholder:text-ink-400 w-full bg-ink-50 dark:bg-ink-800 border-none rounded-lg py-2.5 pl-12 pr-4 text-sm font-bold text-ink-900 dark:text-ink-100 outline-none focus:ring-2 focus:ring-signal-500/20"
                        />
                    </div>
                    <div className="flex items-center gap-2 w-full sm:w-auto overflow-x-auto pb-2 sm:pb-0">
                        {['', 'day', 'week', 'month'].map((p) => (
                            <button
                                key={p}
                                onClick={() => { setReportPeriod(p); setReportStartDate(''); setReportEndDate(''); }}
                                className={`px-4 py-2 rounded-md text-xs font-bold transition-all ${reportPeriod === p ? 'bg-signal-600 text-white shadow-lg' : 'bg-ink-50 dark:bg-ink-800 text-ink-500 dark:text-ink-400 hover:bg-ink-100 dark:hover:bg-ink-700'}`}
                            >
                                {p || 'All'}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="flex-1 bg-white dark:bg-ink-800 p-4 rounded-lg border border-ink-200 dark:border-ink-700 shadow-sm flex items-center gap-3">
                    <Clock className="text-ink-500 dark:text-ink-400" size={18} />
                    <input
                        type="date"
                        value={reportStartDate}
                        onChange={(e) => { setReportStartDate(e.target.value); setReportPeriod(''); }}
                        className="bg-ink-50 dark:bg-ink-800 border-none rounded-md py-2 px-3 text-xs font-bold text-ink-900 dark:text-ink-100 outline-none focus:ring-2 focus:ring-signal-500/20"
                    />
                    <span className="text-ink-500 dark:text-ink-400">-</span>
                    <input
                        type="date"
                        value={reportEndDate}
                        onChange={(e) => { setReportEndDate(e.target.value); setReportPeriod(''); }}
                        className="bg-ink-50 dark:bg-ink-800 border-none rounded-md py-2 px-3 text-xs font-bold text-ink-900 dark:text-ink-100 outline-none focus:ring-2 focus:ring-signal-500/20"
                    />
                </div>
            </div>

            {/* Revenue Summary Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {Object.entries(reportData.total_revenue || {}).map(([curr, amount]) => (
                    <div key={curr} className="bg-white dark:bg-ink-800 p-6 rounded-lg border border-ink-200 dark:border-ink-700 shadow-sm flex items-center justify-between group hover:border-up/40 transition-all">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-up/10 dark:bg-up/20 text-up dark:text-ink-100 rounded-lg group-hover:scale-110 transition-transform">
                                <Activity size={24} />
                            </div>
                            <div>
                                <p className="text-xs font-medium text-ink-500 dark:text-ink-400">Total Profit ({curr})</p>
                                <p className="text-2xl font-bold text-ink-900 dark:text-ink-50">{amount.toLocaleString()} <span className="text-xs text-up dark:text-ink-100 ml-1">{curr}</span></p>
                            </div>
                        </div>
                    </div>
                ))}
                <div className="bg-white dark:bg-ink-800 p-6 rounded-lg border border-ink-200 dark:border-ink-700 shadow-sm flex items-center justify-between group hover:border-signal-600/40 transition-all">
                    <div className="flex items-center gap-3">
                        <div className="p-3 bg-signal-600/10 dark:bg-signal-600/20 text-signal-600 dark:text-signal-300 rounded-lg group-hover:scale-110 transition-transform">
                            <Users size={24} />
                        </div>
                        <div>
                            <p className="text-xs font-medium text-ink-500 dark:text-ink-400">Total Vouchers</p>
                            <p className="text-2xl font-bold text-ink-900 dark:text-ink-50">{reportData.total_sold}</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Mikhmon Breakdown Aggregates */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Daily Sales Breakdown */}
                <div className="bg-white dark:bg-ink-800 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700 overflow-hidden">
                    <div className="p-6 border-b border-ink-200 dark:border-ink-700 bg-ink-50/50 dark:bg-ink-800/50">
                        <h3 className="font-semibold text-ink-900 dark:text-ink-50 text-xs flex items-center gap-2">
                            <Clock size={16} className="text-signal-600 dark:text-signal-300" />
                            Daily Sales Summary
                        </h3>
                    </div>
                    <div className="max-h-[300px] overflow-y-auto">
                        <table className="w-full text-left border-collapse">
                            <thead className="sticky top-0 bg-white dark:bg-ink-800 shadow-sm z-10">
                                <tr className="bg-ink-50/50 dark:bg-ink-800/50">
                                    <th className="px-6 py-3 text-xs font-medium text-ink-500 dark:text-ink-400">Date</th>
                                    <th className="px-6 py-3 text-xs font-medium text-ink-500 dark:text-ink-400">Qty</th>
                                    <th className="px-6 py-3 text-xs font-medium text-ink-500 dark:text-ink-400">Revenue</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-ink-200 dark:divide-ink-700">
                                {(reportData.daily_stats || []).map((day) => (
                                    <tr key={day.date} className="hover:bg-ink-50 dark:hover:bg-ink-700/50 transition-colors">
                                        <td className="px-6 py-4 text-xs font-bold text-ink-900 dark:text-ink-50 font-mono">{day.date}</td>
                                        <td className="px-6 py-4">
                                            <span className="bg-signal-600/10 dark:bg-signal-600/20 text-ink-900 dark:text-ink-50 px-2 py-1 rounded-lg text-xs font-bold">{day.count}</span>
                                        </td>
                                        <td className="px-6 py-4 text-xs font-bold text-up dark:text-ink-100">
                                            {Object.entries(day.revenue).map(([curr, amt]) => (
                                                <div key={curr}>{amt.toLocaleString()} {curr}</div>
                                            ))}
                                        </td>
                                    </tr>
                                ))}
                                {(!reportData.daily_stats || reportData.daily_stats.length === 0) && (
                                    <tr>
                                        <td colSpan="3" className="px-6 py-12 text-center text-xs text-ink-500 dark:text-ink-400 font-medium italic">No daily history for this period.</td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Profile Performance */}
                <div className="bg-white dark:bg-ink-800 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700 overflow-hidden">
                    <div className="p-6 border-b border-ink-200 dark:border-ink-700 bg-ink-50/50 dark:bg-ink-800/50">
                        <h3 className="font-semibold text-ink-900 dark:text-ink-50 text-xs flex items-center gap-2">
                            <Activity size={16} className="text-up dark:text-ink-100" />
                            Best Selling Profiles
                        </h3>
                    </div>
                    <div className="max-h-[300px] overflow-y-auto">
                        <table className="w-full text-left border-collapse">
                            <thead className="sticky top-0 bg-white dark:bg-ink-800 shadow-sm z-10">
                                <tr className="bg-ink-50/50 dark:bg-ink-800/50">
                                    <th className="px-6 py-3 text-xs font-medium text-ink-500 dark:text-ink-400">Profile</th>
                                    <th className="px-6 py-3 text-xs font-medium text-ink-500 dark:text-ink-400">Sold</th>
                                    <th className="px-6 py-3 text-xs font-medium text-ink-500 dark:text-ink-400">Total Income</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-ink-200 dark:divide-ink-700">
                                {(reportData.profile_stats || []).map((prof) => (
                                    <tr key={prof.profile} className="hover:bg-ink-50 dark:hover:bg-ink-700/50 transition-colors">
                                        <td className="px-6 py-4 text-xs font-bold text-ink-900 dark:text-ink-50 font-mono">{prof.profile}</td>
                                        <td className="px-6 py-4">
                                            <span className="bg-signal-600/10 dark:bg-signal-600/20 text-ink-900 dark:text-ink-50 px-2 py-1 rounded-lg text-xs font-bold">{prof.count}</span>
                                        </td>
                                        <td className="px-6 py-4 text-xs font-bold text-up dark:text-ink-100">
                                            {Object.entries(prof.revenue).map(([curr, amt]) => (
                                                <div key={curr}>{amt.toLocaleString()} {curr}</div>
                                            ))}
                                        </td>
                                    </tr>
                                ))}
                                {(!reportData.profile_stats || reportData.profile_stats.length === 0) && (
                                    <tr>
                                        <td colSpan="3" className="px-6 py-12 text-center text-xs text-ink-500 dark:text-ink-400 font-medium italic">No profile sales data.</td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* Detailed Records List */}
            <div className="bg-white dark:bg-ink-800 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700 overflow-hidden">
                <div className="p-6 border-b border-ink-200 dark:border-ink-700 flex justify-between items-center bg-ink-50/50 dark:bg-ink-800/50">
                    <h3 className="font-semibold text-ink-900 dark:text-ink-50 text-xs flex items-center gap-2">
                        <FileText size={16} className="text-ink-500 dark:text-ink-400" />
                        Full Transaction Logs
                    </h3>
                    <div className="flex items-center gap-2">
                        <button
                            disabled={reportPage === 1}
                            onClick={() => setReportPage(p => p - 1)}
                            className="p-2 rounded-md bg-white dark:bg-ink-800 border border-ink-200 dark:border-ink-700 hover:bg-ink-50 dark:hover:bg-ink-700 disabled:opacity-30 shadow-sm"
                        >
                            <Plus size={16} className="rotate-45" />
                        </button>
                        <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Page {reportPage} / {Math.max(1, Math.ceil(filteredReports.length / 30))}</span>
                        <button
                            disabled={reportPage * 30 >= filteredReports.length}
                            onClick={() => setReportPage(p => p + 1)}
                            className="p-2 rounded-md bg-white dark:bg-ink-800 border border-ink-200 dark:border-ink-700 hover:bg-ink-50 dark:hover:bg-ink-700 disabled:opacity-30 shadow-sm"
                        >
                            <Plus size={16} />
                        </button>
                    </div>
                </div>
                <ResponsiveTable
                    data={filteredReports.slice((reportPage - 1) * 30, reportPage * 30)}
                    columns={[
                        {
                            header: 'Code',
                            accessor: 'username',
                            render: (r) => <div className="font-bold text-ink-900 dark:text-ink-50 text-sm font-mono">{r.username}</div>
                        },
                        {
                            header: 'Profile',
                            accessor: 'profile',
                            render: (r) => <span className="px-2 py-0.5 bg-signal-600/10 dark:bg-signal-600/20 text-ink-900 dark:text-ink-50 rounded-lg text-xs font-semibold">{r.profile}</span>
                        },
                        {
                            header: 'Price',
                            accessor: 'price',
                            render: (r) => <div className="font-bold text-up dark:text-ink-100 text-xs">{r.price.toLocaleString()} {r.currency}</div>
                        },
                        {
                            header: 'Time',
                            accessor: 'uptime',
                            render: (r) => <div className="text-xs font-bold font-mono text-signal-600 dark:text-signal-300">{r.uptime}</div>
                        },
                        {
                            header: 'Sold Date',
                            accessor: 'created_at',
                            render: (r) => <div className="text-xs font-medium font-mono text-ink-500 dark:text-ink-400">{r.created_at}</div>
                        }
                    ]}
                    renderCard={(r) => (
                        <div className="flex justify-between items-center p-2">
                            <div>
                                <p className="font-bold text-ink-900 dark:text-ink-50 text-sm font-mono">{r.username}</p>
                                <p className="text-xs font-medium text-ink-500 dark:text-ink-400">{r.profile || '—'}{(r.uptime && r.uptime !== '0s') ? ` • ${r.uptime}` : ''}</p>
                            </div>
                            <div className="text-right">
                                <p className="font-bold text-up dark:text-ink-100">{r.price.toLocaleString()} {r.currency}</p>
                                <p className="text-xs font-medium text-ink-500 dark:text-ink-400">{r.created_at}</p>
                            </div>
                        </div>
                    )}
                    emptyMessage="No sales recorded on this router."
                />
            </div>

            {/* Real-time Setup Guide */}
            <div className="bg-signal-600/5 dark:bg-signal-600/20 p-6 rounded-lg border border-signal-600/20 dark:border-signal-600/30 space-y-4">
                <div className="flex items-center gap-3 text-ink-900 dark:text-ink-50">
                    <Activity size={20} />
                    <h4 className="font-semibold text-xs">Real-time Recording (Recommended)</h4>
                </div>
                <p className="text-xs font-medium text-ink-900 dark:text-ink-50 leading-relaxed">
                    Add this script to your MikroTik Hotspot Server's <strong>On Login</strong> field. It records the sale the moment a user logs in, with the correct profile and price.
                </p>
                <div className="bg-ink-900 rounded-lg p-4 relative group">
                    <pre className="text-xs text-ink-100 font-mono overflow-x-auto whitespace-pre">
                        {`:local userProfile [/ip hotspot user get [find name=$user] profile];\n:local postData ("{\\"device_id\\": \\"${selectedDevice}\\", \\"username\\": \\"" . $user . "\\", \\"profile\\": \\"" . $userProfile . "\\", \\"comment\\": \\"" . $comment . "\\"}");\n/tool fetch url="https://app.netguard.fun/api/v1/hotspot/record-sale" http-method=post http-data=$postData http-header-field="Content-Type: application/json" keep-result=no;`}
                    </pre>
                </div>
                <p className="text-xs text-ink-500 dark:text-ink-400 font-medium leading-relaxed">
                    ⚠️ The <code className="bg-ink-100 dark:bg-ink-800 text-ink-900 dark:text-ink-100 px-1 rounded font-mono">$profile</code> variable is not reliably available in MikroTik login scripts — the first line explicitly looks up the user's profile from the router's user table to guarantee accuracy.
                </p>
            </div>
        </div>
    );
}

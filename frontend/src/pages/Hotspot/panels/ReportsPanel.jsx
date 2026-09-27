import React from 'react';
import { Activity, Clock, FileText, Plus, Search, Users } from 'lucide-react';
import ResponsiveTable from '../../../components/ResponsiveTable';

export default function ReportsPanel({ reportData, filteredReports, reportSearch, setReportSearch, reportPeriod, setReportPeriod, reportStartDate, setReportStartDate, reportEndDate, setReportEndDate, reportPage, setReportPage, selectedDevice }) {
    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Stats Controls */}
            <div className="flex flex-col md:flex-row gap-4 mb-6">
                <div className="flex-[2] bg-white dark:bg-gray-800 p-4 rounded-3xl border border-gray-100 dark:border-gray-700 shadow-sm flex flex-col sm:flex-row items-center gap-4">
                    <div className="relative flex-1 w-full">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                        <input
                            type="text"
                            placeholder="Search sales history..."
                            value={reportSearch}
                            onChange={(e) => setReportSearch(e.target.value)}
                            className="w-full bg-gray-50 dark:bg-gray-700 border-none rounded-2xl py-2.5 pl-12 pr-4 text-sm font-bold text-gray-700 dark:text-gray-200 outline-none focus:ring-2 focus:ring-blue-500/20"
                        />
                    </div>
                    <div className="flex items-center gap-2 w-full sm:w-auto overflow-x-auto pb-2 sm:pb-0">
                        {['', 'day', 'week', 'month'].map((p) => (
                            <button
                                key={p}
                                onClick={() => { setReportPeriod(p); setReportStartDate(''); setReportEndDate(''); }}
                                className={`px-4 py-2 rounded-xl text-xs font-black uppercase transition-all ${reportPeriod === p ? 'bg-blue-600 text-white shadow-lg shadow-blue-100' : 'bg-gray-50 dark:bg-gray-700 text-gray-400 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-600'}`}
                            >
                                {p || 'All'}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="flex-1 bg-white dark:bg-gray-800 p-4 rounded-3xl border border-gray-100 dark:border-gray-700 shadow-sm flex items-center gap-3">
                    <Clock className="text-gray-400" size={18} />
                    <input
                        type="date"
                        value={reportStartDate}
                        onChange={(e) => { setReportStartDate(e.target.value); setReportPeriod(''); }}
                        className="bg-gray-50 dark:bg-gray-700 border-none rounded-xl py-2 px-3 text-[10px] font-black text-gray-700 dark:text-gray-200 outline-none focus:ring-2 focus:ring-blue-500/20"
                    />
                    <span className="text-gray-300 dark:text-gray-600">-</span>
                    <input
                        type="date"
                        value={reportEndDate}
                        onChange={(e) => { setReportEndDate(e.target.value); setReportPeriod(''); }}
                        className="bg-gray-50 dark:bg-gray-700 border-none rounded-xl py-2 px-3 text-[10px] font-black text-gray-700 dark:text-gray-200 outline-none focus:ring-2 focus:ring-blue-500/20"
                    />
                </div>
            </div>

            {/* Revenue Summary Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {Object.entries(reportData.total_revenue || {}).map(([curr, amount]) => (
                    <div key={curr} className="bg-white dark:bg-gray-800 p-6 rounded-3xl border border-gray-100 dark:border-gray-700 shadow-sm flex items-center justify-between group hover:border-emerald-200 transition-all">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-emerald-50 text-emerald-600 rounded-2xl group-hover:scale-110 transition-transform">
                                <Activity size={24} />
                            </div>
                            <div>
                                <p className="text-[10px] font-black uppercase text-gray-400">Total Profit ({curr})</p>
                                <p className="text-2xl font-black text-gray-900 dark:text-white">{amount.toLocaleString()} <span className="text-xs text-emerald-600 ml-1">{curr}</span></p>
                            </div>
                        </div>
                    </div>
                ))}
                <div className="bg-white dark:bg-gray-800 p-6 rounded-3xl border border-gray-100 dark:border-gray-700 shadow-sm flex items-center justify-between group hover:border-blue-200 transition-all">
                    <div className="flex items-center gap-3">
                        <div className="p-3 bg-blue-50 text-blue-600 rounded-2xl group-hover:scale-110 transition-transform">
                            <Users size={24} />
                        </div>
                        <div>
                            <p className="text-[10px] font-black uppercase text-gray-400">Total Vouchers</p>
                            <p className="text-2xl font-black text-gray-900 dark:text-white">{reportData.total_sold}</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Mikhmon Breakdown Aggregates */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Daily Sales Breakdown */}
                <div className="bg-white dark:bg-gray-800 rounded-[32px] shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
                    <div className="p-6 border-b border-gray-50 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-700/50">
                        <h3 className="font-black text-gray-900 dark:text-white uppercase text-[10px] tracking-widest flex items-center gap-2">
                            <Clock size={16} className="text-blue-500" />
                            Daily Sales Summary
                        </h3>
                    </div>
                    <div className="max-h-[300px] overflow-y-auto">
                        <table className="w-full text-left border-collapse">
                            <thead className="sticky top-0 bg-white dark:bg-gray-700 shadow-sm z-10">
                                <tr className="bg-gray-50/50 dark:bg-gray-700/50">
                                    <th className="px-6 py-3 text-[9px] font-black text-gray-400 uppercase tracking-widest">Date</th>
                                    <th className="px-6 py-3 text-[9px] font-black text-gray-400 uppercase tracking-widest">Qty</th>
                                    <th className="px-6 py-3 text-[9px] font-black text-gray-400 uppercase tracking-widest">Revenue</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-50 dark:divide-gray-700">
                                {(reportData.daily_stats || []).map((day) => (
                                    <tr key={day.date} className="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                                        <td className="px-6 py-4 text-xs font-black text-gray-900 dark:text-white">{day.date}</td>
                                        <td className="px-6 py-4">
                                            <span className="bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 px-2 py-1 rounded-lg text-xs font-black">{day.count}</span>
                                        </td>
                                        <td className="px-6 py-4 text-xs font-black text-emerald-600">
                                            {Object.entries(day.revenue).map(([curr, amt]) => (
                                                <div key={curr}>{amt.toLocaleString()} {curr}</div>
                                            ))}
                                        </td>
                                    </tr>
                                ))}
                                {(!reportData.daily_stats || reportData.daily_stats.length === 0) && (
                                    <tr>
                                        <td colSpan="3" className="px-6 py-12 text-center text-xs text-gray-400 font-bold italic">No daily history for this period.</td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Profile Performance */}
                <div className="bg-white dark:bg-gray-800 rounded-[32px] shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
                    <div className="p-6 border-b border-gray-50 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-700/50">
                        <h3 className="font-black text-gray-900 dark:text-white uppercase text-[10px] tracking-widest flex items-center gap-2">
                            <Activity size={16} className="text-emerald-500" />
                            Best Selling Profiles
                        </h3>
                    </div>
                    <div className="max-h-[300px] overflow-y-auto">
                        <table className="w-full text-left border-collapse">
                            <thead className="sticky top-0 bg-white dark:bg-gray-700 shadow-sm z-10">
                                <tr className="bg-gray-50/50 dark:bg-gray-700/50">
                                    <th className="px-6 py-3 text-[9px] font-black text-gray-400 uppercase tracking-widest">Profile</th>
                                    <th className="px-6 py-3 text-[9px] font-black text-gray-400 uppercase tracking-widest">Sold</th>
                                    <th className="px-6 py-3 text-[9px] font-black text-gray-400 uppercase tracking-widest">Total Income</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-50 dark:divide-gray-700">
                                {(reportData.profile_stats || []).map((prof) => (
                                    <tr key={prof.profile} className="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                                        <td className="px-6 py-4 text-xs font-black text-gray-900 dark:text-white uppercase">{prof.profile}</td>
                                        <td className="px-6 py-4">
                                            <span className="bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400 px-2 py-1 rounded-lg text-xs font-black">{prof.count}</span>
                                        </td>
                                        <td className="px-6 py-4 text-xs font-black text-emerald-600">
                                            {Object.entries(prof.revenue).map(([curr, amt]) => (
                                                <div key={curr}>{amt.toLocaleString()} {curr}</div>
                                            ))}
                                        </td>
                                    </tr>
                                ))}
                                {(!reportData.profile_stats || reportData.profile_stats.length === 0) && (
                                    <tr>
                                        <td colSpan="3" className="px-6 py-12 text-center text-xs text-gray-400 font-bold italic">No profile sales data.</td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* Detailed Records List */}
            <div className="bg-white dark:bg-gray-800 rounded-[32px] shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
                <div className="p-6 border-b border-gray-50 dark:border-gray-700 flex justify-between items-center bg-gray-50/50 dark:bg-gray-700/50">
                    <h3 className="font-black text-gray-900 dark:text-white uppercase text-[10px] tracking-widest flex items-center gap-2">
                        <FileText size={16} className="text-gray-400" />
                        Full Transaction Logs
                    </h3>
                    <div className="flex items-center gap-2">
                        <button
                            disabled={reportPage === 1}
                            onClick={() => setReportPage(p => p - 1)}
                            className="p-2 rounded-xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-30 shadow-sm"
                        >
                            <Plus size={16} className="rotate-45" />
                        </button>
                        <span className="text-[10px] font-black text-gray-400 uppercase">Page {reportPage} / {Math.max(1, Math.ceil(filteredReports.length / 30))}</span>
                        <button
                            disabled={reportPage * 30 >= filteredReports.length}
                            onClick={() => setReportPage(p => p + 1)}
                            className="p-2 rounded-xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-30 shadow-sm"
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
                            render: (r) => <div className="font-black text-gray-900 dark:text-white text-sm">{r.username}</div>
                        },
                        {
                            header: 'Profile',
                            accessor: 'profile',
                            render: (r) => <span className="px-2 py-0.5 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-lg text-[9px] font-black uppercase">{r.profile}</span>
                        },
                        {
                            header: 'Price',
                            accessor: 'price',
                            render: (r) => <div className="font-black text-emerald-600 text-xs">{r.price.toLocaleString()} {r.currency}</div>
                        },
                        {
                            header: 'Time',
                            accessor: 'uptime',
                            render: (r) => <div className="text-[10px] font-bold text-blue-400">{r.uptime}</div>
                        },
                        {
                            header: 'Sold Date',
                            accessor: 'created_at',
                            render: (r) => <div className="text-[10px] font-bold text-gray-400 uppercase">{r.created_at}</div>
                        }
                    ]}
                    renderCard={(r) => (
                        <div className="flex justify-between items-center p-2">
                            <div>
                                <p className="font-black text-gray-900 dark:text-white uppercase text-sm">{r.username}</p>
                                <p className="text-[10px] font-bold text-gray-400 uppercase">{r.profile || '—'}{(r.uptime && r.uptime !== '0s') ? ` • ${r.uptime}` : ''}</p>
                            </div>
                            <div className="text-right">
                                <p className="font-black text-emerald-600">{r.price.toLocaleString()} {r.currency}</p>
                                <p className="text-[9px] font-bold text-gray-400 uppercase">{r.created_at}</p>
                            </div>
                        </div>
                    )}
                    emptyMessage="No sales recorded on this router."
                />
            </div>

            {/* Real-time Setup Guide */}
            <div className="bg-blue-50/50 dark:bg-blue-900/20 p-6 rounded-[32px] border border-blue-100/50 dark:border-blue-900/30 space-y-4">
                <div className="flex items-center gap-3 text-blue-600">
                    <Activity size={20} />
                    <h4 className="font-black uppercase text-xs tracking-widest">Real-time Recording (Recommended)</h4>
                </div>
                <p className="text-xs font-medium text-gray-600 dark:text-gray-300 leading-relaxed">
                    Add this script to your MikroTik Hotspot Server's <strong>On Login</strong> field. It records the sale the moment a user logs in, with the correct profile and price.
                </p>
                <div className="bg-gray-900 rounded-2xl p-4 relative group">
                    <pre className="text-[10px] text-emerald-400 font-mono overflow-x-auto whitespace-pre">
                        {`:local userProfile [/ip hotspot user get [find name=$user] profile];\n:local postData ("{\\"device_id\\": \\"${selectedDevice}\\", \\"username\\": \\"" . $user . "\\", \\"profile\\": \\"" . $userProfile . "\\", \\"comment\\": \\"" . $comment . "\\"}");\n/tool fetch url="https://app.netguard.fun/api/v1/hotspot/record-sale" http-method=post http-data=$postData http-header-field="Content-Type: application/json" keep-result=no;`}
                    </pre>
                </div>
                <p className="text-[10px] text-gray-400 dark:text-gray-500 font-medium leading-relaxed">
                    ⚠️ The <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">$profile</code> variable is not reliably available in MikroTik login scripts — the first line explicitly looks up the user's profile from the router's user table to guarantee accuracy.
                </p>
            </div>
        </div>
    );
}

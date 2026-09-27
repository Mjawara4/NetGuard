import React from 'react';
import { Printer, Trash2 } from 'lucide-react';

export default function BooksPanel({ batchHistory, handleReprint, handleBulkDeleteByComment }) {
    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Header */}
            <div className="flex items-center justify-between bg-white dark:bg-gray-800 p-6 rounded-3xl border border-gray-100 dark:border-gray-700 shadow-sm">
                <div>
                    <h2 className="text-xl font-black text-gray-900 dark:text-white">Batch History</h2>
                    <p className="text-gray-500 dark:text-gray-400 text-sm font-medium">Re-print or delete previously generated voucher batches.</p>
                </div>
                <div className="flex items-center gap-3">
                    <div className="text-right">
                        <div className="text-[10px] font-black uppercase text-gray-400 tracking-widest">Total Unused</div>
                        <div className="font-black text-emerald-600 text-lg">{batchHistory.reduce((s, b) => s + (b.count - b.used), 0)}</div>
                    </div>
                    <div className="bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 px-4 py-2 rounded-xl text-xs font-black uppercase tracking-widest">
                        {batchHistory.length} Batches
                    </div>
                </div>
            </div>

            {/* Batch Cards */}
            {batchHistory.length === 0 ? (
                <div className="bg-white dark:bg-gray-800 rounded-3xl border border-gray-100 dark:border-gray-700 p-12 text-center text-gray-400 text-sm font-bold">
                    No batches found. Generate vouchers from the Generator tab.
                </div>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {batchHistory.map((b) => {
                        const unused = b.count - b.used;
                        const usedPct = b.count > 0 ? Math.round((b.used / b.count) * 100) : 0;
                        return (
                            <div key={b.id} className="bg-white dark:bg-gray-800 rounded-[28px] border border-gray-100 dark:border-gray-700 shadow-sm p-5 flex flex-col gap-4">
                                {/* Batch name headline */}
                                <div className="flex items-start justify-between gap-2">
                                    <div>
                                        <div className="text-[9px] font-black uppercase text-gray-400 tracking-widest mb-0.5">Batch</div>
                                        <div className="text-base font-black text-gray-900 dark:text-white tracking-tight truncate max-w-[160px]">{b.displayName}</div>
                                        {/* Legacy rows have status: null (21 in production) and simply
                                            render without this badge, same as before this row existed. */}
                                        {b.status && (
                                            <span className={`inline-block mt-1 px-2 py-0.5 rounded-lg text-[8px] font-black uppercase tracking-wide ${
                                                b.status === 'complete' ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600' :
                                                b.status === 'failed' ? 'bg-red-50 dark:bg-red-900/20 text-red-600' :
                                                'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
                                            }`}>{b.status}</span>
                                        )}
                                    </div>
                                    <div className="text-right shrink-0">
                                        <span className="px-2.5 py-1 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-xl text-[10px] font-black uppercase tracking-wide block mb-1">{b.profile}</span>
                                        {b.timeLimit && <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded-lg text-[9px] font-black uppercase block">{b.timeLimit}</span>}
                                    </div>
                                </div>

                                {b.date && <div className="text-[9px] text-gray-400 dark:text-gray-500 font-bold -mt-2">{b.date}</div>}

                                {/* Counts */}
                                <div className="grid grid-cols-3 gap-2 text-center">
                                    <div className="bg-gray-50 dark:bg-gray-700/50 rounded-xl p-2">
                                        <div className="text-[9px] font-black uppercase text-gray-400">Total</div>
                                        <div className="font-black text-gray-900 dark:text-white text-lg leading-none mt-0.5">{b.count}</div>
                                    </div>
                                    <div className="bg-emerald-50 dark:bg-emerald-900/20 rounded-xl p-2">
                                        <div className="text-[9px] font-black uppercase text-emerald-500">Unused</div>
                                        <div className="font-black text-emerald-600 text-lg leading-none mt-0.5">{unused}</div>
                                    </div>
                                    <div className="bg-orange-50 dark:bg-orange-900/20 rounded-xl p-2">
                                        <div className="text-[9px] font-black uppercase text-orange-400">Used</div>
                                        <div className="font-black text-orange-500 text-lg leading-none mt-0.5">{b.used}</div>
                                    </div>
                                </div>

                                {/* Progress bar */}
                                <div>
                                    <div className="flex justify-between text-[9px] font-black uppercase text-gray-400 mb-1">
                                        <span>Usage</span><span>{usedPct}%</span>
                                    </div>
                                    <div className="w-full bg-gray-100 dark:bg-gray-700 rounded-full h-2">
                                        <div className="h-2 rounded-full bg-gradient-to-r from-blue-500 to-emerald-500 transition-all" style={{ width: `${usedPct}%` }} />
                                    </div>
                                </div>

                                {/* Actions */}
                                <div className="flex gap-2 pt-1">
                                    <button
                                        onClick={() => handleReprint(b)}
                                        className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white py-2.5 rounded-2xl font-black text-[10px] uppercase tracking-widest shadow-lg shadow-blue-100 dark:shadow-blue-900/20 transition-all active:scale-95"
                                    >
                                        <Printer size={13} /> Re-Print ({b.count})
                                    </button>
                                    <button
                                        onClick={() => handleBulkDeleteByComment(b.name)}
                                        className="p-2.5 bg-red-50 dark:bg-red-900/20 text-red-500 rounded-2xl hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors"
                                        title="Delete all vouchers in this batch"
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

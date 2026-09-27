import React from 'react';
import { Printer, Trash2 } from 'lucide-react';
import { bandFor } from '../profileBand';

export default function BooksPanel({ batchHistory, handleReprint, handleBulkDeleteByComment }) {
    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Header */}
            <div className="flex items-center justify-between bg-white dark:bg-ink-800 p-6 rounded-lg border border-ink-200 dark:border-ink-700 shadow-sm">
                <div>
                    <h2 className="text-xl font-semibold text-ink-900 dark:text-ink-50">Voucher Books</h2>
                    <p className="text-ink-500 dark:text-ink-400 text-sm font-medium">Reprint or delete a book of vouchers you printed earlier.</p>
                </div>
                <div className="flex items-center gap-3">
                    <div className="text-right">
                        <div className="text-xs font-medium text-ink-500 dark:text-ink-400">Total unused</div>
                        <div className="font-bold text-up text-lg dark:text-ink-100">{batchHistory.reduce((s, b) => s + (b.count - b.used), 0)}</div>
                    </div>
                    <div className="bg-signal-600/10 dark:bg-signal-600/20 text-ink-900 dark:text-ink-50 px-4 py-2 rounded-md text-xs font-semibold">
                        {batchHistory.length} books
                    </div>
                </div>
            </div>

            {/* Batch Cards */}
            {batchHistory.length === 0 ? (
                <div className="bg-white dark:bg-ink-800 rounded-lg border border-ink-200 dark:border-ink-700 p-12 text-center text-ink-500 dark:text-ink-400 text-sm font-medium">
                    No books yet. Print a book of vouchers from the Generator tab.
                </div>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {batchHistory.map((b) => {
                        const unused = b.count - b.used;
                        const usedPct = b.count > 0 ? Math.round((b.used / b.count) * 100) : 0;
                        return (
                            <div key={b.id} className="bg-white dark:bg-ink-800 rounded-lg border border-ink-200 dark:border-ink-700 shadow-sm p-5 flex flex-col gap-4">
                                {/* Book name headline */}
                                <div className="flex items-start justify-between gap-2">
                                    <div>
                                        <div className="text-xs font-medium text-ink-500 dark:text-ink-400 mb-0.5">Book</div>
                                        <div className="text-base font-bold text-ink-900 dark:text-ink-50 tracking-tight truncate max-w-[160px]">{b.displayName}</div>
                                        {/* Legacy rows have status: null (21 in production) and simply
                                            render without this badge, same as before this row existed. */}
                                        {b.status && (
                                            <span className={`inline-block mt-1 px-2 py-0.5 rounded-lg text-xs font-semibold ${b.status === 'complete' ? 'bg-up/10 dark:bg-up/20 text-ink-900 dark:text-ink-50' :
                                                b.status === 'failed' ? 'bg-down/10 dark:bg-down/20 text-down dark:text-ink-50' :
                                                    'bg-ink-100 dark:bg-ink-800 text-ink-900 dark:text-ink-400'
                                                }`}>{b.status}</span>
                                        )}
                                    </div>
                                    <div className="text-right shrink-0">
                                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-signal-600/10 dark:bg-signal-600/20 text-ink-900 dark:text-ink-50 rounded-md text-xs font-semibold mb-1">
                                            <span className={`w-[5px] h-3 rounded-full shrink-0 ${bandFor(b.profile)}`} aria-hidden="true"></span>
                                            {b.profile}
                                        </span>
                                        {b.timeLimit && <span className="px-2 py-0.5 bg-ink-100 dark:bg-ink-800 text-ink-900 dark:text-ink-400 rounded-lg text-xs font-bold font-mono block">{b.timeLimit}</span>}
                                    </div>
                                </div>

                                {b.date && <div className="text-xs text-ink-500 dark:text-ink-400 font-medium font-mono -mt-2">{b.date}</div>}

                                {/* Counts */}
                                <div className="grid grid-cols-3 gap-2 text-center">
                                    <div className="bg-ink-50 dark:bg-ink-800/50 rounded-md p-2">
                                        <div className="text-xs font-medium text-ink-500 dark:text-ink-400">Total</div>
                                        <div className="font-bold text-ink-900 dark:text-ink-50 text-lg leading-none mt-0.5">{b.count}</div>
                                    </div>
                                    <div className="bg-up/10 dark:bg-up/20 rounded-md p-2">
                                        <div className="text-xs font-medium text-ink-900 dark:text-ink-50">Unused</div>
                                        <div className="font-bold text-ink-900 dark:text-ink-50 text-lg leading-none mt-0.5">{unused}</div>
                                    </div>
                                    <div className="bg-warn/10 dark:bg-warn/20 rounded-md p-2">
                                        <div className="text-xs font-medium text-ink-900 dark:text-ink-50">Used</div>
                                        <div className="font-bold text-ink-900 dark:text-ink-50 text-lg leading-none mt-0.5">{b.used}</div>
                                    </div>
                                </div>

                                {/* Progress bar */}
                                <div>
                                    <div className="flex justify-between text-xs font-medium text-ink-500 dark:text-ink-400 mb-1">
                                        <span>Usage</span><span>{usedPct}%</span>
                                    </div>
                                    <div className="w-full bg-ink-200 dark:bg-ink-700 rounded-full h-2">
                                        <div className="h-2 rounded-full bg-signal-600 transition-all" style={{ width: `${usedPct}%` }} />
                                    </div>
                                </div>

                                {/* Actions */}
                                <div className="flex gap-2 pt-1">
                                    <button
                                        onClick={() => handleReprint(b)}
                                        className="flex-1 flex items-center justify-center gap-2 bg-signal-600 hover:bg-signal-700 text-white py-2.5 rounded-lg font-semibold text-xs shadow-lg transition-all active:scale-95"
                                    >
                                        <Printer size={13} /> Reprint ({b.count})
                                    </button>
                                    <button
                                        onClick={() => handleBulkDeleteByComment(b.name)}
                                        className="p-2.5 bg-down/10 dark:bg-down/20 text-down dark:text-ink-100 rounded-lg hover:bg-down/20 dark:hover:bg-down/40 transition-colors"
                                        title="Delete every voucher in this book"
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

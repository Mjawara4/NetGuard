import React from 'react';
import { Printer } from 'lucide-react';
import { bandFor } from '../profileBand';

export default function GeneratorPanel({ batchForm, setBatchForm, profiles, voucherJob, loading, handleGenerate, dismissVoucherJob }) {
    return (
        <div className="max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="bg-white dark:bg-ink-800 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700 overflow-hidden flex flex-col md:flex-row min-h-[500px]">
                <div className="md:w-1/3 bg-signal-600 p-8 sm:p-12 text-white flex flex-col justify-between">
                    <div>
                        <div className="w-12 h-12 sm:w-16 sm:h-16 bg-white/10 rounded-lg flex items-center justify-center mb-6 sm:mb-8">
                            <Printer size={28} />
                        </div>
                        <h3 className="text-2xl sm:text-3xl font-semibold tracking-tight leading-tight">Print a Book</h3>
                        <p className="text-ink-100 mt-4 font-medium text-xs sm:text-sm">Create unique access codes with a single click.</p>
                    </div>
                    <div className="pt-8 hidden sm:block">
                        <p className="text-xs font-medium text-ink-200">Printing high-speed vouchers</p>
                    </div>
                </div>
                <div className="md:w-2/3 p-8 sm:p-12">
                    <form onSubmit={handleGenerate} className="space-y-6 sm:space-y-8">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 sm:gap-8">
                            <div>
                                <label className="block text-xs font-medium text-ink-500 dark:text-ink-400 mb-3">Token Quantity</label>
                                <input type="number" className="w-full bg-ink-50 dark:bg-ink-800 border-none rounded-lg px-5 py-3.5 sm:py-4 focus:ring-2 focus:ring-signal-500 transition-all font-bold text-xl dark:text-ink-100" value={batchForm.qty} onChange={e => setBatchForm({ ...batchForm, qty: parseInt(e.target.value) })} min="1" max="1000" required />
                            </div>
                            <div>
                                <div className="flex justify-between items-center mb-3">
                                    <label className="block text-xs font-medium text-ink-500 dark:text-ink-400">Generation Mode</label>
                                </div>
                                <div className="flex gap-2">
                                    <select
                                        className="w-5/12 bg-ink-50 dark:bg-ink-800 border-none rounded-lg px-3 py-3.5 sm:py-4 focus:ring-2 focus:ring-signal-500 transition-all font-bold text-xs dark:text-ink-100"
                                        value={batchForm.random_mode ? (batchForm.format === 'numeric' ? 'numeric' : 'auto') : 'prefix'}
                                        onChange={e => {
                                            const mode = e.target.value;
                                            if (mode === 'prefix') {
                                                setBatchForm({ ...batchForm, random_mode: false, prefix: '', format: 'alphanumeric' });
                                            } else if (mode === 'auto') {
                                                setBatchForm({ ...batchForm, random_mode: true, prefix: 'RAND_SEQ', format: 'alphanumeric' });
                                            } else if (mode === 'numeric') {
                                                setBatchForm({ ...batchForm, random_mode: true, prefix: 'RAND_NUM', format: 'numeric' });
                                            }
                                        }}
                                    >
                                        <option value="prefix">Prefix</option>
                                        <option value="auto">Auto (A-Z, 0-9)</option>
                                        <option value="numeric">Auto (0-9 Only)</option>
                                    </select>
                                    <input
                                        type="text"
                                        className="placeholder:text-ink-500 dark:placeholder:text-ink-400 w-7/12 bg-ink-50 dark:bg-ink-800 border-none rounded-lg px-5 py-3.5 sm:py-4 focus:ring-2 focus:ring-signal-500 transition-all font-bold disabled:opacity-50 dark:text-ink-100"
                                        value={batchForm.prefix}
                                        onChange={e => setBatchForm({ ...batchForm, prefix: e.target.value })}
                                        disabled={batchForm.random_mode}
                                        placeholder="Prefix..."
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-ink-500 dark:text-ink-400 mb-3">Code Length</label>
                                <input type="number" className="w-full bg-ink-50 dark:bg-ink-800 border-none rounded-lg px-5 py-3.5 sm:py-4 focus:ring-2 focus:ring-signal-500 transition-all font-bold dark:text-ink-100" value={batchForm.length} onChange={e => setBatchForm({ ...batchForm, length: parseInt(e.target.value) })} min="4" max="20" />
                            </div>
                        </div>

                        <div>
                            <div className="flex items-center gap-2 mb-3">
                                <span className={`w-[5px] h-4 rounded-full shrink-0 ${bandFor(batchForm.profile)}`} aria-hidden="true"></span>
                                <label className="block text-xs font-medium text-ink-500 dark:text-ink-400">Link Profile</label>
                            </div>
                            <select className="w-full bg-ink-50 dark:bg-ink-800 border-none rounded-lg px-5 py-3.5 sm:py-4 focus:ring-2 focus:ring-signal-500 transition-all font-bold dark:text-ink-100" value={batchForm.profile} onChange={e => setBatchForm({ ...batchForm, profile: e.target.value })}>
                                <option value="default">Default Profile</option>
                                {profiles.map(p => <option key={p.name} value={p.name}>{p.name}</option>)}
                            </select>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 sm:gap-8">
                            <div>
                                <label className="block text-xs font-medium text-ink-500 dark:text-ink-400 mb-3">Validity</label>
                                <input type="text" className="placeholder:text-ink-500 dark:placeholder:text-ink-400 w-full bg-ink-50 dark:bg-ink-800 border-none rounded-lg px-5 py-3.5 sm:py-4 focus:ring-2 focus:ring-signal-500 transition-all font-bold dark:text-ink-100" placeholder="e.g. 1h, 1d" value={batchForm.time_limit} onChange={e => setBatchForm({ ...batchForm, time_limit: e.target.value })} />
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-ink-500 dark:text-ink-400 mb-3">Quota</label>
                                <input type="text" className="placeholder:text-ink-500 dark:placeholder:text-ink-400 w-full bg-ink-50 dark:bg-ink-800 border-none rounded-lg px-5 py-3.5 sm:py-4 focus:ring-2 focus:ring-signal-500 transition-all font-bold dark:text-ink-100" placeholder="e.g. 1G" value={batchForm.data_limit} onChange={e => setBatchForm({ ...batchForm, data_limit: e.target.value })} />
                            </div>
                        </div>

                        {voucherJob && (voucherJob.status === 'queued' || voucherJob.status === 'running') && (
                            <div className="bg-signal-600/10 dark:bg-signal-600/20 rounded-lg p-4 sm:p-5">
                                <div className="flex justify-between items-center text-xs font-semibold text-ink-900 dark:text-ink-50 mb-2">
                                    <span>Printing vouchers…</span>
                                    <div className="flex items-center gap-3">
                                        <span>{voucherJob.created ?? 0} / {voucherJob.count}</span>
                                        {/* C1 manual escape hatch: clears local job-tracking state
                                            immediately, independent of whether VOUCHER_JOB_STALL_MS
                                            is the right value. Does NOT touch the server-side job --
                                            if it's actually still running, it keeps running regardless. */}
                                        <button
                                            type="button"
                                            onClick={dismissVoucherJob}
                                            className="font-bold text-ink-900 dark:text-ink-50 hover:text-signal-700 dark:hover:text-ink-100 underline decoration-dotted underline-offset-2 transition-colors"
                                            title="Stop tracking this batch here. If it's still running on the router, it keeps running -- check the History tab later."
                                        >
                                            Dismiss
                                        </button>
                                    </div>
                                </div>
                                <div className="w-full bg-signal-600/25 dark:bg-signal-600/40 rounded-full h-2">
                                    <div
                                        className="h-2 rounded-full bg-signal-600 transition-all"
                                        style={{ width: `${voucherJob.count > 0 ? Math.min(100, Math.round(((voucherJob.created ?? 0) / voucherJob.count) * 100)) : 0}%` }}
                                    />
                                </div>
                            </div>
                        )}

                        <div className="pt-4 sm:pt-6">
                            {/* Copy only -- the handler is still handleGenerate and the
                                endpoint is still /users/batch. The spec asks the operator-facing
                                verb to be "Print", and for the count to be in the button. */}
                            <button type="submit" className="w-full py-4 sm:py-5 bg-signal-600 text-white rounded-lg font-semibold text-xs sm:text-sm hover:bg-signal-700 shadow-2xl transition-all active:scale-[0.98] disabled:opacity-60" disabled={loading || (voucherJob && (voucherJob.status === 'queued' || voucherJob.status === 'running'))}>
                                {loading ? 'Processing...' : (voucherJob && (voucherJob.status === 'queued' || voucherJob.status === 'running')) ? 'Printing…' : `Print ${batchForm.qty || 0} vouchers`}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div >
    );
}

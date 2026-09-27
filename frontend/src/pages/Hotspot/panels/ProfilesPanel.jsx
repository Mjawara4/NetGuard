import React from 'react';
import { Plus, Settings, Shield, Trash2 } from 'lucide-react';
import ResponsiveTable from '../../../components/ResponsiveTable';
import { bandFor } from '../profileBand';

export default function ProfilesPanel({ profiles, handleProfileDelete, setShowProfileModal, setShowPriceModal, setSelectedProfileSettings }) {
    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center bg-white dark:bg-ink-800 p-6 sm:p-8 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700 gap-6">
                <div>
                    <h2 className="text-xl sm:text-2xl font-semibold text-ink-900 dark:text-ink-50 tracking-tight">Hotspot User Profiles</h2>
                    <p className="text-ink-500 dark:text-ink-400 font-medium text-xs sm:text-sm">Define speed limits and simultaneous device allowances.</p>
                </div>
                <button
                    onClick={() => setShowProfileModal(true)}
                    className="bg-signal-600 text-white px-6 sm:px-8 py-3 sm:py-3.5 rounded-lg font-semibold text-xs hover:bg-signal-700 shadow-xl transition-all active:scale-95 flex items-center justify-center gap-2"
                >
                    <Plus size={18} /> Create Profile
                </button>
            </div>

            <div className="bg-white dark:bg-ink-800 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700 overflow-hidden">
                <div className="overflow-hidden">
                    <ResponsiveTable
                        data={profiles}
                        columns={[
                            {
                                header: 'Profile Name',
                                accessor: 'name',
                                render: (p) => (
                                    <div className="inline-flex items-center gap-2">
                                        <span className={`w-[5px] h-4 rounded-full shrink-0 ${bandFor(p.name)}`} aria-hidden="true"></span>
                                        <span className="font-bold text-ink-900 dark:text-ink-50 group-hover:text-signal-600 dark:group-hover:text-signal-300 transition-colors tracking-tight text-sm">{p.name}</span>
                                    </div>
                                )
                            },
                            {
                                header: 'Bandwidth',
                                accessor: 'rate-limit',
                                render: (p) => (
                                    <div className="inline-flex items-center gap-2 bg-signal-600/10 dark:bg-signal-600/20 text-ink-900 dark:text-ink-50 px-3 py-1 rounded-md text-xs font-bold font-mono">
                                        {p['rate-limit'] || 'Unlimited'}
                                    </div>
                                )
                            },
                            {
                                header: 'Devices',
                                accessor: 'shared-users',
                                render: (p) => <div className="text-ink-900 dark:text-ink-50 font-bold text-sm text-center">{p['shared-users'] || '1'}</div>
                            },
                            {
                                header: 'Charge',
                                accessor: 'price',
                                render: (p) => (
                                    <button
                                        onClick={() => {
                                            setSelectedProfileSettings({
                                                name: p.name,
                                                price: p.custom_price || 0,
                                                currency: p.custom_currency || 'TZS'
                                            });
                                            setShowPriceModal(true);
                                        }}
                                        className="inline-flex items-center gap-1.5 bg-up/10 dark:bg-up/20 text-ink-900 dark:text-ink-50 px-3 py-1 rounded-md text-xs font-bold hover:bg-up/20 transition-colors"
                                    >
                                        {p.custom_price ? `${p.custom_price.toLocaleString()} ${p.custom_currency || 'TZS'}` : 'Set price'}
                                        <Settings size={12} />
                                    </button>
                                )
                            },
                            {
                                header: 'Active Users',
                                accessor: 'active_users',
                                render: (p) => (
                                    <div className="flex items-center justify-center gap-1.5">
                                        <div className={`w-1.5 h-1.5 rounded-full ${p.active_users > 0 ? 'bg-up animate-pulse' : 'bg-ink-300'}`}></div>
                                        <span className={`text-xs font-semibold tracking-tight ${p.active_users > 0 ? 'text-up dark:text-ink-100' : 'text-ink-500 dark:text-ink-400'}`}>
                                            {p.active_users || 0} Online
                                        </span>
                                    </div>
                                )
                            },
                            {
                                header: 'Delete',
                                accessor: 'actions',
                                render: (p) => (
                                    <div className="text-right">
                                        <button
                                            onClick={() => handleProfileDelete(p.name)}
                                            className="text-down dark:text-ink-100 p-2 bg-down/10 dark:bg-down/20 rounded-md transition-all active:scale-90"
                                            title="Remove Profile"
                                        >
                                            <Trash2 size={18} />
                                        </button>
                                    </div>
                                )
                            }
                        ]}
                        renderCard={(p) => (
                            <div className="flex flex-col gap-3">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <span className={`w-[5px] h-4 rounded-full shrink-0 ${bandFor(p.name)}`} aria-hidden="true"></span>
                                        <Shield size={16} className="text-signal-600 dark:text-signal-300" />
                                        <span className="font-bold text-ink-900 dark:text-ink-50 text-sm">{p.name}</span>
                                    </div>
                                    <div className="text-xs font-bold bg-signal-600/10 dark:bg-signal-600/20 text-ink-900 dark:text-ink-50 px-2 py-1 rounded-lg font-mono">
                                        {p['rate-limit'] || 'Unlim'}
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-2 text-xs text-ink-500 dark:text-ink-400">
                                    <div className="bg-ink-50 dark:bg-ink-800/50 p-2 rounded-lg text-center">
                                        <div className="font-medium text-xs text-ink-500 dark:text-ink-400">Shared Devices</div>
                                        <div className="font-bold text-ink-900 dark:text-ink-50">{p['shared-users'] || '1'}</div>
                                    </div>
                                    <div className="bg-up/10 dark:bg-up/20 p-2 rounded-lg text-center border border-up/20 dark:border-up/30">
                                        <div className="font-medium text-xs text-ink-900 dark:text-ink-50">Active Users</div>
                                        <div className="font-bold text-ink-900 dark:text-ink-50">{p.active_users || 0} Online</div>
                                    </div>
                                </div>
                                <div className="flex flex-col border-t border-ink-200 dark:border-ink-700 pt-3 mt-1 gap-2">
                                    <button
                                        onClick={() => {
                                            setSelectedProfileSettings({
                                                name: p.name,
                                                price: p.custom_price || 0,
                                                currency: p.custom_currency || 'TZS'
                                            });
                                            setShowPriceModal(true);
                                        }}
                                        className="w-full text-center text-ink-900 dark:text-ink-50 font-semibold text-xs bg-up/10 dark:bg-up/20 py-2 rounded-lg flex items-center justify-center gap-2"
                                    >
                                        <Settings size={14} /> Configure Price ({p.custom_price || '0'} {p.custom_currency || 'TZS'})
                                    </button>
                                    <button onClick={() => handleProfileDelete(p.name)} className="w-full text-center text-down dark:text-ink-100 font-semibold text-xs bg-down/10 dark:bg-down/20 py-2 rounded-lg">Delete Profile</button>
                                </div>
                            </div>
                        )}
                        emptyMessage="No profiles found on this router."
                    />
                </div>
            </div>
        </div>
    );
}

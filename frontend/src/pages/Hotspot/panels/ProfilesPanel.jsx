import React from 'react';
import { Plus, Settings, Shield, Trash2 } from 'lucide-react';
import ResponsiveTable from '../../../components/ResponsiveTable';

export default function ProfilesPanel({ profiles, handleProfileDelete, setShowProfileModal, setShowPriceModal, setSelectedProfileSettings }) {
    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center bg-white dark:bg-gray-800 p-6 sm:p-8 rounded-3xl shadow-sm border border-gray-100 dark:border-gray-700 gap-6">
                <div>
                    <h2 className="text-xl sm:text-2xl font-black text-gray-900 dark:text-white tracking-tight">Hotspot User Profiles</h2>
                    <p className="text-gray-500 dark:text-gray-400 font-medium text-xs sm:text-sm">Define speed limits and simultaneous device allowances.</p>
                </div>
                <button
                    onClick={() => setShowProfileModal(true)}
                    className="bg-blue-600 text-white px-6 sm:px-8 py-3 sm:py-3.5 rounded-2xl font-black text-[10px] sm:text-xs uppercase tracking-widest hover:bg-blue-700 shadow-xl shadow-blue-100 transition-all active:scale-95 flex items-center justify-center gap-2"
                >
                    <Plus size={18} /> Create Profile
                </button>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-3xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
                <div className="overflow-hidden">
                    <ResponsiveTable
                        data={profiles}
                        columns={[
                            {
                                header: 'Profile Name',
                                accessor: 'name',
                                render: (p) => <div className="font-bold text-gray-900 dark:text-white group-hover:text-blue-600 transition-colors uppercase tracking-tight text-sm">{p.name}</div>
                            },
                            {
                                header: 'Bandwidth',
                                accessor: 'rate-limit',
                                render: (p) => (
                                    <div className="inline-flex items-center gap-2 bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-400 px-3 py-1 rounded-xl text-[10px] font-black tracking-widest font-mono">
                                        {p['rate-limit'] || 'UNLIMITED'}
                                    </div>
                                )
                            },
                            {
                                header: 'Devices',
                                accessor: 'shared-users',
                                render: (p) => <div className="text-gray-900 dark:text-white font-black text-sm text-center">{p['shared-users'] || '1'}</div>
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
                                        className="inline-flex items-center gap-1.5 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400 px-3 py-1 rounded-xl text-[10px] font-black tracking-widest hover:bg-emerald-100 transition-colors"
                                    >
                                        {p.custom_price ? `${p.custom_price.toLocaleString()} ${p.custom_currency || 'TZS'}` : 'SET PRICE'}
                                        <Settings size={12} />
                                    </button>
                                )
                            },
                            {
                                header: 'Active Users',
                                accessor: 'active_users',
                                render: (p) => (
                                    <div className="flex items-center justify-center gap-1.5">
                                        <div className={`w-1.5 h-1.5 rounded-full ${p.active_users > 0 ? 'bg-emerald-500 animate-pulse' : 'bg-gray-300'}`}></div>
                                        <span className={`text-[10px] font-black uppercase tracking-tight ${p.active_users > 0 ? 'text-emerald-600' : 'text-gray-400'}`}>
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
                                            className="text-red-500 hover:text-red-700 p-2 bg-red-50 dark:bg-red-900/20 rounded-xl transition-all active:scale-90"
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
                                        <Shield size={16} className="text-purple-500" />
                                        <span className="font-bold text-gray-900 dark:text-white uppercase text-sm">{p.name}</span>
                                    </div>
                                    <div className="text-xs font-black bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-400 px-2 py-1 rounded-lg font-mono">
                                        {p['rate-limit'] || 'UNLIM'}
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-2 text-xs text-gray-500 dark:text-gray-400">
                                    <div className="bg-gray-50 dark:bg-gray-700/50 p-2 rounded-lg text-center">
                                        <div className="uppercase font-bold text-[8px] text-gray-400">Shared Devices</div>
                                        <div className="font-black text-gray-900 dark:text-white">{p['shared-users'] || '1'}</div>
                                    </div>
                                    <div className="bg-emerald-50 dark:bg-emerald-900/20 p-2 rounded-lg text-center border border-emerald-100/50 dark:border-emerald-900/30">
                                        <div className="uppercase font-bold text-[8px] text-emerald-600 dark:text-emerald-400">Active Users</div>
                                        <div className="font-black text-emerald-700 dark:text-emerald-400">{p.active_users || 0} Online</div>
                                    </div>
                                </div>
                                <div className="flex flex-col border-t pt-3 mt-1 gap-2">
                                    <button
                                        onClick={() => {
                                            setSelectedProfileSettings({
                                                name: p.name,
                                                price: p.custom_price || 0,
                                                currency: p.custom_currency || 'TZS'
                                            });
                                            setShowPriceModal(true);
                                        }}
                                        className="w-full text-center text-emerald-600 dark:text-emerald-400 font-bold text-[10px] uppercase bg-emerald-50 dark:bg-emerald-900/20 py-2 rounded-lg flex items-center justify-center gap-2"
                                    >
                                        <Settings size={14} /> Configure Price ({p.custom_price || '0'} {p.custom_currency || 'TZS'})
                                    </button>
                                    <button onClick={() => handleProfileDelete(p.name)} className="w-full text-center text-red-500 font-bold text-[10px] uppercase bg-red-50 dark:bg-red-900/20 py-2 rounded-lg">Delete Profile</button>
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

import React, { useState, useEffect } from 'react';
import api from '../api';
import { Users, CreditCard, Activity, RefreshCw, Plus, Trash, Printer, X, Scissors, Shield, Trash2 } from 'lucide-react';

export default function Hotspot() {
    const [activeTab, setActiveTab] = useState('active');
    const [devices, setDevices] = useState([]);
    const [selectedDevice, setSelectedDevice] = useState(null);
    const [users, setUsers] = useState([]);
    const [activeSessions, setActiveSessions] = useState([]);
    const [profiles, setProfiles] = useState([]);
    const [loading, setLoading] = useState(false);
    const [showProfileModal, setShowProfileModal] = useState(false);
    const [profileForm, setProfileForm] = useState({ name: '', rateLimit: '1M/1M', sharedUsers: 1 });

    // Generation State
    const [batchForm, setBatchForm] = useState({ qty: 10, prefix: 'user', profile: 'default', time_limit: '1h', data_limit: '', length: 4, random_mode: false });
    const [generatedBatch, setGeneratedBatch] = useState([]);
    const [showPrintView, setShowPrintView] = useState(false);

    useEffect(() => {
        fetchDevices();
    }, []);

    useEffect(() => {
        if (selectedDevice) {
            fetchData();
        }
    }, [selectedDevice, activeTab]);

    const fetchDevices = async () => {
        try {
            const res = await api.get('/inventory/devices');
            console.log("Fetched devices:", res.data);
            const routers = res.data.filter(d => d.device_type?.toLowerCase() === 'router');
            setDevices(routers);
            if (routers.length > 0 && !selectedDevice) setSelectedDevice(routers[0].id);
        } catch (e) {
            console.error(e);
        }
    };

    const fetchProfiles = async (deviceId) => {
        setLoading(true);
        try {
            const res = await api.get(`/hotspot/${deviceId}/profiles`);
            setProfiles(res.data);
        } catch (e) {
            console.error("Failed to fetch profiles:", e);
        } finally {
            setLoading(false);
        }
    };

    const fetchData = async () => {
        if (!selectedDevice) return;
        setLoading(true);
        try {
            if (activeTab === 'users') {
                const res = await api.get(`/hotspot/${selectedDevice}/users`);
                setUsers(res.data);
            } else if (activeTab === 'active') {
                const res = await api.get(`/hotspot/${selectedDevice}/active`);
                setActiveSessions(res.data);
            } else if (activeTab === 'profiles') {
                await fetchProfiles(selectedDevice);
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handleKick = async (id) => {
        if (!window.confirm("Disconnect this user?")) return;
        try {
            await api.delete(`/hotspot/${selectedDevice}/active/${id}`);
            fetchData();
        } catch (e) {
            alert("Failed to kick user.");
        }
    };

    const handleProfileAdd = async (e) => {
        e.preventDefault();
        if (!selectedDevice) return;
        try {
            await api.post(`/hotspot/${selectedDevice}/profiles`, {
                name: profileForm.name,
                'rate-limit': profileForm.rateLimit,
                'shared-users': profileForm.sharedUsers
            });
            setShowProfileModal(false);
            setProfileForm({ name: '', rateLimit: '1M/1M', sharedUsers: 1 }); // Reset form
            fetchProfiles(selectedDevice);
        } catch (err) {
            alert("Failed to add profile: " + (err.response?.data?.detail || err.message));
        }
    };

    const handleProfileDelete = async (name) => {
        if (!selectedDevice) return;
        if (!confirm(`Are you sure you want to delete profile "${name}"?`)) return;
        try {
            await api.delete(`/hotspot/${selectedDevice}/profiles/${name}`);
            fetchProfiles(selectedDevice);
        } catch (err) {
            alert("Failed to delete profile: " + (err.response?.data?.detail || err.message));
        }
    };

    const handleGenerate = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await api.post(`/hotspot/${selectedDevice}/users/batch`, batchForm);
            setGeneratedBatch(res.data);
            setShowPrintView(true);
        } catch (e) {
            alert('Generation failed: ' + (e.response?.data?.detail || e.message));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 pt-4 sm:pt-8 px-4 sm:px-6 lg:px-10 pb-12">
            <style>{`
                @media print {
                    body * { visibility: hidden; }
                    #printable-area, #printable-area * { visibility: visible; }
                    #printable-area { position: absolute; left: 0; top: 0; width: 100%; padding: 20px; }
                    .no-print { display: none !important; }
                    .voucher-card { 
                        page-break-inside: avoid; 
                        border: 1px dashed #ccc; 
                        break-inside: avoid;
                    }
                }
            `}</style>

            <div className="max-w-7xl mx-auto">
                {/* Page Header */}
                <div className="mb-8 sm:mb-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6 no-print">
                    <div>
                        <h1 className="text-3xl sm:text-4xl font-black text-gray-900 tracking-tight leading-none">
                            Hotspot <span className="text-blue-600">Controller</span>
                        </h1>
                        <p className="text-gray-500 mt-2 font-medium text-sm sm:text-base">Enterprise voucher management and hotspot profile orchestration.</p>
                    </div>
                    <div className="flex items-center gap-3">
                        <select
                            className="bg-white border border-gray-100 rounded-2xl px-4 sm:px-5 py-3 shadow-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all font-bold text-gray-700 flex-1 lg:min-w-[240px] text-sm sm:text-base"
                            value={selectedDevice || ''}
                            onChange={e => setSelectedDevice(e.target.value)}
                        >
                            <option value="" disabled>Select Core Router</option>
                            {devices.map(d => <option key={d.id} value={d.id}>{d.name} ({d.ip_address})</option>)}
                        </select>
                        <button
                            onClick={fetchData}
                            className="bg-white p-3 border border-gray-100 rounded-2xl shadow-sm hover:bg-gray-50 text-gray-600 transition-all active:scale-95 flex-shrink-0"
                            title="Refresh Data"
                        >
                            <RefreshCw size={22} className={loading ? 'animate-spin text-blue-600' : ''} />
                        </button>
                    </div>
                </div>

                {/* Navigation Bar */}
                <div className="mb-8 sm:mb-10 no-print">
                    <div className="flex bg-white p-1.5 rounded-3xl shadow-sm border border-gray-100 gap-1.5 overflow-x-auto no-scrollbar scroll-smooth">
                        <TabButton id="active" label="Active" icon={Activity} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="users" label="Users" icon={Users} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="profiles" label="Profiles" icon={Shield} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="generate" label="Generator" icon={Printer} activeTab={activeTab} setActiveTab={setActiveTab} />
                    </div>
                </div>

                <div className="space-y-8">
                    {/* Print View Overlay/Content */}
                    {showPrintView && (
                        <div className="bg-white rounded-3xl shadow-xl border border-blue-100 overflow-hidden animate-in fade-in zoom-in duration-300 mb-8 no-print">
                            <div className="bg-blue-600 p-6 flex flex-col sm:flex-row justify-between items-center text-white gap-4">
                                <div className="flex items-center gap-4">
                                    <div className="bg-white/20 p-2 rounded-lg">
                                        <Printer size={20} />
                                    </div>
                                    <div>
                                        <h3 className="font-black uppercase tracking-tight text-sm sm:text-base">Print Preview</h3>
                                        <p className="text-blue-100 text-[10px] sm:text-xs font-medium">Ready to export {generatedBatch.length} vouchers</p>
                                    </div>
                                </div>
                                <div className="flex gap-3 w-full sm:w-auto">
                                    <button onClick={() => setShowPrintView(false)} className="flex-1 sm:flex-none px-5 py-2 hover:bg-white/10 rounded-xl font-bold text-[10px] sm:text-xs uppercase transition-colors border border-white/20">Close</button>
                                    <button onClick={() => window.print()} className="flex-1 sm:flex-none bg-white text-blue-600 px-6 py-2 rounded-xl font-black text-[10px] sm:text-xs uppercase shadow-lg transition-all active:scale-95">Print Now</button>
                                </div>
                            </div>
                            <div className="p-4 sm:p-8 bg-gray-50 grid grid-cols-2 xs:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4 overflow-y-auto max-h-[400px]">
                                {generatedBatch.map((u, i) => (
                                    <div key={i} className="bg-white p-3 sm:p-4 rounded-xl border border-gray-200 shadow-sm text-center">
                                        <div className="text-[8px] sm:text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">Voucher</div>
                                        <div className="font-mono text-base sm:text-xl font-black text-blue-600 bg-blue-50 py-1 sm:py-2 rounded-lg border border-blue-100 mb-1 sm:mb-2">{u.username}</div>
                                        <div className="text-[7px] sm:text-[8px] text-gray-400 uppercase font-bold">LIM: {batchForm.time_limit || 'UNLIM'}</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Hidden Print Area (Physical Print) */}
                    <div className="hidden print:grid print:grid-cols-5 print:gap-2" id="printable-area">
                        {generatedBatch.map((u, i) => (
                            <div key={i} className="voucher-card p-3 text-center">
                                <h3 className="font-black text-xs text-blue-600 uppercase mb-1">NetGuard WiFi</h3>
                                <div className="text-[8px] text-gray-400 font-bold uppercase mb-2">Voucher Code</div>
                                <div className="font-mono font-black text-lg bg-gray-50 border border-gray-200 py-1 rounded-md mb-2">{u.username}</div>
                                <div className="flex justify-between text-[7px] font-bold text-gray-400 border-t pt-1">
                                    <span>LIM: {batchForm.time_limit || 'NONE'}</span>
                                    <span>ID: {i + 1}</span>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Active Sessions */}
                    {activeTab === 'active' && !showPrintView && (
                        <div className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <div className="p-6 sm:p-8 border-b border-gray-50 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                                <h2 className="text-xl font-black text-gray-900">Online Users</h2>
                                <span className="inline-flex max-w-fit bg-blue-50 text-blue-600 px-4 py-1.5 rounded-xl text-[10px] font-black uppercase tracking-widest">
                                    {activeSessions.length} Connected
                                </span>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="min-w-full">
                                    <thead className="bg-gray-50 text-[10px] font-black text-gray-400 uppercase tracking-widest text-left">
                                        <tr>
                                            <th className="px-6 sm:px-8 py-4 whitespace-nowrap">Identity</th>
                                            <th className="px-6 sm:px-8 py-4 whitespace-nowrap">Network Address</th>
                                            <th className="px-6 sm:px-8 py-4 whitespace-nowrap">Time Online</th>
                                            <th className="px-6 sm:px-8 py-4 whitespace-nowrap text-right">Interrupt</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-50">
                                        {activeSessions.map((u, i) => (
                                            <tr key={i} className="hover:bg-gray-50 transition-colors">
                                                <td className="px-6 sm:px-8 py-5 font-bold text-gray-900 text-sm">{u.user}</td>
                                                <td className="px-6 sm:px-8 py-5 text-xs text-gray-500 font-mono whitespace-nowrap">{u.address}</td>
                                                <td className="px-6 sm:px-8 py-5 text-xs text-gray-500 whitespace-nowrap">{u.uptime}</td>
                                                <td className="px-6 sm:px-8 py-5 text-right">
                                                    <button onClick={() => handleKick(u.id)} className="text-red-500 hover:text-red-700 font-black text-[10px] uppercase tracking-widest hover:underline px-3 py-1.5 bg-red-50 rounded-lg whitespace-nowrap">
                                                        Kick
                                                    </button>
                                                </td>
                                            </tr>
                                        ))}
                                        {activeSessions.length === 0 && (
                                            <tr>
                                                <td colSpan="4" className="px-8 py-20 text-center text-gray-400 font-medium italic text-sm">No active hotspot sessions detected.</td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* Users Database */}
                    {activeTab === 'users' && (
                        <div className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <div className="p-6 sm:p-8 border-b border-gray-50">
                                <h2 className="text-xl font-black text-gray-900">Voucher Database</h2>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="min-w-full">
                                    <thead className="bg-gray-50 text-[10px] font-black text-gray-400 uppercase tracking-widest text-left">
                                        <tr>
                                            <th className="px-6 sm:px-8 py-4 whitespace-nowrap">Identity</th>
                                            <th className="px-6 sm:px-8 py-4 whitespace-nowrap">Profile</th>
                                            <th className="px-6 sm:px-8 py-4 whitespace-nowrap">Usage</th>
                                            <th className="px-6 sm:px-8 py-4 whitespace-nowrap text-right">Interrupt</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-50">
                                        {users.map((u, i) => (
                                            <tr key={i} className="hover:bg-gray-50 transition-colors">
                                                <td className="px-6 sm:px-8 py-5">
                                                    <div className="font-bold text-gray-900 text-sm">{u.name}</div>
                                                    <div className="text-[10px] text-gray-400 font-mono tracking-tighter">PWD: {u.password}</div>
                                                </td>
                                                <td className="px-6 sm:px-8 py-5">
                                                    <span className="px-3 py-1 bg-emerald-50 text-emerald-600 rounded-lg text-[10px] font-black uppercase whitespace-nowrap">{u.profile}</span>
                                                </td>
                                                <td className="px-6 sm:px-8 py-5">
                                                    <div className="text-xs font-bold text-gray-700 whitespace-nowrap">{(u.bytes_in / 1024 / 1024).toFixed(1)} MB</div>
                                                    <div className="text-[10px] text-gray-400 font-medium whitespace-nowrap">{u.uptime || '0s'}</div>
                                                </td>
                                                <td className="px-6 sm:px-8 py-5 text-right">
                                                    <button onClick={() => removeUser(u.id)} className="text-red-500 hover:text-red-700 font-black text-[10px] uppercase tracking-widest hover:underline px-3 py-1.5 bg-red-50 rounded-lg whitespace-nowrap">
                                                        Del
                                                    </button>
                                                </td>
                                            </tr>
                                        ))}
                                        {users.length === 0 && (
                                            <tr>
                                                <td colSpan="4" className="px-8 py-20 text-center text-gray-400 font-medium italic text-sm">Voucher database is empty.</td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* Hotspot Profiles Tab */}
                    {activeTab === 'profiles' && (
                        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center bg-white p-6 sm:p-8 rounded-3xl shadow-sm border border-gray-100 gap-6">
                                <div>
                                    <h2 className="text-xl sm:text-2xl font-black text-gray-900 tracking-tight">Hotspot User Profiles</h2>
                                    <p className="text-gray-500 font-medium text-xs sm:text-sm">Define speed limits and simultaneous device allowances.</p>
                                </div>
                                <button
                                    onClick={() => setShowProfileModal(true)}
                                    className="bg-blue-600 text-white px-6 sm:px-8 py-3 sm:py-3.5 rounded-2xl font-black text-[10px] sm:text-xs uppercase tracking-widest hover:bg-blue-700 shadow-xl shadow-blue-100 transition-all active:scale-95 flex items-center justify-center gap-2"
                                >
                                    <Plus size={18} /> Create Profile
                                </button>
                            </div>

                            <div className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
                                <div className="overflow-x-auto">
                                    <table className="min-w-full">
                                        <thead className="bg-gray-50 text-[10px] font-black text-gray-400 uppercase tracking-widest text-left">
                                            <tr>
                                                <th className="px-6 sm:px-8 py-4">Profile Name</th>
                                                <th className="px-6 sm:px-8 py-4">Bandwidth</th>
                                                <th className="px-6 sm:px-8 py-4 text-center">Devices</th>
                                                <th className="px-6 sm:px-8 py-4 text-right">Delete</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-gray-50">
                                            {profiles.map((p, i) => (
                                                <tr key={i} className="hover:bg-gray-50 transition-colors">
                                                    <td className="px-6 sm:px-8 py-5">
                                                        <div className="font-bold text-gray-900 group-hover:text-blue-600 transition-colors uppercase tracking-tight text-sm">{p.name}</div>
                                                    </td>
                                                    <td className="px-6 sm:px-8 py-5">
                                                        <div className="inline-flex items-center gap-2 bg-indigo-50 text-indigo-700 px-3 py-1 rounded-xl text-[10px] font-black tracking-widest font-mono">
                                                            {p['rate-limit'] || 'UNLIMITED'}
                                                        </div>
                                                    </td>
                                                    <td className="px-6 sm:px-8 py-5 text-center">
                                                        <div className="text-gray-900 font-black text-sm">{p['shared-users'] || '1'}</div>
                                                    </td>
                                                    <td className="px-6 sm:px-8 py-5 text-right">
                                                        <button
                                                            onClick={() => handleProfileDelete(p.name)}
                                                            className="text-red-500 hover:text-red-700 p-2 bg-red-50 rounded-xl transition-all active:scale-90"
                                                            title="Remove Profile"
                                                        >
                                                            <Trash2 size={18} />
                                                        </button>
                                                    </td>
                                                </tr>
                                            ))}
                                            {profiles.length === 0 && (
                                                <tr>
                                                    <td colSpan="4" className="px-8 py-20 text-center text-gray-400 font-medium italic">No profiles found on this router.</td>
                                                </tr>
                                            )}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Batch Generator */}
                    {activeTab === 'generate' && (
                        <div className="max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <div className="bg-white rounded-[32px] sm:rounded-[40px] shadow-sm border border-gray-100 overflow-hidden flex flex-col md:flex-row min-h-[500px]">
                                <div className="md:w-1/3 bg-blue-600 p-8 sm:p-12 text-white flex flex-col justify-between">
                                    <div>
                                        <div className="w-12 h-12 sm:w-16 sm:h-16 bg-white/10 rounded-2xl flex items-center justify-center mb-6 sm:mb-8">
                                            <Printer size={28} />
                                        </div>
                                        <h3 className="text-2xl sm:text-3xl font-black tracking-tight leading-tight uppercase">Batch Engine</h3>
                                        <p className="text-blue-100 mt-4 font-medium text-xs sm:text-sm">Create unique access codes with a single click.</p>
                                    </div>
                                    <div className="pt-8 hidden sm:block">
                                        <p className="text-[10px] font-black uppercase tracking-widest text-blue-200">Processing high-speed vouchers</p>
                                    </div>
                                </div>
                                <div className="md:w-2/3 p-8 sm:p-12">
                                    <form onSubmit={handleGenerate} className="space-y-6 sm:space-y-8">
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 sm:gap-8">
                                            <div>
                                                <label className="block text-[10px] font-black text-gray-400 uppercase mb-3 tracking-widest">Token Quantity</label>
                                                <input type="number" className="w-full bg-gray-50 border-none rounded-2xl px-5 py-3.5 sm:py-4 focus:ring-2 focus:ring-blue-500 transition-all font-black text-xl" value={batchForm.qty} onChange={e => setBatchForm({ ...batchForm, qty: parseInt(e.target.value) })} min="1" max="500" required />
                                            </div>
                                            <div>
                                                <div className="flex justify-between items-center mb-3">
                                                    <label className="block text-[10px] font-black text-gray-400 uppercase tracking-widest">Prefix</label>
                                                    <div className="flex items-center gap-2">
                                                        <input type="checkbox" id="random_mode" checked={batchForm.random_mode} onChange={e => setBatchForm({ ...batchForm, random_mode: e.target.checked })} className="w-4 h-4 rounded border-gray-200 text-blue-600 focus:ring-blue-500" />
                                                        <label htmlFor="random_mode" className="text-[8px] sm:text-[10px] text-blue-600 font-black uppercase cursor-pointer">Auto</label>
                                                    </div>
                                                </div>
                                                <input type="text" className="w-full bg-gray-50 border-none rounded-2xl px-5 py-3.5 sm:py-4 focus:ring-2 focus:ring-blue-500 transition-all font-bold disabled:opacity-50" value={batchForm.prefix} onChange={e => setBatchForm({ ...batchForm, prefix: e.target.value })} disabled={batchForm.random_mode} required={!batchForm.random_mode} placeholder={batchForm.random_mode ? 'RAND_SEQ' : 'user'} />
                                            </div>
                                        </div>

                                        <div>
                                            <label className="block text-[10px] font-black text-gray-400 uppercase mb-3 tracking-widest">Link Profile</label>
                                            <select className="w-full bg-gray-50 border-none rounded-2xl px-5 py-3.5 sm:py-4 focus:ring-2 focus:ring-blue-500 transition-all font-bold" value={batchForm.profile} onChange={e => setBatchForm({ ...batchForm, profile: e.target.value })}>
                                                <option value="default">Default Profile</option>
                                                {profiles.map(p => <option key={p.name} value={p.name}>{p.name}</option>)}
                                            </select>
                                        </div>

                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 sm:gap-8">
                                            <div>
                                                <label className="block text-[10px] font-black text-gray-400 uppercase mb-3 tracking-widest">Validity</label>
                                                <input type="text" className="w-full bg-gray-50 border-none rounded-2xl px-5 py-3.5 sm:py-4 focus:ring-2 focus:ring-blue-500 transition-all font-bold" placeholder="e.g. 1h, 1d" value={batchForm.time_limit} onChange={e => setBatchForm({ ...batchForm, time_limit: e.target.value })} />
                                            </div>
                                            <div>
                                                <label className="block text-[10px] font-black text-gray-400 uppercase mb-3 tracking-widest">Quota</label>
                                                <input type="text" className="w-full bg-gray-50 border-none rounded-2xl px-5 py-3.5 sm:py-4 focus:ring-2 focus:ring-blue-500 transition-all font-bold" placeholder="e.g. 1G" value={batchForm.data_limit} onChange={e => setBatchForm({ ...batchForm, data_limit: e.target.value })} />
                                            </div>
                                        </div>

                                        <div className="pt-4 sm:pt-6">
                                            <button type="submit" className="w-full py-4 sm:py-5 bg-blue-600 text-white rounded-3xl font-black text-xs sm:text-sm uppercase tracking-widest hover:bg-blue-700 shadow-2xl shadow-blue-100 transition-all active:scale-[0.98]" disabled={loading}>
                                                {loading ? 'Processing...' : 'Generate Hotspot Vouchers'}
                                            </button>
                                        </div>
                                    </form>
                                </div>
                            </div>
                        </div >
                    )}
                </div>
            </div>

            {/* Profile Creation Modal */}
            {showProfileModal && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-6 z-[100] animate-in fade-in duration-300">
                    <div className="bg-white rounded-[40px] shadow-2xl w-full max-w-lg overflow-hidden animate-in zoom-in-95 duration-300">
                        <div className="bg-blue-600 p-10 text-white relative">
                            <h3 className="text-3xl font-black uppercase tracking-tight">New Hotspot Profile</h3>
                            <p className="text-blue-100 mt-2 font-medium">Configure network limitations for this profile.</p>
                            <button onClick={() => setShowProfileModal(false)} className="absolute top-10 right-10 text-blue-200 hover:text-white transition-colors">
                                <X size={28} />
                            </button>
                        </div>
                        <form onSubmit={handleProfileAdd} className="p-10 space-y-8">
                            <div>
                                <label className="block text-[10px] font-black text-gray-400 uppercase mb-3 tracking-widest">Profile Name</label>
                                <input
                                    type="text"
                                    className="w-full bg-gray-50 border-none rounded-2xl px-5 py-4 focus:ring-2 focus:ring-blue-500 transition-all font-black"
                                    value={profileForm.name}
                                    onChange={e => setProfileForm({ ...profileForm, name: e.target.value })}
                                    placeholder="e.g. ULTRA_FAST_MONTHLY"
                                    required
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-8">
                                <div>
                                    <label className="block text-[10px] font-black text-gray-400 uppercase mb-3 tracking-widest">Rate Limit (Up/Down)</label>
                                    <input
                                        type="text"
                                        className="w-full bg-gray-50 border-none rounded-2xl px-5 py-4 focus:ring-2 focus:ring-blue-500 transition-all font-bold font-mono"
                                        value={profileForm.rateLimit}
                                        onChange={e => setProfileForm({ ...profileForm, rateLimit: e.target.value })}
                                        placeholder="5M/5M"
                                    />
                                </div>
                                <div>
                                    <label className="block text-[10px] font-black text-gray-400 uppercase mb-3 tracking-widest">Shared Device Count</label>
                                    <input
                                        type="number"
                                        className="w-full bg-gray-50 border-none rounded-2xl px-5 py-4 focus:ring-2 focus:ring-blue-500 transition-all font-black"
                                        value={profileForm.sharedUsers}
                                        onChange={e => setProfileForm({ ...profileForm, sharedUsers: parseInt(e.target.value) })}
                                        min="1"
                                        required
                                    />
                                </div>
                            </div>
                            <div className="pt-6 flex gap-4">
                                <button type="button" onClick={() => setShowProfileModal(false)} className="flex-1 px-6 py-4 rounded-2xl font-black text-[10px] uppercase tracking-widest text-gray-400 hover:bg-gray-50 transition-colors">Abort</button>
                                <button type="submit" className="flex-1 px-6 py-4 bg-blue-600 text-white rounded-2xl font-black text-[10px] uppercase tracking-widest hover:bg-blue-700 shadow-xl shadow-blue-100 transition-all active:scale-95">Create Profile</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}

const TabButton = ({ id, label, icon: Icon, activeTab, setActiveTab }) => (
    <button
        onClick={() => setActiveTab(id)}
        className={`flex-1 min-w-[140px] px-8 py-4 rounded-2xl font-black text-[10px] uppercase tracking-widest flex items-center justify-center gap-3 transition-all duration-300 ${activeTab === id
            ? 'bg-blue-600 text-white shadow-lg shadow-blue-100 scale-[1.02]'
            : 'text-gray-400 hover:text-gray-600 hover:bg-gray-50'
            }`}
    >
        <Icon size={16} /> {label}
    </button>
);

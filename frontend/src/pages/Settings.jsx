import React, { useState, useEffect } from 'react';
import api from '../api';
import { Settings, Key, Trash2, Copy, Check, Plus, Shield, Lock } from 'lucide-react';
import ResponsiveTable from '../components/ResponsiveTable';
import ResponsiveModal from '../components/ResponsiveModal';

export default function SettingsPage() {
    const [apiKeys, setApiKeys] = useState([]);
    const [loading, setLoading] = useState(true);
    const [createModalOpen, setCreateModalOpen] = useState(false);
    const [newKeyDescription, setNewKeyDescription] = useState('');
    const [createdKey, setCreatedKey] = useState(null); // The raw key, only shown once
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        fetchApiKeys();
    }, []);

    const fetchApiKeys = async () => {
        try {
            const response = await api.get('/api-keys/');
            setApiKeys(response.data);
        } catch (error) {
            console.error("Failed to fetch API keys:", error);
        } finally {
            setLoading(false);
        }
    };

    const handleCreateKey = async (e) => {
        e.preventDefault();
        try {
            const response = await api.post('/api-keys/', { description: newKeyDescription });
            setCreatedKey(response.data); // Contains the full key
            setNewKeyDescription('');
            fetchApiKeys(); // Refresh list
        } catch (error) {
            console.error("Failed to create API key:", error);
            const errorMessage = error.response?.data?.detail || "Failed to create key. Please try again.";
            alert(errorMessage);
        }
    };

    const handleRevokeKey = async (id) => {
        if (!window.confirm("Are you sure you want to revoke this API key? This will immediately break any integrations using it.")) return;
        try {
            await api.delete(`/api-keys/${id}`);
            fetchApiKeys();
        } catch (error) {
            console.error("Failed to revoke key:", error);
        }
    };

    const copyToClipboard = (text) => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="p-6 max-w-7xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center gap-2">
                        <Settings className="w-8 h-8 text-gray-400" />
                        Settings
                    </h1>
                    <p className="text-gray-500 font-medium mt-1">Manage your organization and integrations.</p>
                </div>
            </div>

            {/* Content Tabs */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left Column: API Keys (Takes up 2 cols) */}
                <div className="lg:col-span-2 space-y-6">
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                        <div className="p-6 border-b border-gray-100 flex items-center justify-between">
                            <div>
                                <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                                    <Key className="w-5 h-5 text-blue-500" />
                                    API Keys
                                </h2>
                                <p className="text-sm text-gray-500 mt-1">Manage keys for external integrations like Hotfly.net.</p>
                            </div>
                            <button
                                onClick={() => setCreateModalOpen(true)}
                                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-xl text-sm font-bold flex items-center gap-2 transition-colors shadow-lg shadow-blue-100"
                            >
                                <Plus size={18} />
                                Create New Key
                            </button>
                        </div>

                        <div className="overflow-hidden">
                            <ResponsiveTable
                                data={apiKeys}
                                columns={[
                                    {
                                        header: 'Description',
                                        accessor: 'description',
                                        render: (key) => <span className="font-bold text-gray-900">{key.description || 'Untitled Key'}</span>
                                    },
                                    {
                                        header: 'Key Preview',
                                        accessor: 'key',
                                        render: (key) => <span className="font-mono text-gray-500 text-xs">{key.key.substring(0, 10)}...****************</span>
                                    },
                                    {
                                        header: 'Created',
                                        accessor: 'created_at',
                                        render: (key) => <span className="text-gray-500">{new Date(key.created_at).toLocaleDateString()}</span>
                                    },
                                    {
                                        header: 'Status',
                                        accessor: 'is_active',
                                        render: (key) => (
                                            <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-bold ${key.is_active ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
                                                {key.is_active ? 'Active' : 'Revoked'}
                                            </span>
                                        )
                                    },
                                    {
                                        header: 'Actions',
                                        accessor: 'actions',
                                        render: (key) => (
                                            <div className="text-right">
                                                <button
                                                    onClick={() => handleRevokeKey(key.id)}
                                                    className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                                >
                                                    <Trash2 size={16} />
                                                </button>
                                            </div>
                                        )
                                    }
                                ]}
                                renderCard={(key) => (
                                    <div className="flex flex-col gap-3">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <Key size={16} className="text-blue-500" />
                                                <span className="font-bold text-gray-900 text-sm">{key.description || 'Untitled Key'}</span>
                                            </div>
                                            <span className={`px-2 py-1 rounded-md text-[10px] font-bold uppercase ${key.is_active ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
                                                {key.is_active ? 'Active' : 'Revoked'}
                                            </span>
                                        </div>
                                        <div className="bg-gray-50 p-2 rounded-lg text-[10px] font-mono text-gray-500 break-all">
                                            {key.key.substring(0, 10)}...****************
                                        </div>
                                        <div className="flex justify-between items-center text-xs text-gray-400">
                                            <span>Created: {new Date(key.created_at).toLocaleDateString()}</span>
                                        </div>
                                        <div className="flex justify-end border-t pt-3 mt-1">
                                            <button onClick={() => handleRevokeKey(key.id)} className="w-full text-center text-red-500 font-bold text-[10px] uppercase bg-red-50 py-2 rounded-lg">Revoke Key</button>
                                        </div>
                                    </div>
                                )}
                                emptyMessage="No API keys found. Create one to get started."
                            />
                        </div>
                    </div>
                </div>

                {/* Right Column: Documentation */}
                <div className="lg:col-span-1">
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden sticky top-6">
                        <div className="p-6 bg-blue-50/50 border-b border-blue-100">
                            <h2 className="text-lg font-bold text-blue-900 flex items-center gap-2">
                                <Shield className="w-5 h-5 text-blue-600" />
                                API Integration Reference
                            </h2>
                        </div>
                        <div className="p-6 space-y-6 text-sm text-gray-600 leading-relaxed max-h-[calc(100vh-200px)] overflow-y-auto custom-scrollbar">
                            {/* 1. Authentication */}
                            <div className="space-y-2">
                                <h3 className="font-black text-gray-900 uppercase text-[10px] tracking-widest flex items-center gap-2">
                                    <span className="w-5 h-5 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center text-[10px]">1</span>
                                    Authentication
                                </h3>
                                <p className="text-xs text-gray-500">Include your API Key in the <code className="font-bold text-blue-600">X-API-Key</code> header.</p>
                                <div className="bg-gray-900 text-gray-100 p-3 rounded-lg font-mono text-[10px] border border-gray-700 shadow-inner">
                                    X-API-Key: ng_sk_...
                                </div>
                            </div>

                            {/* 2. Base URL */}
                            <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
                                <h3 className="font-black text-gray-900 mb-2 uppercase text-[10px] tracking-widest flex items-center gap-2">
                                    <span className="w-5 h-5 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center text-[10px]">2</span>
                                    Base API URL
                                </h3>
                                <div className="font-mono text-blue-600 select-all break-all text-xs font-bold">https://app.netguard.fun/api/v1</div>
                                <p className="text-[10px] text-gray-400 mt-2 font-medium">All endpoints below are relative to this base URL.</p>
                            </div>

                            {/* 3. Scope */}
                            <div className="space-y-2">
                                <h3 className="font-black text-gray-900 uppercase text-[10px] tracking-widest flex items-center gap-2">
                                    <span className="w-5 h-5 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center text-[10px]">3</span>
                                    Scope & Permissions
                                </h3>
                                <div className="space-y-3">
                                    <div className="flex gap-2">
                                        <div className="w-1 h-auto bg-blue-500 rounded-full"></div>
                                        <div className="flex-1">
                                            <p className="text-xs font-bold text-gray-800">Organization Scoped</p>
                                            <p className="text-[10px] text-gray-500 leading-tight">Keys only access data within your specific organization.</p>
                                        </div>
                                    </div>
                                    <div className="flex gap-2">
                                        <div className="w-1 h-auto bg-green-500 rounded-full"></div>
                                        <div className="flex-1">
                                            <p className="text-xs font-bold text-gray-800">Full Programmatic Access</p>
                                            <p className="text-[10px] text-gray-500 leading-tight">Manage Inventory, Hotspot users, and view real-time metrics.</p>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* 4. Endpoints */}
                            <div className="space-y-6 pt-4 border-t border-gray-100">
                                <h3 className="font-black text-gray-900 uppercase text-[10px] tracking-widest flex items-center gap-2">
                                    <span className="w-5 h-5 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center text-[10px]">4</span>
                                    Key Endpoints
                                </h3>

                                {/* Inventory */}
                                <div className="space-y-3">
                                    <h4 className="font-black text-gray-400 text-[10px] uppercase tracking-tighter flex items-center gap-1.5">
                                        <span className="p-1 bg-gray-100 rounded">📦</span> Inventory Management
                                    </h4>
                                    <div className="grid gap-2">
                                        {[
                                            { method: 'GET', path: '/inventory/devices', desc: 'List all devices and UUIDs' },
                                            { method: 'GET', path: '/inventory/devices/{id}', desc: 'Get specific device details' },
                                            { method: 'GET', path: '/inventory/sites', desc: 'List all organization sites' },
                                            { method: 'POST', path: '/inventory/devices/{id}/provision-wireguard', desc: 'Get MikroTik VPN script' }
                                        ].map((ep, i) => (
                                            <div key={i} className="group p-2 hover:bg-gray-50 rounded-lg transition-colors border border-transparent hover:border-gray-100">
                                                <div className="flex items-center gap-2">
                                                    <span className={`text-[9px] font-black px-1.5 py-0.5 rounded ${ep.method === 'GET' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'}`}>{ep.method}</span>
                                                    <code className="text-xs font-bold text-gray-700">{ep.path}</code>
                                                </div>
                                                <p className="text-[10px] text-gray-400 mt-1 pl-1">{ep.desc}</p>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                <div className="space-y-3">
                                    <h4 className="font-black text-gray-400 text-[10px] uppercase tracking-tighter flex items-center gap-1.5">
                                        <span className="p-1 bg-gray-100 rounded">🎫</span> Hotspot Integration
                                    </h4>
                                    <div className="grid gap-2">
                                        {[
                                            { method: 'POST', path: '/hotspot/{id}/users/batch', desc: 'Generate unique vouchers (auto-timestamped)' },
                                            { method: 'GET', path: '/hotspot/{id}/reports', desc: 'Sales report (params: period, start_date, end_date)' },
                                            { method: 'GET', path: '/hotspot/{id}/profiles', desc: 'List profiles with custom prices' },
                                            { method: 'POST', path: '/hotspot/{id}/profiles/{name}/settings', desc: 'Set profile price & currency' },
                                            { method: 'GET', path: '/hotspot/{id}/active', desc: 'List active hotspot sessions' }
                                        ].map((ep, i) => (
                                            <div key={i} className="group p-2 hover:bg-gray-50 rounded-lg transition-colors border border-transparent hover:border-gray-100">
                                                <div className="flex items-center gap-2">
                                                    <span className={`text-[9px] font-black px-1.5 py-0.5 rounded ${ep.method === 'GET' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'}`}>{ep.method}</span>
                                                    <code className="text-xs font-bold text-gray-700">{ep.path}</code>
                                                </div>
                                                <p className="text-[10px] text-gray-400 mt-1 pl-1">{ep.desc}</p>
                                            </div>
                                        ))}
                                    </div>

                                    {/* JSON Example Cards */}
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                                        <div className="bg-gray-900 rounded-xl overflow-hidden shadow-lg border border-gray-800">
                                            <div className="px-3 py-2 bg-gray-800/50 border-b border-gray-700 flex justify-between items-center">
                                                <span className="text-[9px] font-black text-gray-400 uppercase tracking-widest">Batch Payload (JSON)</span>
                                                <button onClick={() => copyToClipboard(`{
  "qty": 10,
  "prefix": "wifi",
  "random_mode": true,
  "time_limit": "1h"
}`)} className="text-gray-500 hover:text-white transition-colors">
                                                    <Copy size={12} />
                                                </button>
                                            </div>
                                            <div className="p-3 font-mono text-[10px] text-blue-300 overflow-x-auto">
                                                {`{
  "qty": 10,
  "prefix": "auto",
  "random_mode": true,
  "time_limit": "1h",
  "data_limit": "500M"
}`}
                                            </div>
                                        </div>

                                        <div className="bg-gray-900 rounded-xl overflow-hidden shadow-lg border border-gray-800">
                                            <div className="px-3 py-2 bg-gray-800/50 border-b border-gray-700 flex justify-between items-center">
                                                <span className="text-[9px] font-black text-gray-400 uppercase tracking-widest">Profile Settings (JSON)</span>
                                                <button onClick={() => copyToClipboard(`{
  "price": 1000,
  "currency": "TZS"
}`)} className="text-gray-500 hover:text-white transition-colors">
                                                    <Copy size={12} />
                                                </button>
                                            </div>
                                            <div className="p-3 font-mono text-[10px] text-green-300 overflow-x-auto">
                                                {`{
  "price": 1000,
  "currency": "TZS"
}`}
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Monitoring */}
                                <div className="space-y-3">
                                    <h4 className="font-black text-gray-400 text-[10px] uppercase tracking-tighter flex items-center gap-1.5">
                                        <span className="p-1 bg-gray-100 rounded">📈</span> Monitoring & Health
                                    </h4>
                                    <div className="grid gap-2">
                                        {[
                                            { method: 'GET', path: '/monitoring/metrics/latest', desc: 'Get current CPU, clients, etc.' },
                                            { method: 'GET', path: '/monitoring/metrics/history', desc: 'Query historical time-series' },
                                            { method: 'GET', path: '/monitoring/alerts', desc: 'List active system alerts' }
                                        ].map((ep, i) => (
                                            <div key={i} className="group p-2 hover:bg-gray-50 rounded-lg transition-colors border border-transparent hover:border-gray-100">
                                                <div className="flex items-center gap-2">
                                                    <span className={`text-[9px] font-black px-1.5 py-0.5 rounded bg-purple-100 text-purple-700`}>GET</span>
                                                    <code className="text-xs font-bold text-gray-700">{ep.path}</code>
                                                </div>
                                                <p className="text-[10px] text-gray-400 mt-1 pl-1">{ep.desc}</p>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Agents Trigger */}
                                <div className="space-y-3">
                                    <h4 className="font-black text-gray-400 text-[10px] uppercase tracking-tighter flex items-center gap-1.5">
                                        <span className="p-1 bg-gray-100 rounded">🤖</span> Manual Control
                                    </h4>
                                    <div className="grid gap-2">
                                        <div className="group p-2 hover:bg-gray-50 rounded-lg transition-colors border border-transparent hover:border-gray-100">
                                            <div className="flex items-center gap-2">
                                                <span className={`text-[9px] font-black px-1.5 py-0.5 rounded bg-blue-100 text-blue-700`}>POST</span>
                                                <code className="text-xs font-bold text-gray-700">/agents/trigger</code>
                                            </div>
                                            <p className="text-[10px] text-gray-400 mt-1 pl-1">Manually run agents via Redis signal.</p>
                                        </div>
                                    </div>
                                    <div className="mt-2 bg-gray-900 rounded-xl overflow-hidden border border-gray-800">
                                        <div className="px-3 py-1.5 bg-gray-800/30 border-b border-gray-700 text-[8px] font-black text-gray-500 uppercase tracking-widest">Trigger Body</div>
                                        <div className="p-2 font-mono text-[10px] text-green-400 whitespace-pre">
                                            {`{ "agent_name": "monitor" }`}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* 5. CURL */}
                            <div className="pt-6 border-t border-gray-100">
                                <h3 className="font-black text-gray-900 uppercase text-[10px] tracking-widest mb-3 flex items-center gap-2">
                                    <span className="w-5 h-5 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center text-[10px]">5</span>
                                    CURL Example
                                </h3>
                                <div className="bg-gray-900 text-gray-400 p-3 rounded-lg font-mono text-[9px] overflow-x-auto border border-gray-700 leading-normal">
                                    <span className="text-blue-400">curl</span> -X GET <span className="text-green-400">"https://app.netguard.fun/api/v1/inventory/devices"</span> \<br />
                                    &nbsp;&nbsp;&nbsp;&nbsp; -H <span className="text-orange-400">"X-API-Key: YOUR_KEY"</span>
                                </div>
                            </div>

                            {/* Security Warning */}
                            <div className="p-4 bg-red-50 rounded-xl border border-red-100 mt-6 group hover:bg-red-100/50 transition-colors">
                                <h4 className="font-black text-red-900 text-[10px] uppercase mb-2 flex items-center gap-2">
                                    <Shield size={14} className="text-red-600 animate-pulse" />
                                    Security Protocol
                                </h4>
                                <ul className="text-[10px] text-red-700 space-y-1.5 font-medium leading-tight">
                                    <li>• Treat keys as sensitive as your main password.</li>
                                    <li>• Never commit keys to version control.</li>
                                    <li>• Revoke immediately if compromised.</li>
                                </ul>
                            </div>
                        </div>

                    </div>
                </div>

                <PasswordChangeSection />
            </div>

            {/* Create Key Modal */}
            <ResponsiveModal
                isOpen={createModalOpen}
                onClose={() => {
                    setCreateModalOpen(false);
                    setCreatedKey(null);
                }}
                title={createdKey ? "Key Generated!" : "Create API Key"}
                size="md"
            >
                {!createdKey ? (
                    <form onSubmit={handleCreateKey} className="pb-4">
                        <p className="text-gray-500 text-sm mb-6">Enter a description to identify this key.</p>
                        <input
                            type="text"
                            placeholder="e.g. Hotfly Production"
                            required
                            value={newKeyDescription}
                            onChange={(e) => setNewKeyDescription(e.target.value)}
                            className="w-full bg-gray-50 border-none rounded-xl py-4 px-5 text-sm font-bold text-gray-900 focus:ring-2 focus:ring-blue-500/20 outline-none mb-6"
                        />
                        <div className="flex gap-3">
                            <button
                                type="button"
                                onClick={() => setCreateModalOpen(false)}
                                className="flex-1 py-3 font-bold text-gray-500 hover:bg-gray-50 rounded-xl transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                type="submit"
                                className="flex-1 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl transition-colors shadow-lg shadow-blue-100"
                            >
                                Generate
                            </button>
                        </div>
                    </form>
                ) : (
                    <div className="pb-4">
                        <div className="text-center mb-6">
                            <p className="text-gray-500 text-sm">Copy this key now. You won't see it again.</p>
                        </div>

                        <div className="bg-gray-50 rounded-xl p-4 mb-6 border border-gray-100 relative group">
                            <code className="text-sm font-mono text-gray-800 break-all">
                                {createdKey.key}
                            </code>
                            <button
                                onClick={() => copyToClipboard(createdKey.key)}
                                className="absolute top-2 right-2 p-2 bg-white rounded-lg shadow-sm border border-gray-100 text-gray-500 hover:text-blue-600 transition-colors"
                            >
                                {copied ? <Check size={16} className="text-green-500" /> : <Copy size={16} />}
                            </button>
                        </div>

                        <button
                            onClick={() => {
                                setCreateModalOpen(false);
                                setCreatedKey(null);
                            }}
                            className="w-full py-4 bg-gray-900 hover:bg-gray-800 text-white font-bold rounded-xl transition-colors shadow-lg"
                        >
                            Done
                        </button>
                    </div>
                )}
            </ResponsiveModal>
        </div >
    );
}

const PasswordChangeSection = () => {
    const [oldPassword, setOldPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [loading, setLoading] = useState(false);

    const handleChangePassword = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            await api.post('/auth/change-password', { old_password: oldPassword, new_password: newPassword });
            alert("Password updated successfully");
            setOldPassword('');
            setNewPassword('');
        } catch (error) {
            alert(error.response?.data?.detail || "Failed to update password");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="lg:col-span-3"> {/* Full width */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                <div className="p-6 border-b border-gray-100">
                    <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                        <Lock className="w-5 h-5 text-purple-500" />
                        Profile Settings
                    </h2>
                </div>
                <div className="p-6">
                    <form onSubmit={handleChangePassword} className="max-w-md space-y-4">
                        <div>
                            <label className="block text-sm font-bold text-gray-700 mb-1">Current Password</label>
                            <input
                                type="password"
                                required
                                value={oldPassword}
                                onChange={e => setOldPassword(e.target.value)}
                                className="w-full bg-gray-50 border-none rounded-xl py-3 px-4 text-sm font-medium focus:ring-2 focus:ring-purple-500/20 outline-none"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-bold text-gray-700 mb-1">New Password</label>
                            <input
                                type="password"
                                required
                                value={newPassword}
                                onChange={e => setNewPassword(e.target.value)}
                                className="w-full bg-gray-50 border-none rounded-xl py-3 px-4 text-sm font-medium focus:ring-2 focus:ring-purple-500/20 outline-none"
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={loading}
                            className="bg-gray-900 hover:bg-gray-800 text-white px-6 py-3 rounded-xl text-sm font-bold transition-colors shadow-lg disabled:opacity-50"
                        >
                            {loading ? 'Updating...' : 'Update Password'}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
};

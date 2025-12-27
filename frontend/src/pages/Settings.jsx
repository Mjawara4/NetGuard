import React, { useState, useEffect } from 'react';
import api from '../api';
import { Settings, Key, Trash2, Copy, Check, Plus, Shield, Lock } from 'lucide-react';

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

                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-sm">
                                <thead className="bg-gray-50 text-gray-500 font-medium border-b border-gray-100">
                                    <tr>
                                        <th className="px-6 py-4">Description</th>
                                        <th className="px-6 py-4">Key Preview</th>
                                        <th className="px-6 py-4">Created</th>
                                        <th className="px-6 py-4">Status</th>
                                        <th className="px-6 py-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-100">
                                    {loading ? (
                                        <tr><td colSpan="5" className="p-6 text-center text-gray-400">Loading keys...</td></tr>
                                    ) : apiKeys.length === 0 ? (
                                        <tr><td colSpan="5" className="p-6 text-center text-gray-400">No API keys found. Create one to get started.</td></tr>
                                    ) : (
                                        apiKeys.map((key) => (
                                            <tr key={key.id} className="group hover:bg-gray-50 transition-colors">
                                                <td className="px-6 py-4 font-bold text-gray-900">{key.description || 'Untitled Key'}</td>
                                                <td className="px-6 py-4 font-mono text-gray-500 text-xs">
                                                    {key.key.substring(0, 10)}...****************
                                                </td>
                                                <td className="px-6 py-4 text-gray-500">
                                                    {new Date(key.created_at).toLocaleDateString()}
                                                </td>
                                                <td className="px-6 py-4">
                                                    <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-bold ${key.is_active ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
                                                        {key.is_active ? 'Active' : 'Revoked'}
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4 text-right">
                                                    <button
                                                        onClick={() => handleRevokeKey(key.id)}
                                                        className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                                    >
                                                        <Trash2 size={16} />
                                                    </button>
                                                </td>
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </table>
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
                        <div className="p-6 space-y-6 text-sm text-gray-600 leading-relaxed max-h-[calc(100vh-200px)] overflow-y-auto">

                            {/* 1. Authentication */}
                            <div className="space-y-2">
                                <h3 className="font-bold text-gray-900">1. Authentication</h3>
                                <p>All requests must include your API Key in the header.</p>
                                <div className="bg-gray-900 text-gray-100 p-3 rounded-lg font-mono text-xs border border-gray-700">
                                    X-API-Key: ng_sk_...
                                </div>
                            </div>

                            {/* 2. Base URL */}
                            <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
                                <h3 className="font-bold text-gray-900 mb-1 uppercase text-[10px] tracking-widest">Base API URL</h3>
                                <div className="font-mono text-blue-600 select-all break-all">https://app.netguard.fun/api/v1</div>
                                <p className="text-[10px] text-gray-400 mt-2">All endpoints below are relative to this URL.</p>
                            </div>

                            {/* 3. Scope */}
                            <div className="space-y-2">
                                <h3 className="font-bold text-gray-900">3. Scope & Permissions</h3>
                                <ul className="list-disc list-inside space-y-1 text-xs">
                                    <li><strong>Org Scoped:</strong> Keys only access your organization's data.</li>
                                    <li><strong>Full Access:</strong> Manage Devices, Sites, Hotspots, and Monitoring.</li>
                                </ul>
                            </div>

                            {/* 4. Endpoints */}
                            <div className="space-y-4">
                                <h3 className="font-bold text-gray-900 border-b pb-2">4. Key Endpoints</h3>

                                {/* Inventory */}
                                <div>
                                    <h4 className="font-semibold text-gray-800 text-xs uppercase mb-2">📦 Inventory</h4>
                                    <div className="space-y-2">
                                        <div>
                                            <p className="text-xs font-mono text-purple-600">GET /inventory/devices</p>
                                            <p className="text-[10px] text-gray-500">List all devices (UUIDs required for other calls)</p>
                                        </div>
                                        <div>
                                            <p className="text-xs font-mono text-purple-600">GET /inventory/sites</p>
                                            <p className="text-[10px] text-gray-500">List all sites</p>
                                        </div>
                                    </div>
                                </div>

                                {/* Hotspot */}
                                <div>
                                    <h4 className="font-semibold text-gray-800 text-xs uppercase mb-2">🎫 Hotspot (Hotfly)</h4>
                                    <div className="space-y-2">
                                        <div>
                                            <p className="text-xs font-mono text-blue-600">POST /hotspot/{'{id}'}/users/batch</p>
                                            <p className="text-[10px] text-gray-500">Batch generate vouchers</p>
                                        </div>
                                        <div>
                                            <p className="text-xs font-mono text-blue-600">GET /hotspot/{'{id}'}/active</p>
                                            <p className="text-[10px] text-gray-500">List active users</p>
                                        </div>
                                        <div>
                                            <p className="text-xs font-mono text-blue-600">GET /hotspot/{'{id}'}/profiles</p>
                                            <p className="text-[10px] text-gray-500">List hotspot profiles</p>
                                        </div>
                                    </div>
                                    {/* JSON Example */}
                                    <div className="mt-2">
                                        <p className="text-[10px] font-bold text-gray-500 mb-1">Batch JSON Example:</p>
                                        <div className="bg-gray-900 text-gray-100 p-2 rounded-lg font-mono text-[10px] overflow-x-auto border border-gray-700 whitespace-pre">
                                            {`{
  "qty": 5,
  "prefix": "auto",
  "data_limit": "500M",
  "time_limit": "24h"
}`}
                                        </div>
                                    </div>
                                </div>

                                {/* Monitoring */}
                                <div>
                                    <h4 className="font-semibold text-gray-800 text-xs uppercase mb-2">📈 Monitoring</h4>
                                    <div className="space-y-2">
                                        <div>
                                            <p className="text-xs font-mono text-green-600">GET /monitoring/metrics/latest?device_id=...</p>
                                            <p className="text-[10px] text-gray-500">Get real-time metrics</p>
                                        </div>
                                        <div>
                                            <p className="text-xs font-mono text-green-600">GET /monitoring/alerts</p>
                                            <p className="text-[10px] text-gray-500">Get active alerts</p>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* 5. Example */}
                            <div className="space-y-2">
                                <h3 className="font-bold text-gray-900">5. cURL Example</h3>
                                <div className="bg-gray-900 text-gray-100 p-3 rounded-lg font-mono text-[10px] overflow-x-auto border border-gray-700 whitespace-pre">
                                    {`curl -X GET "https://app.netguard.fun/api/v1/inventory/devices" \\
     -H "X-API-Key: ng_sk_..."`}
                                </div>
                            </div>

                            {/* Security */}
                            <div className="p-4 bg-yellow-50 rounded-xl border border-yellow-100">
                                <h4 className="font-bold text-yellow-800 text-xs uppercase mb-1 flex items-center gap-2">
                                    <Shield size={12} />
                                    Security Warning
                                </h4>
                                <p className="text-yellow-700 text-xs">
                                    Treat this key like your admin password. Never share it publicly.
                                </p>
                            </div>

                        </div>
                    </div>
                </div>
            </div>

            {/* Create Key Modal */}
            {createModalOpen && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-3xl w-full max-w-md shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
                        {!createdKey ? (
                            <form onSubmit={handleCreateKey} className="p-8">
                                <h3 className="text-xl font-bold mb-2">Create API Key</h3>
                                <p className="text-gray-500 text-sm mb-6">Enter a description to identify this key.</p>

                                <input
                                    type="text"
                                    placeholder="e.g. Hotfly Production"
                                    required
                                    value={newKeyDescription}
                                    onChange={(e) => setNewKeyDescription(e.target.value)}
                                    className="w-full bg-gray-50 border-none rounded-xl py-3 px-4 text-sm font-bold text-gray-900 focus:ring-2 focus:ring-blue-500/20 outline-none mb-6"
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
                            <div className="p-8">
                                <div className="text-center mb-6">
                                    <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                                        <Shield className="w-8 h-8 text-green-600" />
                                    </div>
                                    <h3 className="text-xl font-bold mb-2">Key Generated!</h3>
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
                                    className="w-full py-3 bg-gray-900 hover:bg-gray-800 text-white font-bold rounded-xl transition-colors shadow-lg"
                                >
                                    Done
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
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

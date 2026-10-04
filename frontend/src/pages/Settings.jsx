import React, { useState, useEffect } from 'react';
import api from '../api';
import { Settings, Key, Trash2, Copy, Check, Plus, Shield, Lock } from 'lucide-react';
import { PageHeader, Badge, Card } from '../components/ui';
import ResponsiveTable from '../components/ResponsiveTable';
import ResponsiveModal from '../components/ResponsiveModal';
import PaymentSettings from './PaymentSettings';

export default function SettingsPage() {
    const [apiKeys, setApiKeys] = useState([]);
    const [loading, setLoading] = useState(true);
    const [createModalOpen, setCreateModalOpen] = useState(false);
    const [newKeyDescription, setNewKeyDescription] = useState('');
    const [createdKey, setCreatedKey] = useState(null);
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
            setCreatedKey(response.data);
            setNewKeyDescription('');
            fetchApiKeys();
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
        <div className="page-container">
            <div className="content-max space-y-6">
                <PageHeader
                    title="Settings"
                    subtitle="Manage your organization and integrations."
                />

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div className="lg:col-span-2 space-y-6">
                        <Card padding="p-0">
                            <div className="p-6 border-b border-ink-200 dark:border-ink-700 flex items-center justify-between">
                                <div>
                                    <h2 className="text-lg font-bold text-ink-900 dark:text-ink-50 flex items-center gap-2">
                                        <Key className="w-5 h-5 text-signal-600 dark:text-signal-300" />
                                        API Keys
                                    </h2>
                                    <p className="text-sm text-ink-500 dark:text-ink-400 mt-1">Manage keys for external integrations like Hotfly.net.</p>
                                </div>
                                <button
                                    onClick={() => setCreateModalOpen(true)}
                                    className="bg-signal-600 hover:bg-signal-700 text-ink-50 px-4 py-2 rounded-md text-sm font-bold flex items-center gap-2 transition-colors shadow-lg"
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
                                            render: (key) => <span className="font-bold text-ink-900 dark:text-ink-50">{key.description || 'Untitled Key'}</span>
                                        },
                                        {
                                            header: 'Key Preview',
                                            accessor: 'key',
                                            render: (key) => <span className="font-mono text-ink-500 dark:text-ink-400 text-xs">{key.key.substring(0, 10)}...****************</span>
                                        },
                                        {
                                            header: 'Created',
                                            accessor: 'created_at',
                                            render: (key) => <span className="text-ink-500 dark:text-ink-400">{new Date(key.created_at).toLocaleDateString()}</span>
                                        },
                                        {
                                            header: 'Status',
                                            accessor: 'is_active',
                                            render: (key) => (
                                                <Badge variant={key.is_active ? 'success' : 'critical'}>
                                                    {key.is_active ? 'Active' : 'Revoked'}
                                                </Badge>
                                            )
                                        },
                                        {
                                            header: 'Actions',
                                            accessor: 'actions',
                                            render: (key) => (
                                                <div className="text-right">
                                                    <button
                                                        onClick={() => handleRevokeKey(key.id)}
                                                        className="p-2 text-ink-500 hover:text-down hover:bg-down/20 dark:hover:bg-down/20 rounded-lg transition-colors dark:text-ink-400"
                                                        aria-label="Revoke key"
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
                                                    <Key size={16} className="text-signal-600 dark:text-signal-300" />
                                                    <span className="font-bold text-ink-900 dark:text-ink-50 text-sm">{key.description || 'Untitled Key'}</span>
                                                </div>
                                                <Badge variant={key.is_active ? 'success' : 'critical'}>
                                                    {key.is_active ? 'Active' : 'Revoked'}
                                                </Badge>
                                            </div>
                                            <div className="bg-ink-50 dark:bg-ink-900 p-2 rounded-lg text-xs font-mono text-ink-500 dark:text-ink-400 break-all">
                                                {key.key.substring(0, 10)}...****************
                                            </div>
                                            <div className="flex justify-between items-center text-xs text-ink-500 dark:text-ink-400">
                                                <span>Created: {new Date(key.created_at).toLocaleDateString()}</span>
                                            </div>
                                            <div className="flex justify-end border-t dark:border-ink-700 pt-3 mt-1">
                                                <button onClick={() => handleRevokeKey(key.id)} className="w-full text-center text-down font-bold text-xs bg-down/10 dark:bg-down/20 py-2 rounded-lg dark:text-ink-100">Revoke Key</button>
                                            </div>
                                        </div>
                                    )}
                                    emptyMessage="No API keys found. Create one to get started."
                                />
                            </div>
                        </Card>
                    </div>

                    <div className="lg:col-span-1">
                        <Card padding="p-0" className="sticky top-6">
                            <div className="p-6 bg-signal-600/5 dark:bg-signal-600/10 border-b border-signal-600/20 dark:border-signal-600/30">
                                <h2 className="text-lg font-bold text-signal-700 dark:text-ink-50 flex items-center gap-2">
                                    <Shield className="w-5 h-5 text-signal-600 dark:text-signal-300" />
                                    API Integration Reference
                                </h2>
                            </div>
                            <div className="p-6 space-y-6 text-sm text-ink-500 dark:text-ink-100 leading-relaxed max-h-[calc(100vh-200px)] overflow-y-auto custom-scrollbar">
                                <div className="space-y-2">
                                    <h3 className="font-bold text-ink-900 dark:text-ink-50 text-xs flex items-center gap-2">
                                        <span className="w-5 h-5 bg-signal-600/10 dark:bg-signal-600/20 text-signal-600 dark:text-ink-50 rounded-lg flex items-center justify-center text-xs">1</span>
                                        Authentication
                                    </h3>
                                    <p className="text-xs text-ink-500 dark:text-ink-400">Include your API Key in the <code className="font-bold text-signal-600 dark:text-signal-300">X-API-Key</code> header.</p>
                                    <div className="bg-ink-900 text-ink-50 p-3 rounded-lg font-mono text-xs border border-ink-700 shadow-inner">
                                        X-API-Key: ng_sk_...
                                    </div>
                                </div>

                                <div className="p-4 bg-ink-50 dark:bg-ink-900 rounded-md border border-ink-200 dark:border-ink-700">
                                    <h3 className="font-bold text-ink-900 dark:text-ink-50 mb-2 text-xs flex items-center gap-2">
                                        <span className="w-5 h-5 bg-signal-600/10 dark:bg-signal-600/20 text-signal-600 dark:text-ink-50 rounded-lg flex items-center justify-center text-xs">2</span>
                                        Base API URL
                                    </h3>
                                    <div className="font-mono text-signal-600 dark:text-signal-300 select-all break-all text-xs font-bold">https://app.netguard.fun/api/v1</div>
                                    <p className="text-xs text-ink-500 dark:text-ink-400 mt-2 font-medium">All endpoints below are relative to this base URL.</p>
                                </div>

                                <div className="space-y-2">
                                    <h3 className="font-bold text-ink-900 dark:text-ink-50 text-xs flex items-center gap-2">
                                        <span className="w-5 h-5 bg-signal-600/10 dark:bg-signal-600/20 text-signal-600 dark:text-ink-50 rounded-lg flex items-center justify-center text-xs">3</span>
                                        Scope & Permissions
                                    </h3>
                                    <div className="space-y-3">
                                        <div className="flex gap-2">
                                            <div className="w-1 h-auto bg-signal-500 rounded-full"></div>
                                            <div className="flex-1">
                                                <p className="text-xs font-bold text-ink-900 dark:text-ink-100">Organization Scoped</p>
                                                <p className="text-xs text-ink-500 dark:text-ink-400 leading-tight">Keys only access data within your specific organization.</p>
                                            </div>
                                        </div>
                                        <div className="flex gap-2">
                                            <div className="w-1 h-auto bg-up rounded-full"></div>
                                            <div className="flex-1">
                                                <p className="text-xs font-bold text-ink-900 dark:text-ink-100">Full Programmatic Access</p>
                                                <p className="text-xs text-ink-500 dark:text-ink-400 leading-tight">Manage Inventory, Hotspot users, and view real-time metrics.</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div className="space-y-6 pt-4 border-t border-ink-200 dark:border-ink-700">
                                    <h3 className="font-bold text-ink-900 dark:text-ink-50 text-xs flex items-center gap-2">
                                        <span className="w-5 h-5 bg-signal-600/10 dark:bg-signal-600/20 text-signal-600 dark:text-ink-50 rounded-lg flex items-center justify-center text-xs">4</span>
                                        Key Endpoints
                                    </h3>

                                    <div className="space-y-3">
                                        <h4 className="font-bold text-ink-900 dark:text-ink-50 text-xs tracking-tighter flex items-center gap-1.5">
                                            <span className="p-1 bg-ink-100 dark:bg-ink-800 rounded">Inventory</span> Management
                                        </h4>
                                        <div className="grid gap-2">
                                            {[
                                                { method: 'GET', path: '/inventory/devices', desc: 'List all devices and UUIDs' },
                                                { method: 'GET', path: '/inventory/devices/{id}', desc: 'Get specific device details' },
                                                { method: 'GET', path: '/inventory/sites', desc: 'List all organization sites' },
                                                { method: 'POST', path: '/inventory/devices/{id}/provision-wireguard', desc: 'Get MikroTik VPN script' }
                                            ].map((ep, i) => (
                                                <div key={i} className="group p-2 hover:bg-ink-50 dark:hover:bg-ink-800 rounded-lg transition-colors border border-transparent hover:border-ink-200 dark:hover:border-ink-700">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-xs font-bold px-1.5 py-0.5 rounded bg-signal-600/10 dark:bg-signal-600/20 text-signal-700 dark:text-ink-50">{ep.method}</span>
                                                        <code className="text-xs font-bold text-ink-900 dark:text-ink-100">{ep.path}</code>
                                                    </div>
                                                    <p className="text-xs text-ink-500 dark:text-ink-400 mt-1 pl-1">{ep.desc}</p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>

                                <div className="pt-6 border-t border-ink-200 dark:border-ink-700">
                                    <h3 className="font-bold text-ink-900 dark:text-ink-50 text-xs mb-3 flex items-center gap-2">
                                        <span className="w-5 h-5 bg-signal-600/10 dark:bg-signal-600/20 text-signal-600 dark:text-ink-50 rounded-lg flex items-center justify-center text-xs">5</span>
                                        CURL Example
                                    </h3>
                                    <div className="bg-ink-900 text-ink-300 p-3 rounded-lg font-mono text-xs overflow-x-auto border border-ink-700 leading-normal">
                                        <span className="text-ink-50">curl</span> -X GET <span className="text-ink-100">"https://app.netguard.fun/api/v1/inventory/devices"</span> \<br />
                                        &nbsp;&nbsp;&nbsp;&nbsp; -H <span className="text-ink-100">"X-API-Key: YOUR_KEY"</span>
                                    </div>
                                </div>

                                <div className="p-4 bg-down/10 dark:bg-down/10 rounded-md border border-down/20 dark:border-down/30 mt-6 group hover:bg-down/20 dark:hover:bg-down/20 transition-colors">
                                    <h4 className="font-bold text-down dark:text-ink-100 text-xs mb-2 flex items-center gap-2">
                                        <Shield size={14} className="text-down animate-pulse dark:text-ink-100" />
                                        Security Protocol
                                    </h4>
                                    <ul className="text-xs text-down dark:text-ink-100 space-y-1.5 font-medium leading-tight">
                                        <li>• Treat keys as sensitive as your main password.</li>
                                        <li>• Never commit keys to version control.</li>
                                        <li>• Revoke immediately if compromised.</li>
                                    </ul>
                                </div>
                            </div>
                        </Card>
                    </div>

                    <PaymentSettings />
                    <PasswordChangeSection />
                </div>

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
                            <p className="text-ink-500 dark:text-ink-400 text-sm mb-6">Enter a description to identify this key.</p>
                            <input
                                type="text"
                                placeholder="e.g. Hotfly Production"
                                required
                                value={newKeyDescription}
                                onChange={(e) => setNewKeyDescription(e.target.value)}
                                className="w-full bg-ink-50 dark:bg-ink-900 border-none rounded-md py-4 px-5 text-sm font-bold text-ink-900 dark:text-ink-50 placeholder:text-ink-500 dark:placeholder:text-ink-400 focus:ring-2 focus:ring-signal-500/20 outline-none mb-6"
                            />
                            <div className="flex gap-3">
                                <button
                                    type="button"
                                    onClick={() => setCreateModalOpen(false)}
                                    className="flex-1 py-3 font-bold text-ink-500 hover:bg-ink-50 dark:hover:bg-ink-800 rounded-md transition-colors dark:text-ink-400"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="flex-1 py-3 bg-signal-600 hover:bg-signal-700 text-ink-50 font-bold rounded-md transition-colors shadow-lg"
                                >
                                    Generate
                                </button>
                            </div>
                        </form>
                    ) : (
                        <div className="pb-4">
                            <div className="text-center mb-6">
                                <p className="text-ink-500 dark:text-ink-400 text-sm">Copy this key now. You won&apos;t see it again.</p>
                            </div>

                            <div className="bg-ink-50 dark:bg-ink-900 rounded-md p-4 mb-6 border border-ink-200 dark:border-ink-700 relative group">
                                <code className="text-sm font-mono text-ink-900 dark:text-ink-100 break-all">
                                    {createdKey.key}
                                </code>
                                <button
                                    onClick={() => copyToClipboard(createdKey.key)}
                                    className="absolute top-2 right-2 p-2 bg-white dark:bg-ink-800 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700 text-ink-500 hover:text-signal-600 transition-colors dark:text-ink-400"
                                    aria-label="Copy key"
                                >
                                    {copied ? <Check size={16} className="text-up dark:text-ink-100" /> : <Copy size={16} />}
                                </button>
                            </div>

                            <button
                                onClick={() => {
                                    setCreateModalOpen(false);
                                    setCreatedKey(null);
                                }}
                                className="w-full py-4 bg-ink-900 hover:bg-ink-800 text-ink-50 font-bold rounded-md transition-colors shadow-lg"
                            >
                                Done
                            </button>
                        </div>
                    )}
                </ResponsiveModal>
            </div>
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
        <div className="lg:col-span-3">
            <Card padding="p-0">
                <div className="p-6 border-b border-ink-200 dark:border-ink-700">
                    <h2 className="text-lg font-bold text-ink-900 dark:text-ink-50 flex items-center gap-2">
                        <Lock className="w-5 h-5 text-signal-600 dark:text-signal-300" />
                        Profile Settings
                    </h2>
                </div>
                <div className="p-6">
                    <form onSubmit={handleChangePassword} className="max-w-md space-y-4">
                        <div>
                            <label className="block text-sm font-bold text-ink-900 dark:text-ink-100 mb-1">Current Password</label>
                            <input
                                type="password"
                                required
                                value={oldPassword}
                                onChange={e => setOldPassword(e.target.value)}
                                className="w-full bg-ink-50 dark:bg-ink-900 border-none rounded-md py-3 px-4 text-sm font-medium text-ink-900 dark:text-ink-50 focus:ring-2 focus:ring-signal-500/20 outline-none"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-bold text-ink-900 dark:text-ink-100 mb-1">New Password</label>
                            <input
                                type="password"
                                required
                                value={newPassword}
                                onChange={e => setNewPassword(e.target.value)}
                                className="w-full bg-ink-50 dark:bg-ink-900 border-none rounded-md py-3 px-4 text-sm font-medium text-ink-900 dark:text-ink-50 focus:ring-2 focus:ring-signal-500/20 outline-none"
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={loading}
                            className="bg-ink-900 hover:bg-ink-800 text-ink-50 px-6 py-3 rounded-md text-sm font-bold transition-colors shadow-lg disabled:opacity-50"
                        >
                            {loading ? 'Updating...' : 'Update Password'}
                        </button>
                    </form>
                </div>
            </Card>
        </div>
    );
};

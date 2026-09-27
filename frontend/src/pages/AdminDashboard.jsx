import React, { useState, useEffect } from 'react';
import api from '../api';
import { Users, Shield, CheckCircle, XCircle, Trash2, Activity, Lock, Key, UserCircle } from 'lucide-react';
import { PageHeader, StatCard, Badge, Button } from '../components/ui';
import ResponsiveTable from '../components/ResponsiveTable';

export default function AdminDashboard() {
    const [activeTab, setActiveTab] = useState('users');
    const [users, setUsers] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (activeTab === 'users') fetchUsers();
        if (activeTab === 'security') fetchStats();
    }, [activeTab]);

    const fetchUsers = async () => {
        setLoading(true);
        try {
            const res = await api.get('/admin/users');
            setUsers(res.data);
        } catch (e) {
            console.error(e);
            alert("Failed to fetch users");
        } finally {
            setLoading(false);
        }
    };

    const fetchStats = async () => {
        try {
            const res = await api.get('/admin/security');
            setStats(res.data);
        } catch (e) {
            console.error(e);
        }
    };

    const handleAction = async (userId, action, value) => {
        if (!confirm("Are you sure?")) return;
        try {
            if (action === 'delete') {
                await api.delete(`/admin/users/${userId}`);
                setUsers(users.filter(u => u.id !== userId));
            } else if (action === 'update') {
                const user = users.find(u => u.id === userId);
                await api.put(`/admin/users/${userId}`, { ...user, ...value });
                fetchUsers();
            } else if (action === 'reset_password') {
                const newPass = prompt("Enter new password for user:");
                if (!newPass) return;
                await api.put(`/admin/users/${userId}/password`, { new_password: newPass });
                alert("Password reset successfully");
            }
        } catch (e) {
            alert("Action failed");
        }
    };

    return (
        <div className="page-container">
            <div className="content-max">
                <PageHeader title="Super Admin" accent="Console" subtitle="System-wide user management and security auditing." />

                <div className="mb-10">
                    <div className="flex bg-white dark:bg-ink-800 p-1.5 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700 gap-1.5 w-fit overflow-x-auto no-scrollbar">
                        <TabButton id="users" label="User Management" icon={Users} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="security" label="Security Audit" icon={Shield} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="account" label="My Account" icon={UserCircle} activeTab={activeTab} setActiveTab={setActiveTab} />
                    </div>
                </div>

                {activeTab === 'users' && (
                    <div className="bg-white dark:bg-ink-800 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700 overflow-hidden">
                        <ResponsiveTable
                            data={users}
                            columns={[
                                {
                                    header: 'User',
                                    accessor: 'full_name',
                                    render: (u) => (
                                        <div>
                                            <div className="font-bold text-ink-900 dark:text-ink-50">{u.full_name}</div>
                                            <div className="text-xs text-ink-500 dark:text-ink-400">{u.email}</div>
                                        </div>
                                    )
                                },
                                {
                                    header: 'Role',
                                    accessor: 'role',
                                    render: (u) => (
                                        <Badge variant="neutral">{u.role}</Badge>
                                    )
                                },
                                {
                                    header: 'Status',
                                    accessor: 'is_active',
                                    render: (u) => (
                                        u.is_active ?
                                            <span className="text-up font-bold text-xs flex items-center gap-1 dark:text-ink-100"><CheckCircle size={14} /> Active</span> :
                                            <span className="text-down font-bold text-xs flex items-center gap-1 dark:text-ink-100"><XCircle size={14} /> Inactive</span>
                                    )
                                },
                                {
                                    header: 'Actions',
                                    accessor: 'actions',
                                    render: (u) => (
                                        <div className="flex items-center justify-end gap-2 flex-wrap">
                                            {u.role !== 'super_admin' && (
                                                <>
                                                    <button
                                                        onClick={() => handleAction(u.id, 'update', { is_active: !u.is_active, role: u.role })}
                                                        className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${u.is_active ? 'bg-down/10 text-ink-900 hover:bg-down/20 dark:bg-down/20 dark:text-ink-50' : 'bg-up/10 text-ink-900 hover:bg-up/20 dark:bg-up/20 dark:text-ink-50'}`}
                                                    >
                                                        {u.is_active ? 'Deactivate' : 'Activate'}
                                                    </button>
                                                    <button
                                                        onClick={() => handleAction(u.id, 'reset_password')}
                                                        className="px-3 py-1.5 bg-warn/10 text-ink-900 hover:bg-warn/20 rounded-lg text-xs font-bold flex items-center gap-1 dark:bg-warn/20 dark:text-ink-50"
                                                    >
                                                        <Key size={12} /> Reset
                                                    </button>
                                                    <button
                                                        onClick={() => handleAction(u.id, 'delete')}
                                                        className="px-3 py-1.5 bg-ink-100 text-ink-500 hover:bg-ink-200 rounded-lg text-xs font-bold dark:bg-ink-800 dark:text-ink-100"
                                                    >
                                                        <Trash2 size={12} />
                                                    </button>
                                                </>
                                            )}
                                        </div>
                                    )
                                }
                            ]}
                            renderCard={(u) => (
                                <div className="flex flex-col gap-3">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <div className="font-bold text-ink-900 dark:text-ink-50">{u.full_name}</div>
                                            <div className="text-xs text-ink-500 dark:text-ink-400">{u.email}</div>
                                        </div>
                                        <Badge variant="neutral">{u.role}</Badge>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {u.is_active ?
                                            <span className="text-up font-bold text-xs flex items-center gap-1 dark:text-ink-100"><CheckCircle size={14} /> Active</span> :
                                            <span className="text-down font-bold text-xs flex items-center gap-1 dark:text-ink-100"><XCircle size={14} /> Inactive</span>
                                        }
                                    </div>
                                    {u.role !== 'super_admin' && (
                                        <div className="flex gap-2 pt-2 border-t dark:border-ink-700">
                                            <button onClick={() => handleAction(u.id, 'update', { is_active: !u.is_active, role: u.role })} className="flex-1 text-center py-2 rounded-lg text-xs font-bold bg-ink-50 dark:bg-ink-800 text-ink-500 dark:text-ink-100">Toggle</button>
                                            <button onClick={() => handleAction(u.id, 'reset_password')} className="flex-1 text-center py-2 rounded-lg text-xs font-bold bg-warn/10 dark:bg-warn/20 text-warn dark:text-ink-100">Reset</button>
                                            <button onClick={() => handleAction(u.id, 'delete')} className="flex-1 text-center py-2 rounded-lg text-xs font-bold bg-down/10 dark:bg-down/20 text-down dark:text-ink-100">Delete</button>
                                        </div>
                                    )}
                                </div>
                            )}
                            emptyMessage="No users found."
                        />
                    </div>
                )}

                {activeTab === 'security' && stats && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                        <StatCard label="Total Users" value={stats.total_users} icon={Users} color="blue" />
                        <StatCard label="Super Admins" value={stats.super_admins} icon={Shield} color="indigo" />
                        <StatCard label="Active API Keys" value={stats.active_api_keys} icon={Lock} color="emerald" />
                        <StatCard label="System Status" value={stats.system_status} icon={Activity} color="green" />
                    </div>
                )}

                {activeTab === 'account' && (
                    <div className="bg-white dark:bg-ink-800 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700 overflow-hidden max-w-2xl">
                        <div className="p-8 border-b border-ink-200 dark:border-ink-700">
                            <h2 className="text-xl font-bold text-ink-900 dark:text-ink-50 flex items-center gap-3">
                                <Key className="w-6 h-6 text-signal-600 dark:text-signal-300" />
                                Change My Password
                            </h2>
                            <p className="text-ink-500 dark:text-ink-400 mt-2">Update the password for your Super Admin account.</p>
                        </div>
                        <div className="p-8">
                            <PasswordChangeForm />
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

const TabButton = ({ id, label, icon: Icon, activeTab, setActiveTab }) => (
    <button
        onClick={() => setActiveTab(id)}
        className={`px-6 py-3 rounded-lg font-bold text-xs flex items-center gap-2 transition-all whitespace-nowrap ${activeTab === id
            ? 'bg-signal-600 text-ink-50 shadow-lg'
            : 'text-ink-500 dark:text-ink-400 hover:text-ink-900 hover:bg-ink-50 dark:hover:bg-ink-700 dark:hover:text-ink-100'
            }`}
    >
        <Icon size={16} /> {label}
    </button>
);

const PasswordChangeForm = () => {
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
        <form onSubmit={handleChangePassword} className="space-y-4">
            <div>
                <label className="block text-sm font-bold text-ink-900 dark:text-ink-100 mb-1">Current Password</label>
                <input
                    type="password"
                    required
                    value={oldPassword}
                    onChange={e => setOldPassword(e.target.value)}
                    className="w-full bg-ink-50 dark:bg-ink-900 border-none rounded-md py-3 px-4 text-sm font-medium text-ink-900 dark:text-ink-50 focus:ring-2 focus:ring-signal-500/20 outline-none"
                    placeholder="Enter current password"
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
                    placeholder="Enter new password"
                />
            </div>
            <button
                type="submit"
                disabled={loading}
                className="w-full bg-ink-900 hover:bg-ink-800 text-ink-50 py-3 rounded-md text-sm font-bold transition-colors shadow-lg disabled:opacity-50"
            >
                {loading ? 'Updating...' : 'Update Password'}
            </button>
        </form>
    );
};

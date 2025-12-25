import React, { useState, useEffect } from 'react';
import api from '../api';
import { Users, Shield, CheckCircle, XCircle, Trash2, Activity, Lock, Key, UserCircle } from 'lucide-react';

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
        <div className="min-h-screen bg-gray-50 pt-8 px-6 pb-12">
            <div className="max-w-7xl mx-auto">
                <div className="mb-10">
                    <h1 className="text-4xl font-black text-gray-900 tracking-tight leading-none">
                        Super Admin <span className="text-blue-600">Console</span>
                    </h1>
                    <p className="text-gray-500 mt-2 font-medium">System-wide user management and security auditing.</p>
                </div>

                <div className="mb-10">
                    <div className="flex bg-white p-1.5 rounded-3xl shadow-sm border border-gray-100 gap-1.5 w-fit">
                        <TabButton id="users" label="User Management" icon={Users} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="security" label="Security Audit" icon={Shield} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="account" label="My Account" icon={UserCircle} activeTab={activeTab} setActiveTab={setActiveTab} />
                    </div>
                </div>

                {activeTab === 'users' && (
                    <div className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
                        <div className="overflow-x-auto">
                            <table className="min-w-full">
                                <thead className="bg-gray-50 text-[10px] font-black text-gray-400 uppercase tracking-widest text-left">
                                    <tr>
                                        <th className="px-8 py-4">User</th>
                                        <th className="px-8 py-4">Role</th>
                                        <th className="px-8 py-4">Status</th>
                                        <th className="px-8 py-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-50">
                                    {users.map(u => (
                                        <tr key={u.id}>
                                            <td className="px-8 py-5">
                                                <div className="font-bold text-gray-900">{u.full_name}</div>
                                                <div className="text-xs text-gray-500">{u.email}</div>
                                            </td>
                                            <td className="px-8 py-5">
                                                <span className="px-3 py-1 bg-gray-100 rounded-lg text-xs font-bold text-gray-600 uppercase">{u.role}</span>
                                            </td>
                                            <td className="px-8 py-5">
                                                {u.is_active ?
                                                    <span className="text-emerald-600 font-bold text-xs flex items-center gap-1"><CheckCircle size={14} /> Active</span> :
                                                    <span className="text-red-500 font-bold text-xs flex items-center gap-1"><XCircle size={14} /> Inactive</span>
                                                }
                                            </td>
                                            <td className="px-8 py-5 text-right space-x-2">
                                                {u.role !== 'super_admin' && (
                                                    <>
                                                        <button
                                                            onClick={() => handleAction(u.id, 'update', { is_active: !u.is_active, role: u.role })}
                                                            className={`px-3 py-1.5 rounded-lg text-[10px] font-black uppercase ${u.is_active ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-600'}`}
                                                        >
                                                            {u.is_active ? 'Deactivate' : 'Activate'}
                                                        </button>
                                                        <button
                                                            onClick={() => handleAction(u.id, 'reset_password')}
                                                            className="px-3 py-1.5 bg-yellow-50 text-yellow-600 hover:bg-yellow-100 rounded-lg text-[10px] font-black uppercase flex items-center gap-1"
                                                        >
                                                            <Key size={12} /> Reset
                                                        </button>
                                                        <button
                                                            onClick={() => handleAction(u.id, 'delete')}
                                                            className="px-3 py-1.5 bg-gray-100 text-gray-600 hover:bg-gray-200 rounded-lg text-[10px] font-black uppercase"
                                                        >
                                                            Delete
                                                        </button>
                                                    </>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
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
                    <div className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden max-w-2xl">
                        <div className="p-8 border-b border-gray-100">
                            <h2 className="text-xl font-bold text-gray-900 flex items-center gap-3">
                                <Key className="w-6 h-6 text-purple-600" />
                                Change My Password
                            </h2>
                            <p className="text-gray-500 mt-2">Update the password for your Super Admin account.</p>
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
        className={`px-6 py-3 rounded-2xl font-black text-[10px] uppercase tracking-widest flex items-center gap-2 transition-all ${activeTab === id
            ? 'bg-blue-600 text-white shadow-lg shadow-blue-100'
            : 'text-gray-400 hover:text-gray-600 hover:bg-gray-50'
            }`}
    >
        <Icon size={16} /> {label}
    </button>
);

const StatCard = ({ label, value, icon: Icon, color }) => (
    <div className={`bg-white p-6 rounded-3xl shadow-sm border border-gray-100`}>
        <div className={`w-12 h-12 rounded-2xl bg-${color}-50 text-${color}-600 flex items-center justify-center mb-4`}>
            <Icon size={24} />
        </div>
        <div className="text-3xl font-black text-gray-900 mb-1">{value}</div>
        <div className="text-xs font-bold text-gray-400 uppercase tracking-wider">{label}</div>
    </div>
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
                <label className="block text-sm font-bold text-gray-700 mb-1">Current Password</label>
                <input
                    type="password"
                    required
                    value={oldPassword}
                    onChange={e => setOldPassword(e.target.value)}
                    className="w-full bg-gray-50 border-none rounded-xl py-3 px-4 text-sm font-medium focus:ring-2 focus:ring-purple-500/20 outline-none"
                    placeholder="Enter current password"
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
                    placeholder="Enter new password"
                />
            </div>
            <button
                type="submit"
                disabled={loading}
                className="w-full bg-gray-900 hover:bg-gray-800 text-white py-3 rounded-xl text-sm font-bold transition-colors shadow-lg disabled:opacity-50 mt-2"
            >
                {loading ? 'Updating...' : 'Update Password'}
            </button>
        </form>
    );
};

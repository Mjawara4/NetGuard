import React, { useState } from 'react';
import api from '../api';
import { useNavigate, Link } from 'react-router-dom';
import { Mail, Lock, ArrowRight, Loader2, ShieldCheck } from 'lucide-react';

export default function Login() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    const handleLogin = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            const formData = new FormData();
            formData.append('username', email);
            formData.append('password', password);

            const response = await api.post('/auth/login', formData);
            localStorage.setItem('token', response.data.access_token);

            // Fetch user details
            const userRes = await api.get('/auth/me');
            localStorage.setItem('user', JSON.stringify(userRes.data));

            navigate('/');
        } catch (err) {
            setError('Invalid credentials. Please verify your identity.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#F8FAFC] flex flex-col items-center justify-center p-6 sm:p-10">
            <div className="w-full max-w-[400px]">
                {/* Logo & Header */}
                <div className="text-center mb-10">
                    <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 rounded-2xl shadow-xl shadow-blue-100 mb-6 group animate-in zoom-in duration-700">
                        <ShieldCheck className="text-white w-8 h-8 group-hover:scale-110 transition-transform" />
                    </div>
                    <h1 className="text-4xl font-black text-gray-900 tracking-tight leading-none mb-3">
                        NetGuard <span className="text-blue-600">AI</span>
                    </h1>
                    <p className="text-gray-500 font-medium">Autonomous Network Management</p>
                </div>

                {/* Card */}
                <div className="bg-white rounded-[32px] shadow-2xl shadow-blue-50 border border-gray-100 p-8 sm:p-10 animate-in fade-in slide-in-from-bottom-8 duration-700">
                    {error && (
                        <div className="mb-6 p-4 bg-red-50 border border-red-100 rounded-2xl text-red-600 text-xs font-bold uppercase tracking-wider flex items-center gap-3">
                            <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></div>
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleLogin} className="space-y-6">
                        <div className="space-y-1.5">
                            <label className="text-[10px] font-black text-gray-400 uppercase tracking-[0.2em] ml-1">Email Identity</label>
                            <div className="relative group">
                                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
                                <input
                                    type="email"
                                    required
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="administrator@netguard.ai"
                                    className="w-full bg-gray-50 border-none rounded-2xl py-4 pl-12 pr-4 text-sm font-bold text-gray-900 placeholder:text-gray-300 focus:ring-2 focus:ring-blue-500/20 transition-all outline-none"
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-[10px] font-black text-gray-400 uppercase tracking-[0.2em] ml-1">Password</label>
                            <div className="relative group">
                                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
                                <input
                                    type="password"
                                    required
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="••••••••••••"
                                    className="w-full bg-gray-50 border-none rounded-2xl py-4 pl-12 pr-4 text-base font-bold text-gray-900 placeholder:text-gray-300 focus:ring-2 focus:ring-blue-500/20 transition-all outline-none"
                                />
                            </div>
                        </div>

                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-black py-4 px-4 rounded-2xl shadow-xl shadow-blue-200 transition-all active:scale-[0.98] flex items-center justify-center gap-2 uppercase tracking-widest text-xs mt-4"
                        >
                            {loading ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                            ) : (
                                <>
                                    Access Console
                                    <ArrowRight className="w-5 h-5" />
                                </>
                            )}
                        </button>
                    </form>

                    <div className="mt-8 pt-8 border-t border-gray-50 text-center">
                        <p className="text-gray-400 text-sm font-medium">
                            New operator?{' '}
                            <Link to="/signup" className="text-blue-600 font-black hover:underline underline-offset-4">
                                Create Account
                            </Link>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}

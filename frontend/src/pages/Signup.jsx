import React, { useState } from 'react';
import api from '../api';
import { useNavigate, Link } from 'react-router-dom';
import { User, Mail, Lock, Building, Loader2 } from 'lucide-react';

export default function Signup() {
    const [formData, setFormData] = useState({
        full_name: '',
        email: '',
        password: '',
        organization_name: ''
    });
    const [errors, setErrors] = useState([]);
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    const handleChange = (e) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSignup = async (e) => {
        e.preventDefault();
        setErrors([]);
        setLoading(true);
        try {
            await api.post('/auth/signup', formData);

            const loginData = new FormData();
            loginData.append('username', formData.email);
            loginData.append('password', formData.password);

            const response = await api.post('/auth/login', loginData);
            localStorage.setItem('token', response.data.access_token);
            navigate('/');
        } catch (err) {
            console.error(err);
            const data = err.response?.data;
            if (data?.errors) {
                setErrors(data.errors.map(e => e.msg));
            } else if (data?.detail) {
                setErrors([data.detail]);
            } else {
                setErrors(['Registration failed. Please try again.']);
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-ink-50 dark:bg-ink-900 flex flex-col items-center justify-center p-6 sm:p-10">
            <div className="w-full max-w-[440px]">
                <div className="text-center mb-10">
                    <div className="inline-flex items-center justify-center w-16 h-16 bg-signal-600 rounded-md shadow-xl mb-6 group">
                        <Building className="text-white w-8 h-8 group-hover:scale-110 transition-transform" />
                    </div>
                    <h1 className="text-4xl font-display font-semibold text-ink-900 dark:text-ink-50 tracking-tight leading-none mb-3">
                        Join <span className="text-signal-600 dark:text-signal-300">NetGuard</span>
                    </h1>
                    <p className="text-ink-500 dark:text-ink-400 font-medium">Create your autonomous network hub.</p>
                </div>

                <div className="bg-white dark:bg-ink-800 rounded-md border border-ink-100 dark:border-ink-700 p-8 sm:p-10">
                    {errors.length > 0 && (
                        <div className="mb-6 p-4 bg-down/10 dark:bg-down/20 border border-down/20 dark:border-down/30 rounded-md text-ink-900 dark:text-ink-50 text-xs font-bold flex items-start gap-3">
                            <div className="w-1.5 h-1.5 rounded-full bg-down animate-pulse mt-1.5 shrink-0"></div>
                            <div className="flex-1">
                                {errors.length === 1 ? (
                                    errors[0]
                                ) : (
                                    <ul className="list-disc pl-2 space-y-1">
                                        {errors.map((err, i) => (
                                            <li key={i}>{err}</li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        </div>
                    )}

                    <form onSubmit={handleSignup} className="space-y-5">
                        <div className="space-y-1.5">
                            <label htmlFor="full_name" className="text-xs font-bold text-ink-500 dark:text-ink-400 ml-1">Full name</label>
                            <div className="relative group">
                                <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-ink-400 group-focus-within:text-signal-500 transition-colors" />
                                <input
                                    id="full_name"
                                    name="full_name"
                                    type="text"
                                    required
                                    value={formData.full_name}
                                    onChange={handleChange}
                                    placeholder="Muhammed Jalloh"
                                    className="w-full bg-ink-50 dark:bg-ink-900 border-none rounded-md py-4 pl-12 pr-4 text-sm font-bold text-ink-900 dark:text-white placeholder:text-ink-300 dark:placeholder:text-ink-600 focus:ring-2 focus:ring-signal-500/20 transition-all outline-none"
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label htmlFor="organization_name" className="text-xs font-bold text-ink-500 dark:text-ink-400 ml-1">Organization name</label>
                            <div className="relative group">
                                <Building className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-ink-400 group-focus-within:text-signal-500 transition-colors" />
                                <input
                                    id="organization_name"
                                    name="organization_name"
                                    type="text"
                                    required
                                    value={formData.organization_name}
                                    onChange={handleChange}
                                    placeholder="Hotfly Ventures"
                                    className="w-full bg-ink-50 dark:bg-ink-900 border-none rounded-md py-4 pl-12 pr-4 text-sm font-bold text-ink-900 dark:text-white placeholder:text-ink-300 dark:placeholder:text-ink-600 focus:ring-2 focus:ring-signal-500/20 transition-all outline-none"
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label htmlFor="email" className="text-xs font-bold text-ink-500 dark:text-ink-400 ml-1">Work email</label>
                            <div className="relative group">
                                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-ink-400 group-focus-within:text-signal-500 transition-colors" />
                                <input
                                    id="email"
                                    name="email"
                                    type="email"
                                    required
                                    value={formData.email}
                                    onChange={handleChange}
                                    placeholder="muhammed@hotfly.net"
                                    className="w-full bg-ink-50 dark:bg-ink-900 border-none rounded-md py-4 pl-12 pr-4 text-sm font-bold text-ink-900 dark:text-white placeholder:text-ink-300 dark:placeholder:text-ink-600 focus:ring-2 focus:ring-signal-500/20 transition-all outline-none"
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label htmlFor="password" className="text-xs font-bold text-ink-500 dark:text-ink-400 ml-1">Password</label>
                            <div className="relative group">
                                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-ink-400 group-focus-within:text-signal-500 transition-colors" />
                                <input
                                    id="password"
                                    name="password"
                                    type="password"
                                    required
                                    value={formData.password}
                                    onChange={handleChange}
                                    placeholder="••••••••••••"
                                    className="w-full bg-ink-50 dark:bg-ink-900 border-none rounded-md py-4 pl-12 pr-4 text-base font-bold text-ink-900 dark:text-white placeholder:text-ink-300 dark:placeholder:text-ink-600 focus:ring-2 focus:ring-signal-500/20 transition-all outline-none"
                                />
                            </div>
                        </div>

                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full bg-signal-600 hover:bg-signal-700 disabled:bg-signal-400 text-white font-semibold py-4 px-4 rounded-md shadow-xl transition-all active:scale-[0.98] flex items-center justify-center gap-2 text-xs mt-4"
                        >
                            {loading ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                            ) : (
                                'Create account'
                            )}
                        </button>
                    </form>

                    <div className="mt-8 pt-8 border-t border-ink-50 dark:border-ink-700 text-center">
                        <p className="text-ink-500 dark:text-ink-400 text-sm font-medium">
                            Already have an account?{' '}
                            <Link to="/login" className="text-signal-600 dark:text-signal-300 font-semibold hover:underline underline-offset-4">
                                Sign in
                            </Link>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}

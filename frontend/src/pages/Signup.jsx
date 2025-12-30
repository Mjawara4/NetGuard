import React, { useState } from 'react';
import api from '../api';
import { useNavigate, Link } from 'react-router-dom';
import { User, Mail, Lock, Building, ArrowRight, Loader2 } from 'lucide-react';

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

            // Auto-login after signup
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
                // Handle Pydantic validation errors
                setErrors(data.errors.map(e => e.msg));
            } else if (data?.detail) {
                // Handle standard HTTP errors
                setErrors([data.detail]);
            } else {
                setErrors(['Registration failed. Please try again.']);
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#F8FAFC] flex flex-col items-center justify-center p-6 sm:p-10">
            <div className="w-full max-w-[440px]">
                {/* Logo & Header */}
                <div className="text-center mb-10">
                    <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 rounded-2xl shadow-xl shadow-blue-100 mb-6 group animate-in zoom-in duration-700">
                        <Building className="text-white w-8 h-8 group-hover:scale-110 transition-transform" />
                    </div>
                    <h1 className="text-4xl font-black text-gray-900 tracking-tight leading-none mb-3">
                        Join <span className="text-blue-600">NetGuard</span>
                    </h1>
                    <p className="text-gray-500 font-medium">Create your autonomous network hub.</p>
                </div>

                {/* Card */}
                <div className="bg-white rounded-[32px] shadow-2xl shadow-blue-50 border border-gray-100 p-8 sm:p-10 animate-in fade-in slide-in-from-bottom-8 duration-700">
                    {errors.length > 0 && (
                        <div className="mb-6 p-4 bg-red-50 border border-red-100 rounded-2xl text-red-600 text-xs font-bold uppercase tracking-wider flex items-start gap-3">
                            <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse mt-1.5 shrink-0"></div>
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
                            <label className="text-[10px] font-black text-gray-400 uppercase tracking-[0.2em] ml-1">Full Identity</label>
                            <div className="relative group">
                                <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
                                <input
                                    name="full_name"
                                    type="text"
                                    required
                                    value={formData.full_name}
                                    onChange={handleChange}
                                    placeholder="Muhammed Jalloh"
                                    className="w-full bg-gray-50 border-none rounded-2xl py-4 pl-12 pr-4 text-sm font-bold text-gray-900 placeholder:text-gray-300 focus:ring-2 focus:ring-blue-500/20 transition-all outline-none"
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-[10px] font-black text-gray-400 uppercase tracking-[0.2em] ml-1">Organization Name</label>
                            <div className="relative group">
                                <Building className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
                                <input
                                    name="organization_name"
                                    type="text"
                                    required
                                    value={formData.organization_name}
                                    onChange={handleChange}
                                    placeholder="Hotfly Ventures"
                                    className="w-full bg-gray-50 border-none rounded-2xl py-4 pl-12 pr-4 text-sm font-bold text-gray-900 placeholder:text-gray-300 focus:ring-2 focus:ring-blue-500/20 transition-all outline-none"
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-[10px] font-black text-gray-400 uppercase tracking-[0.2em] ml-1">Work Email</label>
                            <div className="relative group">
                                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
                                <input
                                    name="email"
                                    type="email"
                                    required
                                    value={formData.email}
                                    onChange={handleChange}
                                    placeholder="muhammed@hotfly.net"
                                    className="w-full bg-gray-50 border-none rounded-2xl py-4 pl-12 pr-4 text-sm font-bold text-gray-900 placeholder:text-gray-300 focus:ring-2 focus:ring-blue-500/20 transition-all outline-none"
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-[10px] font-black text-gray-400 uppercase tracking-[0.2em] ml-1">Master Password</label>
                            <div className="relative group">
                                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
                                <input
                                    name="password"
                                    type="password"
                                    required
                                    value={formData.password}
                                    onChange={handleChange}
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
                                    Initialize Console
                                    <ArrowRight className="w-5 h-5" />
                                </>
                            )}
                        </button>
                    </form>

                    <div className="mt-8 pt-8 border-t border-gray-50 text-center">
                        <p className="text-gray-400 text-sm font-medium">
                            Already have an entity?{' '}
                            <Link to="/login" className="text-blue-600 font-black hover:underline underline-offset-4">
                                Sign In
                            </Link>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}

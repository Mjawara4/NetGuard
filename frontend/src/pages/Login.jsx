import React, { useState } from 'react';
import api from '../api';
import { useNavigate, Link } from 'react-router-dom';
import { Mail, Lock, Loader2, ShieldCheck } from 'lucide-react';
import { Input } from '../components/ui';

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
        <div className="min-h-screen bg-ink-50 dark:bg-ink-900 flex flex-col items-center justify-center p-6 sm:p-10">
            <div className="w-full max-w-[400px]">
                <div className="text-center mb-10">
                    <div className="inline-flex items-center justify-center w-16 h-16 bg-signal-600 rounded-md shadow-xl mb-6 group">
                        <ShieldCheck className="text-white w-8 h-8 group-hover:scale-110 transition-transform" />
                    </div>
                    <h1 className="text-4xl font-display font-semibold text-ink-900 dark:text-ink-50 tracking-tight leading-none mb-3">
                        NetGuard <span className="text-signal-600 dark:text-signal-300">AI</span>
                    </h1>
                    <p className="text-ink-500 dark:text-ink-400 font-medium">Autonomous Network Management</p>
                </div>

                <div className="bg-white dark:bg-ink-800 rounded-md border border-ink-100 dark:border-ink-700 p-8 sm:p-10">
                    {error && (
                        <div className="mb-6 p-4 bg-down/10 dark:bg-down/20 border border-down/20 dark:border-down/30 rounded-md text-ink-900 dark:text-ink-50 text-xs font-medium flex items-center gap-3">
                            <div className="w-1.5 h-1.5 rounded-full bg-down animate-pulse"></div>
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleLogin} className="space-y-6">
                        <Input
                            id="email"
                            label="Email"
                            icon={Mail}
                            type="email"
                            required
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="administrator@netguard.ai"
                        />

                        <Input
                            id="password"
                            label="Password"
                            icon={Lock}
                            type="password"
                            required
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="••••••••••••"
                            textSize="text-base"
                        />

                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full bg-signal-600 hover:bg-signal-700 disabled:bg-signal-400 text-white font-semibold py-4 px-4 rounded-md shadow-xl transition-all active:scale-[0.98] flex items-center justify-center text-xs mt-4"
                        >
                            {loading ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                            ) : (
                                'Sign in'
                            )}
                        </button>
                    </form>

                    <div className="mt-8 pt-8 border-t border-ink-200 dark:border-ink-700 text-center">
                        <p className="text-ink-500 dark:text-ink-400 text-sm font-medium">
                            New here?{' '}
                            <Link to="/signup" className="text-signal-600 dark:text-signal-300 font-semibold hover:underline underline-offset-4">
                                Create account
                            </Link>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}

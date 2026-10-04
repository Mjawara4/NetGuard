import React, { useEffect, useMemo, useState } from 'react';
import { Wifi } from 'lucide-react';
import api from '../api';

const isCaptivePopup = () => {
    const agent = navigator.userAgent || '';
    return /CaptiveNetworkSupport|; wv\)|WebView/i.test(agent);
};

export default function Buy() {
    const params = useMemo(() => new URLSearchParams(window.location.search), []);
    const router = params.get('router');
    const mac = params.get('mac');
    const [state, setState] = useState({ loading: true, enabled: false, plans: [] });
    const [paying, setPaying] = useState(null);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!router) {
            setState({ loading: false, enabled: false, plans: [] });
            setError('This payment link is missing its router ID.');
            return;
        }
        api.get('/buy/plans', { params: { router } })
            .then(({ data }) => setState({ loading: false, ...data }))
            .catch(() => {
                setState({ loading: false, enabled: false, plans: [] });
                setError('Unable to load WiFi plans.');
            });
    }, [router]);

    const purchase = async (plan) => {
        setPaying(plan);
        setError('');
        try {
            const { data } = await api.post('/buy/pay', { router, mac, plan });
            window.location.assign(data.checkout_url);
        } catch (requestError) {
            setError(requestError.response?.data?.detail || 'Unable to start checkout.');
            setPaying(null);
        }
    };

    return (
        <main className="min-h-screen bg-ink-50 dark:bg-ink-950 p-4 flex items-center justify-center">
            <section className="w-full max-w-lg bg-white dark:bg-ink-900 rounded-xl shadow-xl p-6 space-y-6">
                <header className="text-center">
                    <Wifi className="mx-auto text-signal-600" size={36} />
                    <h1 className="mt-3 text-2xl font-bold text-ink-900 dark:text-ink-50">Buy WiFi</h1>
                    <p className="text-sm text-ink-500 dark:text-ink-400">Choose a plan and pay securely with Modem Pay.</p>
                </header>

                {isCaptivePopup() && (
                    <div className="rounded-md bg-warn/10 border border-warn/30 p-4 text-sm text-ink-900 dark:text-ink-100">
                        <strong>Open in your browser to pay.</strong>
                        <p className="mt-1 break-all">{window.location.href}</p>
                    </div>
                )}
                {state.loading && <p className="text-center">Loading plans...</p>}
                {!state.loading && !state.enabled && !error && (
                    <p className="text-center">Online payments are not available for this hotspot.</p>
                )}
                {error && <p role="alert" className="text-center text-down">{error}</p>}
                <div className="space-y-3">
                    {state.plans.map((plan) => (
                        <div key={plan.profile} className="flex items-center justify-between border border-ink-200 dark:border-ink-700 rounded-md p-4">
                            <div>
                                <h2 className="font-bold text-ink-900 dark:text-ink-50">{plan.profile}</h2>
                                <p className="text-sm text-ink-500 dark:text-ink-400">{plan.currency} {plan.price}</p>
                            </div>
                            <button
                                type="button"
                                onClick={() => purchase(plan.profile)}
                                disabled={paying !== null}
                                className="bg-signal-600 text-white px-5 py-2 rounded-md font-bold disabled:opacity-50"
                            >
                                {paying === plan.profile ? 'Opening...' : 'Buy'}
                            </button>
                        </div>
                    ))}
                </div>
            </section>
        </main>
    );
}

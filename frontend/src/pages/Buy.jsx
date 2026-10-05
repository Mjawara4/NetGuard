import React, { useEffect, useMemo, useState } from 'react';
import { Wifi } from 'lucide-react';
import api from '../api';

const isCaptivePopup = () => {
    const agent = navigator.userAgent || '';
    return /CaptiveNetworkSupport|; wv\)|WebView/i.test(agent);
};

const formatPrice = (price, currency) => {
    const amount = Number(price).toLocaleString(undefined, { maximumFractionDigits: 2 });
    return currency === 'GMD' ? `D${amount}` : `${currency} ${amount}`;
};

export default function Buy() {
    const params = useMemo(() => new URLSearchParams(window.location.search), []);
    const router = params.get('router');
    const mac = params.get('mac');
    const returnedPayment = params.get('payment') === 'success';
    const intent = params.get('intent');
    const [state, setState] = useState({ loading: true, enabled: false, plans: [] });
    const [paying, setPaying] = useState(null);
    const [error, setError] = useState('');
    const [paymentResult, setPaymentResult] = useState(null);

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

    useEffect(() => {
        if (!returnedPayment || !router || !intent) return undefined;
        let attempts = 0;
        const check = async () => {
            attempts += 1;
            try {
                const { data } = await api.get('/buy/status', { params: { router, intent } });
                setPaymentResult(data);
                if (data.status === 'fulfilled' || attempts >= 30) clearInterval(timer);
            } catch {
                if (attempts >= 30) clearInterval(timer);
            }
        };
        const timer = setInterval(check, 2000);
        check();
        return () => clearInterval(timer);
    }, [returnedPayment, router, intent]);

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
                {returnedPayment && paymentResult?.status !== 'fulfilled' && (
                    <p className="text-center text-ink-900 dark:text-ink-50">Payment received. Creating your WiFi voucher…</p>
                )}
                {paymentResult?.status === 'fulfilled' && (
                    <div className="rounded-md border border-up/30 bg-up/10 p-4 text-center">
                        <p className="font-bold text-ink-900 dark:text-ink-50">Your WiFi voucher code</p>
                        <p className="mt-2 text-2xl font-mono font-bold text-up">{paymentResult.voucher_username}</p>
                        <p className="mt-2 text-sm text-ink-500 dark:text-ink-400">Return to the WiFi login page and enter this code.</p>
                    </div>
                )}
                <div className="space-y-3">
                    {state.plans.map((plan) => (
                        <div key={plan.profile} className="flex items-center justify-between border border-ink-200 dark:border-ink-700 rounded-md p-4">
                            <div>
                                <h2 className="font-bold text-ink-900 dark:text-ink-50">{plan.profile}</h2>
                                <p className="text-sm text-ink-500 dark:text-ink-400">{formatPrice(plan.price, plan.currency)}</p>
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

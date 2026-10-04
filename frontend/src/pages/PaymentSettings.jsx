import React, { useEffect, useState } from 'react';
import { CreditCard } from 'lucide-react';
import api from '../api';
import { Card } from '../components/ui';

export default function PaymentSettings() {
    const [configured, setConfigured] = useState(false);
    const [enabled, setEnabled] = useState(false);
    const [secretKey, setSecretKey] = useState('');
    const [webhookSecret, setWebhookSecret] = useState('');
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        api.get('/payments/settings').then(({ data }) => {
            setConfigured(data.configured);
            setEnabled(data.payments_enabled);
        }).catch((error) => console.error('Failed to fetch payment settings:', error));
    }, []);

    const save = async (event) => {
        event.preventDefault();
        setSaving(true);
        const payload = { payments_enabled: enabled };
        if (secretKey) payload.modempay_secret_key = secretKey;
        if (webhookSecret) payload.modempay_webhook_secret = webhookSecret;
        try {
            const { data } = await api.put('/payments/settings', payload);
            setConfigured(data.configured);
            setEnabled(data.payments_enabled);
            setSecretKey('');
            setWebhookSecret('');
        } catch (error) {
            alert(error.response?.data?.detail || 'Failed to save payment settings');
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="lg:col-span-3">
            <Card padding="p-0">
                <div className="p-6 border-b border-ink-200 dark:border-ink-700">
                    <h2 className="text-lg font-bold text-ink-900 dark:text-ink-50 flex items-center gap-2">
                        <CreditCard className="w-5 h-5 text-signal-600 dark:text-signal-300" />
                        Modem Pay
                    </h2>
                    <p className="text-sm text-ink-500 dark:text-ink-400 mt-1">
                        Accept captive-portal payments directly into your organization&apos;s account.
                    </p>
                </div>
                <form onSubmit={save} className="p-6 max-w-2xl space-y-4">
                    {configured && <p role="status" className="text-sm font-bold text-up">Credentials configured</p>}
                    <label className="block text-sm font-bold text-ink-900 dark:text-ink-100">
                        Secret key
                        <input
                            aria-label="Modem Pay secret key"
                            type="password"
                            value={secretKey}
                            onChange={(event) => setSecretKey(event.target.value)}
                            placeholder={configured ? 'Leave blank to keep existing key' : 'sk_test_...'}
                            autoComplete="new-password"
                            className="mt-1 w-full bg-ink-50 dark:bg-ink-900 border-none rounded-md py-3 px-4 text-sm font-medium text-ink-900 dark:text-ink-50"
                        />
                    </label>
                    <label className="block text-sm font-bold text-ink-900 dark:text-ink-100">
                        Webhook secret
                        <input
                            aria-label="Modem Pay webhook secret"
                            type="password"
                            value={webhookSecret}
                            onChange={(event) => setWebhookSecret(event.target.value)}
                            placeholder={configured ? 'Leave blank to keep existing secret' : 'whsec_...'}
                            autoComplete="new-password"
                            className="mt-1 w-full bg-ink-50 dark:bg-ink-900 border-none rounded-md py-3 px-4 text-sm font-medium text-ink-900 dark:text-ink-50"
                        />
                    </label>
                    <label className="flex items-center gap-3 text-sm font-bold text-ink-900 dark:text-ink-100">
                        <input
                            type="checkbox"
                            checked={enabled}
                            onChange={(event) => setEnabled(event.target.checked)}
                        />
                        Enable captive-portal payments
                    </label>
                    <button type="submit" disabled={saving} className="bg-signal-600 hover:bg-signal-700 text-ink-50 px-6 py-3 rounded-md text-sm font-bold disabled:opacity-50">
                        {saving ? 'Saving...' : 'Save payment settings'}
                    </button>
                </form>
            </Card>
        </div>
    );
}

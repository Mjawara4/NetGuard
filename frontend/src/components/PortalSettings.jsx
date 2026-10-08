import React, { useCallback, useEffect, useState } from 'react';
import { Check, Copy } from 'lucide-react';
import api from '../api';

// The login page belongs to whoever runs the hotspot. This card never changes
// it on its own: every button is an explicit request, and replacing the page
// with NetGuard's asks first.

const SERVING = {
    custom: 'The router is serving your own login page',
    netguard: "The router is serving NetGuard's login page",
    missing: 'The router has no login page in its hotspot folder',
    unreadable: 'The router has a login page NetGuard cannot read (too large)',
};

const modeButton = (active) =>
    `px-3 py-2 rounded-md text-xs font-bold border ${active
        ? 'bg-signal-600 text-white border-signal-600'
        : 'border-ink-300 dark:border-ink-600 text-ink-700 dark:text-ink-200'}`;

export default function PortalSettings({ device }) {
    // No answer from the server is NOT "NetGuard": default to the owner's page.
    const [mode, setMode] = useState('custom');
    const [buttonHtml, setButtonHtml] = useState('');
    const [status, setStatus] = useState(null);
    const [busy, setBusy] = useState(false);
    const [notice, setNotice] = useState('');
    const [copied, setCopied] = useState(false);

    const loadStatus = useCallback(() => {
        api.get(`/hotspot/${device.id}/portal/status`)
            .then(({ data }) => setStatus(data))
            .catch(() => setStatus(null));
    }, [device.id]);

    useEffect(() => {
        setMode('custom');
        setButtonHtml('');
        setStatus(null);
        setNotice('');
        setCopied(false);
        api.get(`/hotspot/${device.id}/portal-config`)
            .then(({ data }) => {
                setMode(data.mode === 'netguard' ? 'netguard' : 'custom');
                setButtonHtml(data.button_html || '');
            })
            .catch(() => {});
        loadStatus();
    }, [device.id, loadStatus]);

    const snippet = buttonHtml
        || `<a href="https://app.netguard.fun/buy?router=${device.id}&mac=$(mac)&ip=$(ip)">Buy WiFi</a>`;

    const copySnippet = async () => {
        try {
            await navigator.clipboard.writeText(snippet);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 2000);
        } catch {
            setCopied(false);
            alert('Copy was blocked by the browser. Select and copy the code manually.');
        }
    };

    const request = async (path, body, done) => {
        setBusy(true);
        setNotice('');
        try {
            await api.post(`/hotspot/${device.id}/${path}`, body);
            done();
        } catch (e) {
            setNotice(e.response?.data?.detail || 'The portal was not changed.');
        } finally {
            setBusy(false);
            loadStatus();
        }
    };

    const chooseNetguard = () => {
        if (mode === 'netguard') return;
        const where = status?.directory ? `${status.directory}/login.html` : 'the login page';
        const ok = window.confirm(
            `This will replace ${where} on the router with NetGuard's Buy WiFi page.\n\n`
            + 'A copy of your current page is kept on the router first, and you can restore it from here. Continue?',
        );
        if (!ok) return;
        request('portal-mode', { mode: 'netguard' }, () => {
            setMode('netguard');
            setNotice("NetGuard's login page is installed. Your previous page is saved on the router.");
        });
    };

    const chooseCustom = () => {
        if (mode === 'custom') return;
        request('portal-mode', { mode: 'custom' }, () => {
            setMode('custom');
            setNotice('NetGuard will leave this router\'s login page alone. Use "Restore my page" to bring yours back.');
        });
    };

    const addButton = () => request('portal/install-custom', undefined, () => {
        setMode('custom');
        setNotice('Buy WiFi button added to your login page. The original is saved on the router.');
    });

    const restore = () => request('portal/restore', undefined, () => {
        setMode('custom');
        setNotice('Your own login page is back.');
    });

    return (
        <div className="bg-white dark:bg-ink-800 p-6 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700">
            <div className="mb-4">
                <h4 className="font-bold text-ink-900 dark:text-ink-50">Captive Portal</h4>
                <p className="mt-1 text-xs text-ink-500 dark:text-ink-400">
                    NetGuard leaves your login page alone unless you choose its portal here.
                </p>
            </div>

            <div className="mb-3 grid grid-cols-2 gap-2">
                <button type="button" disabled={busy} aria-pressed={mode === 'custom'} onClick={chooseCustom} className={modeButton(mode === 'custom')}>My own portal</button>
                <button type="button" disabled={busy} aria-pressed={mode === 'netguard'} onClick={chooseNetguard} className={modeButton(mode === 'netguard')}>NetGuard portal</button>
            </div>

            {status && (
                <p className="mb-4 rounded-md bg-ink-50 dark:bg-ink-900 p-3 text-xs text-ink-700 dark:text-ink-200">
                    {SERVING[status.login_page] || 'Router state unknown'}
                    {status.directory && <> — <code>{`${status.directory}/login.html`}</code></>}
                    {status.has_backup && <span className="block mt-1 text-ink-500 dark:text-ink-400">A copy of your own page is saved on the router.</span>}
                </p>
            )}

            <div className="flex flex-wrap gap-2">
                <button type="button" disabled={busy} onClick={addButton} className="px-4 py-2 rounded-md bg-up text-white text-xs font-bold disabled:opacity-50">Add Buy button to my page</button>
                <button type="button" disabled={busy || !status?.has_backup} onClick={restore} className="px-4 py-2 rounded-md border border-ink-300 dark:border-ink-600 text-xs font-bold text-ink-700 dark:text-ink-200 disabled:opacity-50">Restore my page</button>
            </div>
            {notice && <p role="status" className="mt-3 text-xs font-medium text-ink-700 dark:text-ink-200">{notice}</p>}

            <details className="mt-5">
                <summary className="cursor-pointer text-xs font-bold text-ink-700 dark:text-ink-200">Add the button by hand instead</summary>
                <div className="mt-3 flex justify-end">
                    <button type="button" onClick={copySnippet} className="inline-flex items-center gap-2 px-3 py-2 rounded-md bg-signal-600 text-white text-xs font-bold">
                        {copied ? <Check size={15} /> : <Copy size={15} />}
                        {copied ? 'Copied' : 'Copy HTML'}
                    </button>
                </div>
                <textarea readOnly value={snippet} aria-label="Custom portal Buy WiFi HTML" className="mt-2 w-full min-h-32 p-3 rounded-md bg-ink-900 text-ink-100 font-mono text-xs border border-ink-700 resize-y" />
                <div className="mt-3 rounded-md bg-ink-50 dark:bg-ink-900 p-4 text-xs text-ink-600 dark:text-ink-300 space-y-2">
                    <p>WinBox → Files → open the folder your hotspot uses → download <code>login.html</code>.</p>
                    <p>Paste the HTML inside the page&rsquo;s <code>&lt;body&gt;</code>, save it, then upload it back into the same folder.</p>
                    <p>Keep <code>$(mac)</code>, <code>$(ip)</code> and <code>$(link-login-only)</code> unchanged; MikroTik fills them for each customer.</p>
                </div>
            </details>
        </div>
    );
}

import React, { useState, useEffect, useRef } from 'react';
import { X, Check, Wifi, Download, Copy } from 'lucide-react';
import api from '../api';
import { Button } from './ui';

/**
 * Guided, step-by-step onboarding for a new router. It sequences the three
 * real actions (create device, provision the tunnel, generate the script) with
 * the physical steps in between, so a non-technical installer is never guessing
 * which button to press next. Each step reuses the same endpoints the rest of
 * the Devices page uses -- it orchestrates, it does not duplicate.
 */

const STEPS = ['Name it', 'Prepare', 'Turn on VPN', 'Get the file', 'Apply it', 'Check'];

// A plain MikroTik router, five ports, WAN called out. Grounded in the actual
// hardware so the one thing people get wrong -- which port the internet goes in
// -- is unmistakable. Strokes use currentColor; the WAN port uses the accent.
function RouterDiagram() {
    return (
        <svg viewBox="0 -8 320 108" className="w-full max-w-sm mx-auto text-ink-400 dark:text-ink-500" role="img" aria-label="Router with the internet cable in port 1 and a laptop in port 2">
            <rect x="8" y="20" width="304" height="56" rx="8" fill="none" stroke="currentColor" strokeWidth="2" />
            {[0, 1, 2, 3, 4].map((i) => (
                <rect key={i} x={28 + i * 40} y="46" width="26" height="20" rx="3"
                    fill={i === 0 ? '#7C3E9C' : 'none'}
                    stroke={i === 0 ? '#7C3E9C' : 'currentColor'} strokeWidth="2" />
            ))}
            <text x="41" y="86" textAnchor="middle" className="fill-signal-600 dark:fill-signal-300" fontSize="9" fontWeight="700">WAN</text>
            <text x="81" y="86" textAnchor="middle" fill="currentColor" fontSize="9">laptop</text>
            <text x="160" y="36" textAnchor="middle" fill="currentColor" fontSize="10" fontWeight="600">MikroTik router</text>
            <line x1="41" y1="20" x2="41" y2="8" stroke="#7C3E9C" strokeWidth="2" />
            <text x="41" y="6" textAnchor="middle" className="fill-signal-600 dark:fill-signal-300" fontSize="8">internet</text>
        </svg>
    );
}

function WinboxDiagram() {
    return (
        <svg viewBox="0 0 320 110" className="w-full max-w-sm mx-auto text-ink-400 dark:text-ink-500" role="img" aria-label="Drag the file into WinBox Files, then run import in a terminal">
            <rect x="8" y="10" width="130" height="90" rx="6" fill="none" stroke="currentColor" strokeWidth="2" />
            <text x="73" y="28" textAnchor="middle" fill="currentColor" fontSize="10" fontWeight="600">Files</text>
            <rect x="24" y="40" width="98" height="16" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" />
            <text x="73" y="52" textAnchor="middle" fill="currentColor" fontSize="8">drop .rsc here</text>
            <path d="M150 55 h20 m-6 -5 l6 5 l-6 5" fill="none" stroke="#7C3E9C" strokeWidth="2" />
            <rect x="182" y="10" width="130" height="90" rx="6" fill="#1A1F1E" stroke="currentColor" strokeWidth="2" />
            <text x="196" y="40" fill="#F6F8F7" fontSize="8" fontFamily="monospace">/import</text>
            <text x="196" y="54" fill="#BB86D4" fontSize="8" fontFamily="monospace">file-name=</text>
            <text x="196" y="68" fill="#BB86D4" fontSize="8" fontFamily="monospace">netguard-...</text>
        </svg>
    );
}

export default function OnboardWizard({ onClose, onComplete }) {
    const [step, setStep] = useState(0);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    const [name, setName] = useState('');
    const [device, setDevice] = useState(null);
    const [wgReady, setWgReady] = useState(false);
    const [slug, setSlug] = useState('');
    const [timezone] = useState('Africa/Banjul');
    // 'connect' is for a router already running a hotspot: nothing of the owner's is changed.
    const [mode, setMode] = useState('full');
    const [result, setResult] = useState(null); // { script, api_password, recovery_password, site_slug }
    const [copied, setCopied] = useState(false);
    const [reach, setReach] = useState('waiting'); // waiting | connected
    const pollRef = useRef(null);

    const slugify = (s) => (s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 32).replace(/-+$/g, '');

    const go = (n) => { setError(''); setStep(n); };

    const createDevice = async () => {
        if (!name.trim() || busy) return;
        setBusy(true); setError('');
        try {
            let siteId;
            const sites = await api.get('/inventory/sites');
            if (!sites.data.length) { setError('No site exists yet. Create a site first, then come back.'); setBusy(false); return; }
            siteId = sites.data[0].id;
            const res = await api.post('/inventory/devices', { name: name.trim(), ip_address: '0.0.0.0', device_type: 'router', site_id: siteId });
            setDevice(res.data);
            setSlug(slugify(name));
            go(1);
        } catch (e) {
            setError(e.response?.data?.detail ? JSON.stringify(e.response.data.detail) : (e.message || 'Could not add the router.'));
        } finally { setBusy(false); }
    };

    const setupTunnel = async () => {
        if (!device || busy) return;
        setBusy(true); setError('');
        try {
            await api.post(`/inventory/devices/${device.id}/provision-wireguard`);
            setWgReady(true);
            go(3);
        } catch (e) {
            setError(e.response?.data?.detail || e.message || 'Could not set up the tunnel.');
        } finally { setBusy(false); }
    };

    const getScript = async () => {
        if (!device || busy || !slug) return;
        setBusy(true); setError('');
        try {
            const res = await api.post(`/inventory/devices/${device.id}/provision-script`, null,
                { params: { site_slug: slug, timezone, rotate: false, ...(mode === 'connect' ? { mode: 'connect' } : {}) } });
            setResult(res.data);
        } catch (e) {
            const d = e.response?.data?.detail;
            setError(typeof d === 'string' ? d : (d ? JSON.stringify(d) : e.message));
        } finally { setBusy(false); }
    };

    const download = () => {
        const blob = new Blob([result.script], { type: 'application/octet-stream' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = `netguard-${result.site_slug}.rsc`;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const copy = async () => {
        try { await navigator.clipboard.writeText(result.script); setCopied(true); setTimeout(() => setCopied(false), 2000); }
        catch { setError('Copy was blocked. Use Download instead.'); }
    };

    // Step 6 polls the device's API reachability so "connected" is real, not assumed.
    useEffect(() => {
        if (step !== 5 || !device) return;
        const check = async () => {
            try {
                const res = await api.get(`/monitoring/metrics/latest?device_id=${device.id}&limit=50`);
                const m = (res.data || []).find((x) => x.metric_type === 'api_reachable');
                if (m && m.value === 1) { setReach('connected'); if (pollRef.current) clearInterval(pollRef.current); }
            } catch { /* keep waiting */ }
        };
        check();
        pollRef.current = setInterval(check, 8000);
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, [step, device]);

    const finish = () => { onComplete && onComplete(); onClose(); };

    return (
        <div className="fixed inset-0 z-50 bg-ink-950/60 flex items-start sm:items-center justify-center p-0 sm:p-6 overflow-y-auto" role="dialog" aria-modal="true" aria-label="Set up a new router">
            <div className="bg-white dark:bg-ink-900 w-full max-w-2xl sm:rounded-lg shadow-2xl min-h-full sm:min-h-0">
                {/* Progress rail. Numbered because this genuinely is a sequence. */}
                <div className="flex items-center justify-between px-5 sm:px-8 pt-6 pb-4 border-b border-ink-100 dark:border-ink-800">
                    <div className="flex items-center gap-1.5 overflow-x-auto">
                        {STEPS.map((label, i) => (
                            <div key={label} className="flex items-center gap-1.5 shrink-0">
                                <div className={`flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${i < step ? 'bg-up text-white' : i === step ? 'bg-signal-600 text-white' : 'bg-ink-100 dark:bg-ink-800 text-ink-400'}`}>
                                    {i < step ? <Check size={14} /> : i + 1}
                                </div>
                                <span className={`text-xs hidden sm:inline ${i === step ? 'font-bold text-ink-900 dark:text-ink-50' : 'text-ink-400'}`}>{label}</span>
                                {i < STEPS.length - 1 && <span className="w-3 sm:w-5 h-px bg-ink-200 dark:bg-ink-700" />}
                            </div>
                        ))}
                    </div>
                    <button onClick={onClose} className="text-ink-400 hover:text-ink-700 dark:hover:text-ink-200 ml-2 shrink-0" aria-label="Close"><X size={20} /></button>
                </div>

                <div className="px-5 sm:px-8 py-6 space-y-5">
                    {error && <div className="p-3 rounded-md bg-down/10 text-sm text-down dark:text-ink-100" role="alert">{error}</div>}

                    {step === 0 && (
                        <div className="space-y-4">
                            <h2 className="text-xl font-bold text-ink-900 dark:text-ink-50">Name your router</h2>
                            <p className="text-sm text-ink-500 dark:text-ink-400">Give it a name you&rsquo;ll recognise later &mdash; the shop or the village usually works best.</p>
                            <input autoFocus value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && createDevice()}
                                placeholder="Serrekunda shop" data-testid="wiz-name"
                                className="w-full bg-white dark:bg-ink-800 dark:text-ink-100 border border-ink-200 dark:border-ink-700 rounded-md px-4 py-3 text-sm" />
                            <div className="flex justify-end">
                                <Button onClick={createDevice} disabled={!name.trim() || busy}>{busy ? 'Adding…' : 'Add router'}</Button>
                            </div>
                        </div>
                    )}

                    {step === 1 && (
                        <div className="space-y-4">
                            <h2 className="text-xl font-bold text-ink-900 dark:text-ink-50">Get the router ready</h2>
                            <div className="grid sm:grid-cols-2 gap-2">
                                <button type="button" aria-pressed={mode === 'full'} onClick={() => setMode('full')}
                                    className={`text-left p-3 rounded-md border text-sm ${mode === 'full' ? 'border-signal-600 bg-signal-600/10' : 'border-ink-200 dark:border-ink-700'} text-ink-900 dark:text-ink-50`}>
                                    <span className="block font-bold">New or reset router</span>
                                    <span className="block text-xs text-ink-500 dark:text-ink-400">NetGuard sets up everything.</span>
                                </button>
                                <button type="button" aria-pressed={mode === 'connect'} onClick={() => setMode('connect')}
                                    className={`text-left p-3 rounded-md border text-sm ${mode === 'connect' ? 'border-signal-600 bg-signal-600/10' : 'border-ink-200 dark:border-ink-700'} text-ink-900 dark:text-ink-50`}>
                                    <span className="block font-bold">It already has a hotspot</span>
                                    <span className="block text-xs text-ink-500 dark:text-ink-400">Keep my setup; just connect NetGuard.</span>
                                </button>
                            </div>
                            {mode === 'full' ? (
                                <>
                                    <RouterDiagram />
                                    <ol className="text-sm text-ink-700 dark:text-ink-200 space-y-2 list-decimal pl-5">
                                        <li>If it&rsquo;s been set up before, reset it: <span className="font-mono text-xs">System &rarr; Reset Configuration</span>, leave &ldquo;No Default Configuration&rdquo; unticked.</li>
                                        <li>Put the <span className="font-bold">internet cable into port 1</span>. This is the one people get wrong.</li>
                                        <li>Plug your laptop into port 2 and open WinBox.</li>
                                        <li>Set your laptop to a fixed address <span className="font-mono text-xs">10.15.0.50</span>, mask <span className="font-mono text-xs">255.255.0.0</span>, so you can still reach the router after setup.</li>
                                    </ol>
                                </>
                            ) : (
                                <ol className="text-sm text-ink-700 dark:text-ink-200 space-y-2 list-decimal pl-5">
                                    <li><span className="font-bold">Do not reset the router.</span> Leave your hotspot, network and login page as they are.</li>
                                    <li>Make sure the router is online, then open WinBox the way you normally do.</li>
                                    <li>NetGuard will add a VPN tunnel, an API user and the payment sites. Nothing of yours is changed or removed.</li>
                                </ol>
                            )}
                            <div className="flex justify-between">
                                <Button variant="ghost" onClick={() => go(0)}>Back</Button>
                                <Button onClick={() => go(2)}>Router is ready</Button>
                            </div>
                        </div>
                    )}

                    {step === 2 && (
                        <div className="space-y-4">
                            <h2 className="text-xl font-bold text-ink-900 dark:text-ink-50">Turn on the VPN</h2>
                            <p className="text-sm text-ink-500 dark:text-ink-400">One click &mdash; there&rsquo;s no script here. This just reserves the router&rsquo;s place on the network. The setup file you actually run on the router comes on the <span className="font-bold">next</span> step, and it already includes this VPN.</p>
                            <div className="flex items-center gap-2 text-sm text-ink-700 dark:text-ink-200"><Wifi size={16} className="text-signal-600 dark:text-signal-300" /> {wgReady ? 'Tunnel ready.' : 'Not set up yet.'}</div>
                            <div className="flex justify-between">
                                <Button variant="ghost" onClick={() => go(1)}>Back</Button>
                                <Button onClick={setupTunnel} disabled={busy}>{busy ? 'Setting up…' : 'Turn on VPN'}</Button>
                            </div>
                        </div>
                    )}

                    {step === 3 && (
                        <div className="space-y-4">
                            <h2 className="text-xl font-bold text-ink-900 dark:text-ink-50">Get your setup file</h2>
                            {!result ? (
                                <>
                                    <label className="block text-xs font-medium text-ink-500 dark:text-ink-400">{mode === 'connect' ? 'Short name (used for the file name)' : 'Short name (becomes the WiFi name)'}</label>
                                    <input value={slug} onChange={(e) => setSlug(slugify(e.target.value))} data-testid="wiz-slug"
                                        className="w-full bg-white dark:bg-ink-800 dark:text-ink-100 border border-ink-200 dark:border-ink-700 rounded-md px-4 py-3 text-sm font-mono" />
                                    <div className="flex justify-between">
                                        <Button variant="ghost" onClick={() => go(2)}>Back</Button>
                                        <Button onClick={getScript} disabled={busy || !slug}>{busy ? 'Generating…' : 'Get script'}</Button>
                                    </div>
                                </>
                            ) : (
                                <>
                                    <div className="p-4 rounded-md bg-warn/10 text-sm text-ink-900 dark:text-ink-50">
                                        <p className="font-bold mb-1">Save this now. It&rsquo;s shown once.</p>
                                        <p>Closing this window clears it, and NetGuard can&rsquo;t show these again.</p>
                                    </div>
                                    <div className="grid sm:grid-cols-2 gap-3">
                                        <div className="bg-ink-50 dark:bg-ink-800 p-3 rounded-md">
                                            <div className="text-xs font-bold text-ink-500 dark:text-ink-400 mb-1">WiFi admin / API password</div>
                                            <code data-testid="wiz-api-pw" className="block font-mono text-sm break-all select-all text-ink-900 dark:text-ink-50">{result.api_password}</code>
                                        </div>
                                        {result.recovery_password && (
                                            <div className="bg-ink-50 dark:bg-ink-800 p-3 rounded-md">
                                                <div className="text-xs font-bold text-ink-500 dark:text-ink-400 mb-1">Recovery login (netguard-recovery)</div>
                                                <code className="block font-mono text-sm break-all select-all text-ink-900 dark:text-ink-50">{result.recovery_password}</code>
                                            </div>
                                        )}
                                    </div>
                                    <div>
                                        <div className="text-xs font-bold text-ink-500 dark:text-ink-400 mb-1">Your setup file</div>
                                        <pre data-testid="wiz-script" className="bg-ink-900 text-ink-100 p-3 rounded-md text-xs font-mono overflow-auto whitespace-pre-wrap max-h-48 border border-ink-700">{result.script}</pre>
                                    </div>
                                    <div className="flex flex-wrap gap-3">
                                        <Button variant="outline" onClick={download}><Download size={16} className="mr-1" /> Download .rsc</Button>
                                        <Button variant="outline" onClick={copy}><Copy size={16} className="mr-1" /> {copied ? 'Copied' : 'Copy script'}</Button>
                                        <Button onClick={() => go(4)} className="ml-auto">Next</Button>
                                    </div>
                                </>
                            )}
                        </div>
                    )}

                    {step === 4 && (
                        <div className="space-y-4">
                            <h2 className="text-xl font-bold text-ink-900 dark:text-ink-50">Apply it to the router</h2>
                            <WinboxDiagram />
                            <p className="text-sm text-ink-700 dark:text-ink-200">
                                <span className="font-bold">Quickest:</span> paste the whole script into the WinBox terminal in one go.
                                Or drag the <span className="font-mono text-xs">.rsc</span> into <span className="font-bold">Files</span> and run:
                            </p>
                            <code className="block bg-ink-900 text-ink-100 p-3 rounded-md text-xs font-mono overflow-x-auto">/import file-name=netguard-{result?.site_slug || '<name>'}.rsc</code>
                            {mode === 'connect'
                                ? <p className="text-xs text-ink-500 dark:text-ink-400">Your hotspot keeps running and your WinBox stays connected. Afterwards, add the Buy button from the router&rsquo;s Captive Portal card.</p>
                                : <p className="text-xs text-ink-500 dark:text-ink-400">Your WinBox will drop partway through when the ports move. That&rsquo;s expected &mdash; reconnect on <span className="font-mono">10.15.0.50</span>.</p>}
                            <div className="flex justify-between">
                                <Button variant="ghost" onClick={() => go(3)}>Back</Button>
                                <Button onClick={() => go(5)}>I&rsquo;ve applied it</Button>
                            </div>
                        </div>
                    )}

                    {step === 5 && (
                        <div className="space-y-4">
                            <h2 className="text-xl font-bold text-ink-900 dark:text-ink-50">Check it works</h2>
                            <div className={`p-4 rounded-md text-sm ${reach === 'connected' ? 'bg-up/10 text-up dark:text-ink-50' : 'bg-ink-50 dark:bg-ink-800 text-ink-700 dark:text-ink-200'}`} data-testid="wiz-reach">
                                {reach === 'connected'
                                    ? <span className="font-bold flex items-center gap-2"><Check size={16} /> Connected. NetGuard is reading this router.</span>
                                    : <span>Waiting for the router to come online&hellip; this can take a minute after you apply the script.</span>}
                            </div>
                            <p className="text-sm font-bold text-ink-900 dark:text-ink-50">With a phone, check:</p>
                            <ol className="text-sm text-ink-700 dark:text-ink-200 space-y-1 list-decimal pl-5">
                                <li>The new WiFi name appears and you can join it.</li>
                                <li>The login page comes up by itself.</li>
                                <li>After logging in (test login <span className="font-mono text-xs">admin</span> / <span className="font-mono text-xs">root</span>), the internet works.</li>
                            </ol>
                            <p className="text-xs text-warn">If you haven&rsquo;t already set the router&rsquo;s admin (WinBox) password, set it now &mdash; this script never changes it, and a factory router starts blank.</p>
                            <div className="flex justify-end">
                                <Button onClick={finish}>Finish</Button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

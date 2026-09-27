import React, { useState, useEffect, useRef } from 'react';
import api from '../../api';
import { LayoutDashboard, Users, CreditCard, Activity, RefreshCw, Trash, Printer, X, Scissors, Shield, Clock, Settings, Search, FileText, Globe, AlertCircle, TrendingUp } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip, Legend } from 'recharts';
import ResponsiveModal from '../../components/ResponsiveModal';
import SalesForecast from '../../components/SalesForecast';
import { MetricCard, TabButton } from './components';
import LogsPanel from './panels/LogsPanel';
import ReportsPanel from './panels/ReportsPanel';
import ProfilesPanel from './panels/ProfilesPanel';
import ActivePanel from './panels/ActivePanel';
import UsersPanel from './panels/UsersPanel';
import BooksPanel from './panels/BooksPanel';
import GeneratorPanel from './panels/GeneratorPanel';

// Device-scoped so two routers' in-flight generation jobs never clobber
// each other's localStorage entry.
const voucherJobStorageKey = (deviceId) => `hotspot_voucher_job_${deviceId}`;

const VOUCHER_JOB_POLL_MS = 3000;

// A poll that fails this many times in a row for a reason other than a
// confirmed 404 (a real network/server problem, not "the job is gone") is
// treated as unrecoverable -- see pollVoucherJob's catch block.
//
// 10 misses (~30s at the 3s poll interval) rather than 3 (~9s): a backend
// restart during a deploy -- including this one's own -- takes roughly
// 10-30s, which is LONGER than the old 3-miss/9s threshold. That made any
// brief backend blip abandon a perfectly healthy in-flight job. The
// stale-id case this counter was never meant to catch (a job_id left over
// from a wiped database, a different environment, etc) already takes the
// immediate 404 path below, not this one -- so raising this costs nothing
// for that case and only stops healthy jobs from being thrown away.
const MAX_TRANSIENT_POLL_FAILURES = 10;

// C1: a job stuck at "running"/"queued" forever (worker crashed after
// BRPOP'ing it, worker not running, backend unreachable at its last progress
// report) returns HTTP 200 every time it's polled -- never a 404, never a
// run of errors -- so neither escape hatch above ever fires. This is the
// second, independent escape: if `created` (vouchers actually recorded so
// far) hasn't advanced in this long, treat the job as stalled and abandon it
// client-side.
//
// Why 3 minutes: the worker flushes progress about every 10 vouchers, and
// each voucher takes ~187ms on the router, so a *normal* gap between
// progress reports is ~2s (10 * 187ms). A slow or contended router could
// stretch that considerably -- and on top of that, I1's own terminal-report
// retry deliberately backs off for up to ~30s on a flaky backend, during
// which `created` legitimately does not move. 3 minutes comfortably outlasts
// both of those without being so long that a genuinely stuck job leaves the
// operator staring at a disabled Generate button for the rest of their shift.
const VOUCHER_JOB_STALL_MS = 3 * 60 * 1000;

export default function Hotspot() {
    const [activeTab, setActiveTab] = useState('dashboard');
    const [devices, setDevices] = useState([]);
    const [selectedDevice, setSelectedDevice] = useState(null);
    const [users, setUsers] = useState([]);
    const [activeSessions, setActiveSessions] = useState([]);
    const [profiles, setProfiles] = useState([]);
    const [dashboardData, setDashboardData] = useState(null);
    const [systemInfo, setSystemInfo] = useState(null);
    const [batchHistory, setBatchHistory] = useState([]);
    const [logs, setLogs] = useState([]);
    const [reportData, setReportData] = useState(null);
    const [reportPage, setReportPage] = useState(1);
    const [healthStatus, setHealthStatus] = useState('unknown');
    const [loading, setLoading] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [prefetching, setPrefetching] = useState(false);
    const [dataFreshness, setDataFreshness] = useState({});
    const [showProfileModal, setShowProfileModal] = useState(false);
    const [profileForm, setProfileForm] = useState({ name: '', rateLimit: '1M/1M', sharedUsers: 1 });
    const [userSearch, setUserSearch] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [isSearching, setIsSearching] = useState(false);
    const [logSearch, setLogSearch] = useState('');
    const [logFilter, setLogFilter] = useState('all');
    const [reportSearch, setReportSearch] = useState('');
    const [showPriceModal, setShowPriceModal] = useState(false);
    const [selectedProfileSettings, setSelectedProfileSettings] = useState({ name: '', price: 0, currency: 'TZS' });
    const [reportPeriod, setReportPeriod] = useState('');
    const [reportStartDate, setReportStartDate] = useState('');
    const [reportEndDate, setReportEndDate] = useState('');

    const filteredReports = reportData?.data?.filter(r =>
        (r.username || '').toLowerCase().includes(reportSearch.toLowerCase()) ||
        (r.profile || '').toLowerCase().includes(reportSearch.toLowerCase()) ||
        (r.comment || '').toLowerCase().includes(reportSearch.toLowerCase())
    ) || [];

    // Generation State
    const [batchForm, setBatchForm] = useState({ qty: 10, prefix: 'user', profile: 'default', time_limit: '1h', data_limit: '', length: 10, random_mode: false, format: 'alphanumeric' });
    const [generatedBatch, setGeneratedBatch] = useState([]);
    // C2 (version-skew: old frontend still open, new backend already
    // deployed): the old page's handleGenerate destructures {job_id,...}
    // straight into setGeneratedBatch, so generatedBatch can end up holding
    // that plain object instead of an array once the backend moves to the
    // job shape. We can't patch code already served to that open tab, but
    // rendering here must not assume generatedBatch is an array just
    // because the setter's declared type says so -- anything non-array
    // renders as empty instead of throwing "generatedBatch.map is not a
    // function" and hard-crashing the page.
    const safeGeneratedBatch = Array.isArray(generatedBatch) ? generatedBatch : [];
    const [showPrintView, setShowPrintView] = useState(false);
    // Background voucher-generation job (Task 5): the batch endpoint now
    // returns 202 + job_id instead of the vouchers themselves. This tracks
    // that job's poll state so the operator sees progress, and survives a
    // page reload / screen lock via the device-scoped localStorage key below.
    const [voucherJob, setVoucherJob] = useState(null); // { job_id, status, count, created, vouchers }
    const pollIntervalRef = useRef(null);
    // Consecutive poll failures that were NOT a confirmed "job is gone" (404)
    // -- see pollVoucherJob's catch block.
    const pollFailureCountRef = useRef(0);
    // Last-seen `created` count and `status`, and when either was last
    // observed to change -- see VOUCHER_JOB_STALL_MS / pollVoucherJob's
    // stall check below (C1). `status` is tracked alongside `created`
    // because there's exactly one voucher-worker (no replicas in compose,
    // one job at a time) and qty is unbounded, so a second job can sit
    // "queued" behind a large one for minutes -- created stays 0 the whole
    // time, but that's the queue doing its job, not a stall. See the stall
    // check itself for why only "running" counts toward the timeout.
    const lastProgressRef = useRef({ created: null, status: null, at: 0 });

    // Template State
    const [template, setTemplate] = useState({
        header_text: "Wi-Fi Voucher",
        footer_text: "Thank you for visiting!",
        logo_url: "",
        color_primary: "#2563EB"
    });

    useEffect(() => {
        fetchDevices();
    }, []);

    // On device select: prefetch all common tabs in parallel so switching is instant
    useEffect(() => {
        if (selectedDevice) {
            prefetchAll(selectedDevice);
        }
    }, [selectedDevice]);

    // Resume any in-flight voucher generation job on mount and whenever the
    // selected device changes. This is what makes it safe for the operator
    // to leave the Hotspot page, lock their screen, or reload mid-batch --
    // the job keeps running on the router/worker regardless, and this effect
    // reconnects the UI to it instead of losing progress.
    useEffect(() => {
        if (!selectedDevice) return;
        const storedJobId = localStorage.getItem(voucherJobStorageKey(selectedDevice));
        if (storedJobId) {
            setVoucherJob({ job_id: storedJobId, status: 'running', count: 0, created: 0, vouchers: [] });
            pollVoucherJob(storedJobId, selectedDevice);
        } else {
            stopPolling();
            setVoucherJob(null);
        }
        return () => stopPolling();
    }, [selectedDevice]);

    // Fetch data when tab changes (show stale data immediately, refresh silently)
    useEffect(() => {
        if (selectedDevice) {
            fetchData();
        }
    }, [activeTab]);

    // Fetch data when report filters change
    useEffect(() => {
        if (selectedDevice && activeTab === 'reports') {
            fetchData();
        }
    }, [reportPeriod, reportStartDate, reportEndDate]);

    // Search fallback: if local filter returns nothing, query router directly
    useEffect(() => {
        if (!selectedDevice || !userSearch.trim() || activeTab !== 'users') {
            setSearchResults([]);
            return;
        }
        const q = userSearch.toLowerCase().trim();
        const filtered = users.filter(u => (u.name || '').toLowerCase().includes(q) || (u.comment || '').toLowerCase().includes(q));
        if (filtered.length > 0) {
            setSearchResults([]);
            return;
        }
        // Local filter empty — search router directly
        const timer = setTimeout(async () => {
            setIsSearching(true);
            try {
                const res = await api.get(`/hotspot/${selectedDevice}/users/search?name=${encodeURIComponent(q)}`);
                setSearchResults(Array.isArray(res.data) ? res.data : [res.data]);
            } catch (e) {
                setSearchResults([]);
            } finally {
                setIsSearching(false);
            }
        }, 400);
        return () => clearTimeout(timer);
    }, [userSearch, selectedDevice, activeTab, users]);

    // Poll Dashboard and Active tabs every 15 seconds
    useEffect(() => {
        if (!selectedDevice) return;
        if (activeTab !== 'dashboard' && activeTab !== 'active') return;
        fetchData();
        const interval = setInterval(fetchData, 15000);
        return () => clearInterval(interval);
    }, [selectedDevice, activeTab]);

    const fetchDevices = async () => {
        try {
            const res = await api.get('/inventory/devices');
            const routers = res.data.filter(d => d.device_type?.toLowerCase() === 'router');
            setDevices(routers);
            if (routers.length > 0 && !selectedDevice) {
                setSelectedDevice(routers[0].id);
            }
        } catch (e) {
            console.error(e);
        }
    };


    const fetchProfiles = async (deviceId) => {
        setLoading(true);
        try {
            const res = await api.get(`/hotspot/${deviceId}/profiles`);
            setProfiles(res.data);
        } catch (e) {
            console.error("Failed to fetch profiles:", e);
        } finally {
            setLoading(false);
        }
    };

    const fetchTemplate = async (deviceId) => {
        try {
            const res = await api.get(`/hotspot/${deviceId}/voucher-template`);
            if (res.data) setTemplate(res.data);
            setDataFreshness(prev => ({ ...prev, templates: Date.now() }));
        } catch (e) {
            console.error("Failed to fetch template:", e);
        }
    };

    const refreshCurrentTab = () => {
        setDataFreshness(prev => ({ ...prev, [activeTab]: 0 }));
        fetchData();
    };

    // Batch history used to be derived entirely by grouping the /users list
    // by comment -- which meant it went empty whenever the voucher cache
    // was empty, even though the batches themselves still existed. It now
    // renders straight from GET /{device_id}/batches (the persisted
    // VoucherBatch rows), which exists independently of that cache.
    //
    // "used" still isn't tracked on VoucherBatch, so it's cross-referenced
    // here against whatever the router's /users list currently reports for
    // each voucher's username -- best-effort, and 0 if that list hasn't
    // loaded, but the batch itself (and its reprint/delete actions) no
    // longer depends on it being populated.
    const buildBatchHistoryFromBatches = (batchesRaw, usersList) => {
        const usageByName = new Map((usersList || []).filter(u => u.name).map(u => [u.name, u]));
        return (batchesRaw || []).map(b => {
            const vouchers = b.vouchers || b.data || [];
            const used = vouchers.filter(v => {
                const u = usageByName.get(v.username);
                return u && u.uptime && u.uptime !== '0s';
            }).length;
            return {
                id: b.id,
                name: b.name,
                displayName: b.displayName,
                count: b.count,
                used,
                profile: b.profile,
                timeLimit: b.timeLimit || '',
                date: b.date,
                status: b.status,
                data: vouchers,
            };
        });
    };

    // Fire all tab requests in parallel as soon as a device is selected.
    // Data lands in state silently — by the time the user clicks a tab it's ready.
    const prefetchAll = async (deviceId) => {
        setPrefetching(true);
        const now = Date.now();
        try {
            // Phase 1: fetch the fast/common tabs first
            const [summaryRes, systemRes, usersRes, activeRes, profilesRes, templateRes] = await Promise.allSettled([
                api.get(`/hotspot/${deviceId}/summary`),
                api.get(`/hotspot/${deviceId}/system-info`),
                api.get(`/hotspot/${deviceId}/users?limit=200`),
                api.get(`/hotspot/${deviceId}/active?limit=200`),
                api.get(`/hotspot/${deviceId}/profiles`),
                api.get(`/hotspot/${deviceId}/voucher-template`),
            ]);
            if (summaryRes.status === 'fulfilled') {
                setDashboardData(summaryRes.value.data);
                // The read endpoints never throw anymore (they serve from
                // cache), so "the request succeeded" no longer means "the
                // router/agent/Redis are healthy". /summary's `stale` field
                // is the real signal: a dead router/VPN/agent/Redis shows up
                // as stale cached data, not an HTTP error.
                setHealthStatus(summaryRes.value.data?.stale ? 'offline' : 'online');
            } else {
                setHealthStatus('offline');
            }
            if (systemRes.status === 'fulfilled') setSystemInfo(systemRes.value.data);
            if (usersRes.status === 'fulfilled') setUsers(usersRes.value.data);
            if (activeRes.status === 'fulfilled') setActiveSessions(activeRes.value.data);
            if (profilesRes.status === 'fulfilled') setProfiles(profilesRes.value.data);
            if (templateRes.status === 'fulfilled' && templateRes.value.data) setTemplate(templateRes.value.data);

            // Phase 2: fetch heavier tabs in background so they are ready when clicked
            const [logsRes, reportsRes, allUsersRes, batchesRes] = await Promise.allSettled([
                api.get(`/hotspot/${deviceId}/logs`),
                api.get(`/hotspot/${deviceId}/reports`),
                api.get(`/hotspot/${deviceId}/users?limit=0`), // full list for batch history accuracy
                api.get(`/hotspot/${deviceId}/batches`),
            ]);
            if (logsRes.status === 'fulfilled') setLogs(logsRes.value.data);
            if (reportsRes.status === 'fulfilled') setReportData(reportsRes.value.data);
            const fullUsersList = allUsersRes.status === 'fulfilled' ? allUsersRes.value.data : users;
            if (allUsersRes.status === 'fulfilled') setUsers(fullUsersList);
            if (batchesRes.status === 'fulfilled') {
                setBatchHistory(buildBatchHistoryFromBatches(batchesRes.value.data, fullUsersList));
            }

            setDataFreshness({
                dashboard: now,
                users: now,
                history: now,
                active: now,
                logs: now,
                reports: now,
                profiles: now,
                templates: now,
            });
        } catch (e) {
            console.error('Prefetch error', e);
        } finally {
            setPrefetching(false);
        }
    };

    const saveTemplate = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await api.post(`/hotspot/${selectedDevice}/voucher-template`, template);
            if (res.data) alert('Template saved!');
        } catch (e) {
            alert("Failed to save template.");
        } finally {
            setLoading(false);
        }
    };

    const fetchData = async () => {
        if (!selectedDevice) return;

        const FRESHNESS_MS = 30000; // 30 seconds
        const alreadyHasData = {
            dashboard: !!dashboardData,
            users: users.length > 0,
            history: batchHistory.length > 0,
            active: activeSessions.length > 0,
            logs: logs.length > 0,
            reports: !!reportData,
            profiles: profiles.length > 0,
            templates: !!template.header_text,
        }[activeTab] ?? false;

        const lastFetch = dataFreshness[activeTab];
        const isFresh = lastFetch && (Date.now() - lastFetch) < FRESHNESS_MS;

        // If prefetched data is fresh and present, render instantly without network round-trip
        if (alreadyHasData && isFresh) {
            return;
        }

        if (!alreadyHasData) setLoading(true);
        else setIsRefreshing(true);

        try {
            if (activeTab === 'dashboard') {
                const [summaryRes, systemRes] = await Promise.all([
                    api.get(`/hotspot/${selectedDevice}/summary`),
                    api.get(`/hotspot/${selectedDevice}/system-info`)
                ]);
                setDashboardData(summaryRes.data);
                setSystemInfo(systemRes.data);
                // Drive health from /summary's `stale` flag, not from
                // whether the request threw (it always serves from cache
                // and never does) -- see I1.
                setHealthStatus(summaryRes.data?.stale ? 'offline' : 'online');
            } else if (activeTab === 'users') {
                const res = await api.get(`/hotspot/${selectedDevice}/users?limit=200`);
                setUsers(res.data);
            } else if (activeTab === 'history') {
                // allSettled, not all: a /batches hiccup shouldn't also throw
                // away a perfectly good /users result (and vice versa).
                const [usersRes, batchesRes] = await Promise.allSettled([
                    api.get(`/hotspot/${selectedDevice}/users?limit=0`),
                    api.get(`/hotspot/${selectedDevice}/batches`),
                ]);
                const usersList = usersRes.status === 'fulfilled' ? usersRes.value.data : users;
                if (usersRes.status === 'fulfilled') setUsers(usersList);
                if (batchesRes.status === 'fulfilled') {
                    setBatchHistory(buildBatchHistoryFromBatches(batchesRes.value.data, usersList));
                }
            } else if (activeTab === 'active') {
                const res = await api.get(`/hotspot/${selectedDevice}/active?limit=200`);
                setActiveSessions(res.data);
            } else if (activeTab === 'logs') {
                const res = await api.get(`/hotspot/${selectedDevice}/logs`);
                setLogs(res.data);
            } else if (activeTab === 'reports') {
                const params = new URLSearchParams();
                if (reportPeriod) params.append('period', reportPeriod);
                if (reportStartDate) params.append('start_date', reportStartDate);
                if (reportEndDate) params.append('end_date', reportEndDate);
                const [reportRes, templateRes] = await Promise.all([
                    api.get(`/hotspot/${selectedDevice}/reports?${params.toString()}`),
                    api.get(`/hotspot/${selectedDevice}/voucher-template`)
                ]);
                setReportData(reportRes.data);
                if (templateRes.data) setTemplate(templateRes.data);
            } else if (activeTab === 'profiles') {
                const [profilesRes, templateRes] = await Promise.all([
                    api.get(`/hotspot/${selectedDevice}/profiles`),
                    api.get(`/hotspot/${selectedDevice}/voucher-template`)
                ]);
                setProfiles(profilesRes.data);
                if (templateRes.data) setTemplate(templateRes.data);
            } else if (activeTab === 'templates') {
                await fetchTemplate(selectedDevice);
            }

            setDataFreshness(prev => ({ ...prev, [activeTab]: Date.now() }));
        } catch (e) {
            console.error(e);
            if (activeTab !== 'templates') setHealthStatus('offline');
        } finally {
            setLoading(false);
            setIsRefreshing(false);
        }
    };

    const handleReprint = (batch) => {
        const timeLimit = batch.timeLimit || batch.data[0]?.['limit-uptime'] || batch.data[0]?.limit_uptime || batchForm.time_limit || '';
        // batch.data items come from GET /{device}/batches now, shaped like
        // VoucherBatch.vouchers ({username, password}) rather than the old
        // router-user shape ({name, password, ...}) -- accept either so
        // reprint keeps working regardless of which produced this batch.
        setGeneratedBatch(batch.data.map(u => ({ username: u.username || u.name, password: u.password })));
        setBatchForm({ ...batchForm, profile: batch.profile, time_limit: timeLimit });
        // This print view is unrelated to any generation job, so clear any
        // leftover job state that could otherwise attach a stale "N / count"
        // note (below) to a batch it doesn't belong to.
        setVoucherJob(null);
        setShowPrintView(true);
    };

    const handleKick = async (id) => {
        if (!window.confirm("Disconnect this user?")) return;
        try {
            await api.delete(`/hotspot/${selectedDevice}/active/${id}`);
            fetchData();
        } catch (e) {
            alert("Failed to kick user.");
        }
    };

    const handleProfileAdd = async (e) => {
        e.preventDefault();
        if (!selectedDevice) return;
        try {
            await api.post(`/hotspot/${selectedDevice}/profiles`, {
                name: profileForm.name,
                'rate-limit': profileForm.rateLimit,
                'shared-users': profileForm.sharedUsers
            });
            setShowProfileModal(false);
            setProfileForm({ name: '', rateLimit: '1M/1M', sharedUsers: 1 }); // Reset form
            fetchProfiles(selectedDevice);
        } catch (err) {
            alert("Failed to add profile: " + (err.response?.data?.detail || err.message));
        }
    };

    const handleProfileDelete = async (name) => {
        if (!selectedDevice) return;
        if (!confirm(`Are you sure you want to delete profile "${name}"?`)) return;
        try {
            await api.delete(`/hotspot/${selectedDevice}/profiles/${name}`);
            fetchProfiles(selectedDevice);
        } catch (err) {
            alert("Failed to delete profile: " + (err.response?.data?.detail || err.message));
        }
    };

    const handleUpdatePriceSettings = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            await api.post(`/hotspot/${selectedDevice}/profiles/${selectedProfileSettings.name}/settings`, {
                price: selectedProfileSettings.price,
                currency: selectedProfileSettings.currency
            });
            setShowPriceModal(false);
            fetchData();
        } catch (err) {
            alert("Failed to update price settings: " + (err.response?.data?.detail || err.message));
        } finally {
            setLoading(false);
        }
    };

    const stopPolling = () => {
        if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
        }
    };

    // Polls GET /hotspot/jobs/{job_id} until the job reaches a terminal
    // state (complete or failed). On either terminal state the job's own
    // vouchers -- not just "complete" ones -- are pushed into
    // generatedBatch so the existing print view renders them unchanged: a
    // failed job's partial vouchers are real, sellable vouchers already
    // created on the router, and the operator must be able to print them.
    const pollVoucherJob = (jobId, deviceId) => {
        stopPolling();
        pollFailureCountRef.current = 0;
        lastProgressRef.current = { created: null, status: null, at: Date.now() };

        // Give up on this job entirely: stop polling, forget it so a future
        // mount doesn't resume something dead, reset voucherJob to null so
        // the Generate button re-enables, and tell the operator why -- a
        // silent reset still leaves them wondering what happened to their
        // batch, and the alert() below is the same mechanism every other
        // handler in this component already uses for errors.
        const giveUp = (message) => {
            stopPolling();
            localStorage.removeItem(voucherJobStorageKey(deviceId));
            setVoucherJob(null);
            alert(message);
        };

        const tick = async () => {
            try {
                const res = await api.get(`/hotspot/jobs/${jobId}`);
                pollFailureCountRef.current = 0;
                const job = res.data;
                setVoucherJob(job);
                if (job.status === 'complete' || job.status === 'failed') {
                    stopPolling();
                    setGeneratedBatch(job.vouchers || []);
                    setShowPrintView(true);
                    // Terminal state shown to the operator -- forget the job so a
                    // future mount doesn't try to resume something already done.
                    localStorage.removeItem(voucherJobStorageKey(deviceId));
                    return;
                }

                // C1: a job stuck "running" forever returns this exact 200
                // response every single poll -- there is no error for the two
                // escape hatches below to catch. Detect it ourselves: if
                // `created` hasn't moved since the last time we checked, and
                // it's been at least VOUCHER_JOB_STALL_MS since it last did,
                // this job is making no forward progress. Give up client-side
                // (the manual Dismiss button next to the progress bar is the
                // other way out, for an operator who doesn't want to wait for
                // the timeout).
                //
                // The clock only ever COUNTS DOWN while status === 'running'.
                // There is a single voucher-worker (no replicas in compose,
                // one job at a time) and qty is unbounded, so a second job
                // (another device, another tab, a re-Generate after a
                // Dismiss) can legitimately sit "queued" behind a large one
                // for minutes -- created stays 0 that whole time, and that is
                // the queue doing its job, not a stall. Treating that as
                // stalled clears the id and re-enables Generate while the
                // first job is still genuinely running, which is how an
                // operator ends up starting a second, duplicate job for one
                // request (paid-for duplicate vouchers, not just wasted time).
                //
                // A "queued" job is therefore never auto-abandoned, no matter
                // how long it stays queued -- including the case where the
                // queue truly is stuck (worker down, nothing draining it).
                // That case is indistinguishable from "just waiting behind a
                // long job" purely from this response shape, so any timeout
                // here would reintroduce the exact double-submission risk
                // above. The manual Dismiss control is the intended and
                // sufficient escape for a forever-queued job: it's already
                // operator-driven (nothing fires without the operator
                // choosing to fire it), so it can't fire *for* a job that's
                // actually still progressing behind the scenes.
                //
                // The queued -> running transition itself counts as forward
                // progress (the job left the queue and started doing real
                // work) even though `created` is still 0 at that instant, so
                // a `status` change also resets the clock, not only a
                // `created` change.
                const createdNow = job.created ?? 0;
                const prevProgress = lastProgressRef.current;
                const progressed = prevProgress.created === null
                    || createdNow !== prevProgress.created
                    || job.status !== prevProgress.status;
                if (progressed) {
                    lastProgressRef.current = { created: createdNow, status: job.status, at: Date.now() };
                } else if (job.status === 'running' && Date.now() - prevProgress.at >= VOUCHER_JOB_STALL_MS) {
                    giveUp('This voucher batch has made no progress for a while and may be stuck. It may still be running on the router -- check the History tab shortly. You can start a new batch now.');
                }
            } catch (e) {
                console.error('Failed to poll voucher job:', e);
                if (e.response?.status === 404) {
                    // The job genuinely does not exist (deleted batch row, a
                    // database restored from backup, a stale id from another
                    // environment) -- there is nothing left to poll for, so
                    // clear it immediately rather than hammering the backend
                    // every 3s forever with the Generate button stuck disabled.
                    giveUp('This voucher batch could not be found (it may have been deleted). You can start a new batch now.');
                    return;
                }
                // Anything else (network hiccup, 5xx, timeout) might just be a
                // blip -- the job could still be running and creating real
                // vouchers on the router. Tolerate a few consecutive failures
                // before concluding we've actually lost it, so one bad request
                // doesn't throw away progress on a batch that's still going.
                pollFailureCountRef.current += 1;
                if (pollFailureCountRef.current >= MAX_TRANSIENT_POLL_FAILURES) {
                    giveUp('Lost contact while tracking this voucher batch. It may still be running on the router -- check the History tab shortly. You can start a new batch now.');
                }
            }
        };
        tick();
        pollIntervalRef.current = setInterval(tick, VOUCHER_JOB_POLL_MS);
    };

    // C1 manual escape hatch: a guaranteed way out that doesn't depend on
    // VOUCHER_JOB_STALL_MS being the right value for every situation. Purely
    // local -- stops polling, forgets the job id, re-enables Generate. It
    // deliberately does NOT attempt to cancel anything server-side: the
    // worker/router job (if it's even still alive) is left alone, exactly
    // like the timeout-driven giveUp() path above.
    const dismissVoucherJob = () => {
        stopPolling();
        if (selectedDevice) localStorage.removeItem(voucherJobStorageKey(selectedDevice));
        setVoucherJob(null);
    };

    const handleGenerate = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await api.post(`/hotspot/${selectedDevice}/users/batch`, batchForm);
            const data = res.data;

            // C2 (version-skew: new frontend served before the backend
            // restarts): the OLD synchronous /users/batch returns 200 with a
            // plain array of {username, password} vouchers, not
            // {job_id, status, count}. The old backend already created and
            // committed those vouchers -- treat this exactly like the
            // pre-background-job code did (render them straight into the
            // print view) instead of destructuring a job shape that isn't
            // there. Do NOT store a job id or start polling: there is no job,
            // and polling "/jobs/undefined" would just hammer the backend
            // while the operator never sees vouchers that already exist.
            if (Array.isArray(data) || !data || typeof data !== 'object' || !data.job_id) {
                setVoucherJob(null);
                setGeneratedBatch(Array.isArray(data) ? data : []);
                setShowPrintView(true);
                return;
            }

            const { job_id, status, count, detail } = data;

            // I3: an enqueue failure (e.g. Redis down) comes back 202 with
            // status: "failed" and a `detail` message, not an HTTP error --
            // surfacing it here instead of storing the job id and polling
            // means the operator sees why, instead of an empty "Ready to
            // export 0 vouchers" print view a moment later.
            if (status === 'failed') {
                alert('Voucher generation failed: ' + (detail || 'Unknown error.'));
                return;
            }

            localStorage.setItem(voucherJobStorageKey(selectedDevice), job_id);
            setVoucherJob({ job_id, status, count, created: 0, vouchers: [] });
            setGeneratedBatch([]);
            setShowPrintView(false);
            pollVoucherJob(job_id, selectedDevice);
        } catch (e) {
            alert('Generation failed: ' + (e.response?.data?.detail || e.message));
        } finally {
            setLoading(false);
        }
    };



    const handleCleanupExpired = async () => {
        if (!window.confirm("Delete all users who have reached their time or data limits?")) return;
        setLoading(true);
        try {
            const res = await api.delete(`/hotspot/${selectedDevice}/users/bulk?expired=true`);
            alert(`Cleaned up ${res.data.count} expired users.`);
            fetchData();
        } catch (e) {
            alert("Cleanup failed: " + (e.response?.data?.detail || e.message));
        } finally {
            setLoading(false);
        }
    };

    const handleBulkDeleteByComment = async (comment) => {
        if (!window.confirm(`Delete all users in batch "${comment}"?`)) return;
        setLoading(true);
        try {
            const res = await api.delete(`/hotspot/${selectedDevice}/users/bulk?comment=${comment}`);
            alert(`Deleted ${res.data.count} users.`);
            fetchData();
        } catch (e) {
            alert("Bulk delete failed.");
        } finally {
            setLoading(false);
        }
    };

    const handleExportCSV = async () => {
        try {
            const res = await api.get(`/hotspot/${selectedDevice}/users/export`, { responseType: 'blob' });
            const url = window.URL.createObjectURL(new Blob([res.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `hotspot_users_${selectedDevice}.csv`);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (e) {
            alert("Export failed.");
        }
    };

    const handleDelete = async (name) => {
        if (!window.confirm(`Are you sure you want to delete user "${name}"?`)) return;
        setLoading(true);
        try {
            await api.delete(`/hotspot/${selectedDevice}/users/${name}`);
            fetchData();
        } catch (e) {
            alert("Delete failed: " + (e.response?.data?.detail || e.message));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-ink-50 dark:bg-ink-900 pt-4 sm:pt-8 px-4 sm:px-6 lg:px-10 pb-12">
            <style>{`
                @media print {
                    @page { margin: 5mm; size: auto; }
                    body * { visibility: hidden; }
                    #printable-area, #printable-area * { visibility: visible; }
                    #printable-area { 
                        position: absolute; 
                        left: 0; 
                        top: 0; 
                        width: 100%; 
                        display: block !important;
                    }
                    .no-print { display: none !important; }
                    
                    /* Grid simulation using inline-block for better print support */
                    .voucher-card { 
                        display: inline-block !important;
                        width: 19% !important; /* Slightly wider */
                        margin: 0.5% !important; /* Tighter margins */
                        vertical-align: top;
                        
                        page-break-inside: avoid !important; 
                        break-inside: avoid !important;
                        page-break-after: auto;
                        
                        border: 1px dashed #ccc; 
                        box-sizing: border-box;
                    }
                    
                    /* Dynamic Print Styles */
                    .print-header { color: ${template.color_primary} !important; }
                    .print-border { border-color: ${template.color_primary} !important; }
                    .print-bg { background-color: ${template.color_primary}10 !important; } /* 10% opacity */
                }
            `}</style>

            <div className="max-w-7xl mx-auto">
                {/* Page Header */}
                <div className="mb-8 sm:mb-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6 no-print">
                    <div>
                        <h1 className="text-3xl sm:text-4xl font-semibold text-ink-900 dark:text-ink-50 tracking-tight leading-none">
                            Hotspot <span className="text-signal-600 dark:text-signal-300">Controller</span>
                        </h1>
                        <p className="text-ink-500 dark:text-ink-400 mt-2 font-medium text-sm sm:text-base">Enterprise voucher management and hotspot profile orchestration.</p>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="flex flex-col items-end gap-1 px-3">
                            <div className="flex items-center gap-1.5">
                                <div className={`w-2 h-2 rounded-full ${healthStatus === 'online' ? 'bg-up animate-pulse' : healthStatus === 'offline' ? 'bg-down' : 'bg-ink-300'}`}></div>
                                <span className={`text-xs font-semibold ${healthStatus === 'online' ? 'text-up dark:text-ink-100' : healthStatus === 'offline' ? 'text-down dark:text-ink-100' : 'text-ink-500 dark:text-ink-400'}`}>
                                    {healthStatus === 'online' ? 'Sync Active' : healthStatus === 'offline' ? 'Sync Failed' : 'Checking...'}
                                </span>
                            </div>
                        </div>
                        <select
                            className="bg-white dark:bg-ink-800 border border-ink-200 dark:border-ink-700 rounded-lg px-4 sm:px-5 py-3 shadow-sm focus:ring-2 focus:ring-signal-500 outline-none transition-all font-bold text-ink-900 dark:text-ink-100 flex-1 lg:min-w-[240px] text-sm sm:text-base"
                            value={selectedDevice || ''}
                            onChange={e => setSelectedDevice(e.target.value)}
                        >
                            <option value="" disabled>Select Core Router</option>
                            {devices.map(d => <option key={d.id} value={d.id}>{d.name} ({d.ip_address})</option>)}
                        </select>
                        <button
                            onClick={refreshCurrentTab}
                            className="bg-white dark:bg-ink-800 p-3 border border-ink-200 dark:border-ink-700 rounded-lg shadow-sm hover:bg-ink-50 dark:hover:bg-ink-700 text-ink-500 dark:text-ink-100 transition-all active:scale-95 flex-shrink-0"
                            title="Refresh Data"
                        >
                            <RefreshCw size={22} className={(loading || isRefreshing || prefetching) ? 'animate-spin text-signal-600' : ''} />
                        </button>
                    </div>
                    {prefetching && (
                        <div className="no-print mt-3 flex justify-end">
                            <span className="inline-flex items-center gap-2 px-3 py-1.5 bg-signal-600/10 dark:bg-signal-600/20 text-ink-900 dark:text-ink-50 rounded-md text-xs font-semibold">
                                <RefreshCw size={12} className="animate-spin" /> Preloading all tabs...
                            </span>
                        </div>
                    )}
                </div>

                {/* Navigation Bar */}
                <div className="mb-8 sm:mb-10 no-print">
                    <div className="flex bg-white dark:bg-ink-800 p-1.5 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700 gap-1.5 overflow-x-auto no-scrollbar scroll-smooth">
                        <TabButton id="dashboard" label="Dashboard" icon={LayoutDashboard} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="active" label="Active" icon={Activity} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="users" label="Vouchers" icon={CreditCard} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="history" label="Books" icon={Search} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="logs" label="Logs" icon={FileText} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="reports" label="Report" icon={FileText} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="forecast" label="AI Forecast" icon={TrendingUp} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="profiles" label="Profiles" icon={Shield} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="generate" label="Generator" icon={Printer} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="templates" label="Templates" icon={Settings} activeTab={activeTab} setActiveTab={setActiveTab} />
                    </div>
                </div>

                <div className="space-y-8">
                    {/* Forecast Tab */}
                    {activeTab === 'forecast' && (
                        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <SalesForecast />
                        </div>
                    )}
                    {/* Dashboard Tab */}
                    {activeTab === 'dashboard' && !showPrintView && dashboardData && (
                        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                            {/* Dashboard Headline Stats */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 dark:text-ink-50">
                                <MetricCard title="Active Sessions" value={dashboardData.active_count} icon={Users} color="blue" />
                                <MetricCard title="Total Vouchers" value={dashboardData.total_vouchers} icon={CreditCard} color="indigo" />
                                <MetricCard title="Data (Current Sessions)" value={`${dashboardData.total_data_mb}MB`} icon={Activity} color="emerald" />
                                <MetricCard title="System Health" value={healthStatus === 'online' ? 'Healthy' : 'Sync Error'} icon={Shield} color={healthStatus === 'online' ? 'emerald' : 'red'} />
                            </div>

                            {/* System Info Stats */}
                            {systemInfo && (
                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                    <div className="bg-white dark:bg-ink-800 p-4 rounded-lg border border-ink-200 dark:border-ink-700 shadow-sm flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <div className="p-2 rounded-lg bg-warn/10 text-warn dark:text-ink-100"><Activity size={16} /></div>
                                            <span className="text-xs font-bold text-ink-500 dark:text-ink-400">CPU Load</span>
                                        </div>
                                        <span className="font-bold text-ink-900 dark:text-ink-50">{systemInfo.cpu_load}%</span>
                                    </div>
                                    <div className="bg-white dark:bg-ink-800 p-4 rounded-lg border border-ink-200 dark:border-ink-700 shadow-sm flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <div className="p-2 rounded-lg bg-signal-600/10 text-signal-600 dark:text-signal-300"><CreditCard size={16} /></div>
                                            <span className="text-xs font-bold text-ink-500 dark:text-ink-400">Memory</span>
                                        </div>
                                        <span className="font-bold text-ink-900 dark:text-ink-50">{Math.round(systemInfo.free_memory)}MB / {Math.round(systemInfo.total_memory)}MB</span>
                                    </div>
                                    <div className="bg-white dark:bg-ink-800 p-4 rounded-lg border border-ink-200 dark:border-ink-700 shadow-sm flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <div className="p-2 rounded-lg bg-signal-600/10 text-signal-600 dark:text-signal-300"><Clock size={16} /></div>
                                            <span className="text-xs font-bold text-ink-500 dark:text-ink-400">Router Uptime</span>
                                        </div>
                                        <span className="font-bold font-mono text-ink-900 dark:text-ink-50 truncate max-w-[120px]">{systemInfo.uptime}</span>
                                    </div>
                                </div>
                            )}

                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                                {/* Profile Distribution Chart */}
                                <div className="bg-white dark:bg-ink-800 p-6 sm:p-8 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700">
                                    <h3 className="text-lg font-semibold text-ink-900 dark:text-ink-50 mb-6 tracking-tight flex items-center gap-2">
                                        <Activity size={20} className="text-signal-600 dark:text-signal-300" />
                                        Voucher Distribution
                                    </h3>
                                    <div className="h-[300px] w-full">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <PieChart>
                                                <Pie
                                                    data={dashboardData.profile_distribution}
                                                    cx="50%"
                                                    cy="50%"
                                                    innerRadius={60}
                                                    outerRadius={100}
                                                    paddingAngle={5}
                                                    dataKey="value"
                                                >
                                                    {dashboardData.profile_distribution.map((entry, index) => (
                                                        <Cell key={`cell-${index}`} fill={['#7C3E9C', '#2F7D62', '#8A6114', '#A971C4', '#9A3A22'][index % 5]} />
                                                    ))}
                                                </Pie>
                                                <RechartsTooltip />
                                                {/* Recharts colours legend labels with the slice fill, which
                                                    measures 1.89-2.64:1 for the profile names on the dark card.
                                                    The swatch already carries the colour; the label takes the
                                                    body token. */}
                                                <Legend formatter={(value) => <span className="text-ink-900 dark:text-ink-50">{value}</span>} />
                                            </PieChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>

                                {/* Quick Actions / Status */}
                                <div className="bg-white dark:bg-ink-800 p-6 sm:p-8 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700 flex flex-col justify-between">
                                    <div>
                                        <h3 className="text-lg font-semibold text-ink-900 dark:text-ink-50 mb-4 tracking-tight">Sync Status</h3>
                                        <div className="space-y-4">
                                            <div className="flex items-center justify-between p-4 bg-ink-50 dark:bg-ink-800/50 rounded-lg">
                                                <div className="flex items-center gap-3">
                                                    <div className={`p-2 rounded-lg ${healthStatus === 'online' ? 'bg-up/20 text-up' : 'bg-down/20 text-down'} dark:text-ink-100`}>
                                                        <Globe size={18} />
                                                    </div>
                                                    <span className="text-sm font-bold text-ink-900 dark:text-ink-100">Router Integration</span>
                                                </div>
                                                <span className={`text-xs font-bold ${healthStatus === 'online' ? 'text-up' : 'text-down'} dark:text-ink-100`}>{healthStatus}</span>
                                            </div>
                                            <div className="flex items-center justify-between p-4 bg-ink-50 dark:bg-ink-800/50 rounded-lg">
                                                <div className="flex items-center gap-3">
                                                    <div className="p-2 rounded-lg bg-signal-600/10 text-signal-600 dark:text-signal-300">
                                                        <Activity size={18} />
                                                    </div>
                                                    <span className="text-sm font-bold text-ink-900 dark:text-ink-100">API Latency</span>
                                                </div>
                                                <span className="text-xs font-bold text-signal-600 dark:text-signal-300">Optimal</span>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="mt-6 flex gap-3">
                                        <button onClick={() => setActiveTab('generate')} className="flex-1 bg-signal-600 text-white py-3 rounded-lg font-semibold text-xs shadow-lg">Quick Print</button>
                                        <button onClick={() => setActiveTab('active')} className="flex-1 bg-white dark:bg-ink-800 border border-ink-200 dark:border-ink-700 text-ink-500 dark:text-ink-100 py-3 rounded-lg font-semibold text-xs">View Sessions</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                    {/* Print View Overlay/Content */}
                    {showPrintView && (
                        <div className="bg-white dark:bg-ink-800 rounded-lg shadow-xl border border-signal-600/20 dark:border-signal-600/30 overflow-hidden animate-in fade-in zoom-in duration-300 mb-8 no-print">
                            <div className="bg-signal-600 p-6 flex flex-col sm:flex-row justify-between items-center text-white gap-4">
                                <div className="flex items-center gap-4">
                                    <div className="bg-white/20 p-2 rounded-lg">
                                        <Printer size={20} />
                                    </div>
                                    <div>
                                        <h3 className="font-semibold tracking-tight text-sm sm:text-base">Print Preview</h3>
                                        <p className="text-ink-100 text-xs font-medium">Ready to export {safeGeneratedBatch.length} vouchers</p>
                                        {/* Honest short-batch / failed-job disclosure (Task 5): a job can
                                            legitimately finish "complete" with fewer vouchers than requested
                                            (the router's collision budget can run out), and a "failed" job's
                                            partial vouchers are still real and sellable. Only shown when they
                                            differ -- a full/normal batch (and reprints, which clear voucherJob)
                                            render exactly as before. */}
                                        {voucherJob && (voucherJob.status === 'complete' || voucherJob.status === 'failed') && voucherJob.count > safeGeneratedBatch.length && (
                                            <p className="text-ink-50 text-xs font-bold mt-0.5">
                                                {safeGeneratedBatch.length} / {voucherJob.count} {voucherJob.status === 'failed' ? 'created before job failed' : 'complete'}
                                            </p>
                                        )}
                                    </div>
                                </div>
                                <div className="flex gap-3 w-full sm:w-auto">
                                    <button onClick={() => setShowPrintView(false)} className="flex-1 sm:flex-none px-5 py-2 hover:bg-white/10 rounded-md font-semibold text-xs transition-colors border border-white/20">Close</button>
                                    <button onClick={() => window.print()} className="flex-1 sm:flex-none bg-white text-signal-600 px-6 py-2 rounded-md font-semibold text-xs shadow-lg transition-all active:scale-95">Print Now</button>
                                </div>
                            </div>
                            <div className="p-4 sm:p-8 bg-ink-50 dark:bg-ink-900/50 grid grid-cols-2 xs:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4 overflow-y-auto max-h-[400px]">
                                {safeGeneratedBatch.map((u, i) => (
                                    <div key={i} className="bg-white dark:bg-ink-800 p-3 sm:p-4 rounded-md border border-ink-200 dark:border-ink-700 shadow-sm text-center">
                                        <div className="text-xs font-medium text-ink-500 dark:text-ink-400 mb-1">Voucher</div>
                                        <div className={`${u.username.length > 8 ? 'text-xs' : 'text-base sm:text-lg'} font-mono font-bold py-1 sm:py-2 rounded-lg border mb-1 sm:mb-2 transition-all`} style={{ color: template.color_primary, backgroundColor: template.color_primary + '15', borderColor: template.color_primary + '30' }}>{u.username}</div>
                                        <div className="text-xs text-ink-500 dark:text-ink-400 font-medium">Lim: {batchForm.time_limit || 'Unlim'}</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Hidden Print Area (Physical Print) */}
                    {/* Hidden Print Area (Physical Print) */}
                    {/* Hidden Print Area (Physical Print) */}
                    <div className="hidden print:grid print:grid-cols-5 print:gap-2 print:p-2" id="printable-area">
                        {safeGeneratedBatch.map((u, i) => (
                            <div key={i} className="voucher-card p-2 rounded-lg border border-ink-200 text-center bg-white flex flex-col justify-center min-h-[85px] overflow-hidden break-inside-avoid shadow-sm relative">
                                {/* Cut Guides */}
                                <div className="absolute top-0 left-0 w-2 h-2 border-t border-l border-ink-300"></div>
                                <div className="absolute top-0 right-0 w-2 h-2 border-t border-r border-ink-300"></div>
                                <div className="absolute bottom-0 left-0 w-2 h-2 border-b border-l border-ink-300"></div>
                                <div className="absolute bottom-0 right-0 w-2 h-2 border-b border-r border-ink-300"></div>

                                <div className="text-xs font-bold leading-none mb-2 print-header" style={{ color: template.color_primary }}>{template.header_text}</div>
                                <div className="bg-signal-600/10 border border-signal-600/20 rounded-md py-1.5 mb-1.5 w-full flex justify-center items-center print-bg print-border overflow-hidden" style={{ backgroundColor: template.color_primary + '10', borderColor: template.color_primary + '30' }}>
                                    <div className={`${u.username.length > 8 ? 'text-xs' : 'text-base'} font-bold leading-none tracking-tight print-header whitespace-nowrap overflow-hidden text-ellipsis px-1 transition-all`} style={{ color: template.color_primary }}>{u.username}</div>
                                </div>
                                <div className="text-xs font-bold text-ink-500 leading-none mb-0.5" style={{ color: template.color_primary }}>
                                    {template.footer_text}
                                </div>
                                <div className="text-xs font-bold text-ink-500 leading-none">
                                    Lim: {batchForm.time_limit || 'Unlim'}
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Active Sessions */}
                    {activeTab === 'active' && !showPrintView && (
                        <ActivePanel
                            activeSessions={activeSessions}
                            userSearch={userSearch}
                            setUserSearch={setUserSearch}
                            handleKick={handleKick}
                        />
                    )}

                    {/* Users Database */}
                    {activeTab === 'users' && (
                        <UsersPanel
                            users={users}
                            userSearch={userSearch}
                            setUserSearch={setUserSearch}
                            searchResults={searchResults}
                            isSearching={isSearching}
                            handleDelete={handleDelete}
                            handleExportCSV={handleExportCSV}
                            handleCleanupExpired={handleCleanupExpired}
                            handleBulkDeleteByComment={handleBulkDeleteByComment}
                        />
                    )}

                    {/* Batch History Tab */}
                    {activeTab === 'history' && !showPrintView && (
                        <BooksPanel
                            batchHistory={batchHistory}
                            handleReprint={handleReprint}
                            handleBulkDeleteByComment={handleBulkDeleteByComment}
                        />
                    )}

                    {/* Hotspot Logs Tab */}
                    {activeTab === 'logs' && (
                        <LogsPanel
                            logs={logs}
                            logSearch={logSearch}
                            setLogSearch={setLogSearch}
                            logFilter={logFilter}
                            setLogFilter={setLogFilter}
                            loading={loading}
                            fetchData={fetchData}
                        />
                    )}

                    {/* Sales Report Tab */}
                    {activeTab === 'reports' && reportData && (
                        <ReportsPanel
                            reportData={reportData}
                            filteredReports={filteredReports}
                            reportSearch={reportSearch}
                            setReportSearch={setReportSearch}
                            reportPeriod={reportPeriod}
                            setReportPeriod={setReportPeriod}
                            reportStartDate={reportStartDate}
                            setReportStartDate={setReportStartDate}
                            reportEndDate={reportEndDate}
                            setReportEndDate={setReportEndDate}
                            reportPage={reportPage}
                            setReportPage={setReportPage}
                            selectedDevice={selectedDevice}
                        />
                    )}


                    {/* Hotspot Profiles Tab */}
                    {activeTab === 'profiles' && (
                        <ProfilesPanel
                            profiles={profiles}
                            handleProfileDelete={handleProfileDelete}
                            setShowProfileModal={setShowProfileModal}
                            setShowPriceModal={setShowPriceModal}
                            setSelectedProfileSettings={setSelectedProfileSettings}
                        />
                    )}

                    {/* Batch Generator */}
                    {activeTab === 'generate' && (
                        <GeneratorPanel
                            batchForm={batchForm}
                            setBatchForm={setBatchForm}
                            profiles={profiles}
                            voucherJob={voucherJob}
                            loading={loading}
                            handleGenerate={handleGenerate}
                            dismissVoucherJob={dismissVoucherJob}
                        />
                    )}

                    {/* Template Editor */}
                    {activeTab === 'templates' && (
                        <div className="max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <div className="bg-white dark:bg-ink-800 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700 overflow-hidden flex flex-col md:flex-row min-h-[500px]">
                                <div className="md:w-1/3 bg-ink-900 p-8 sm:p-12 text-white flex flex-col justify-between">
                                    <div>
                                        <div className="w-12 h-12 sm:w-16 sm:h-16 bg-white/10 rounded-lg flex items-center justify-center mb-6 sm:mb-8">
                                            <Printer size={28} />
                                        </div>
                                        <h3 className="text-2xl sm:text-3xl font-semibold tracking-tight leading-tight">Print Styles</h3>
                                        <p className="text-ink-400 mt-4 font-medium text-xs sm:text-sm">Customize how your vouchers look when printed.</p>
                                    </div>
                                </div>
                                <div className="md:w-2/3 p-8 sm:p-12">
                                    <form onSubmit={saveTemplate} className="space-y-6">
                                        <div>
                                            <label className="block text-xs font-medium text-ink-500 dark:text-ink-400 mb-3">Header Text</label>
                                            <input type="text" className="w-full bg-ink-50 dark:bg-ink-800 border-none rounded-lg px-5 py-4 focus:ring-2 focus:ring-signal-500 transition-all font-bold dark:text-ink-100" value={template.header_text} onChange={e => setTemplate({ ...template, header_text: e.target.value })} />
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium text-ink-500 dark:text-ink-400 mb-3">Footer Text</label>
                                            <input type="text" className="w-full bg-ink-50 dark:bg-ink-800 border-none rounded-lg px-5 py-4 focus:ring-2 focus:ring-signal-500 transition-all font-bold dark:text-ink-100" value={template.footer_text} onChange={e => setTemplate({ ...template, footer_text: e.target.value })} />
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium text-ink-500 dark:text-ink-400 mb-3">Primary Color</label>
                                            <div className="flex gap-4 items-center">
                                                <input type="color" className="h-12 w-24 rounded-md cursor-pointer border-none p-1 bg-ink-50 dark:bg-ink-800" value={template.color_primary} onChange={e => setTemplate({ ...template, color_primary: e.target.value })} />
                                                <span className="font-mono text-ink-500 dark:text-ink-400 text-sm font-bold">{template.color_primary}</span>
                                            </div>
                                        </div>

                                        <div className="pt-6">
                                            <button type="submit" className="w-full py-4 bg-signal-600 text-white rounded-lg font-semibold text-xs sm:text-sm hover:bg-signal-700 shadow-xl transition-all active:scale-[0.98]" disabled={loading}>
                                                {loading ? 'Saving...' : 'Save Template'}
                                            </button>
                                        </div>
                                    </form>
                                    <div className="mt-8 pt-8 border-t border-ink-200 dark:border-ink-700">
                                        <h4 className="text-xs font-medium text-ink-500 dark:text-ink-400 mb-4">Preview</h4>
                                        <div className="w-48 mx-auto p-4 border border-dashed border-ink-300 dark:border-ink-700 rounded-lg text-center bg-ink-50 dark:bg-ink-800/50">
                                            <div className="text-xs font-bold leading-none mb-2" style={{ color: template.color_primary }}>{template.header_text}</div>
                                            <div className="border rounded-md py-3 mb-2 w-full flex justify-center items-center" style={{ borderColor: template.color_primary + '40', backgroundColor: template.color_primary + '15' }}>
                                                <div className="font-mono text-xl font-bold leading-none tracking-tight" style={{ color: template.color_primary }}>abc1234</div>
                                            </div>
                                            <div className="text-xs font-bold text-ink-500 dark:text-ink-400">{template.footer_text}</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div >

            {/* Profile Creation Modal */}
            < ResponsiveModal
                isOpen={showProfileModal}
                onClose={() => setShowProfileModal(false)
                }
                title="New Hotspot Profile"
                size="lg"
            >
                <div className="pb-4">
                    <p className="text-signal-600 text-xs sm:text-sm mb-6 font-medium dark:text-signal-300">Configure network limitations for this profile.</p>
                    <form onSubmit={handleProfileAdd} className="space-y-8">
                        <div>
                            <label className="block text-xs font-medium text-ink-500 dark:text-ink-400 mb-3">Profile Name</label>
                            <input
                                type="text"
                                className="placeholder:text-ink-500 dark:placeholder:text-ink-400 w-full bg-ink-50 dark:bg-ink-800 border-none rounded-lg px-5 py-4 focus:ring-2 focus:ring-signal-500 transition-all font-bold dark:text-ink-100"
                                value={profileForm.name}
                                onChange={e => setProfileForm({ ...profileForm, name: e.target.value })}
                                placeholder="e.g. ULTRA_FAST_MONTHLY"
                                required
                            />
                        </div>
                        <div className="grid grid-cols-2 gap-8">
                            <div>
                                <label className="block text-xs font-medium text-ink-500 dark:text-ink-400 mb-3">Rate Limit (Up/Down)</label>
                                <input
                                    type="text"
                                    className="placeholder:text-ink-500 dark:placeholder:text-ink-400 w-full bg-ink-50 dark:bg-ink-800 border-none rounded-lg px-5 py-4 focus:ring-2 focus:ring-signal-500 transition-all font-bold font-mono dark:text-ink-100"
                                    value={profileForm.rateLimit}
                                    onChange={e => setProfileForm({ ...profileForm, rateLimit: e.target.value })}
                                    placeholder="5M/5M"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-ink-500 dark:text-ink-400 mb-3">Shared Device Count</label>
                                <input
                                    type="number"
                                    className="w-full bg-ink-50 dark:bg-ink-800 border-none rounded-lg px-5 py-4 focus:ring-2 focus:ring-signal-500 transition-all font-bold dark:text-ink-100"
                                    value={profileForm.sharedUsers}
                                    onChange={e => setProfileForm({ ...profileForm, sharedUsers: parseInt(e.target.value) })}
                                    min="1"
                                    required
                                />
                            </div>
                        </div>
                        <div className="pt-6 flex gap-4">
                            <button type="button" onClick={() => setShowProfileModal(false)} className="flex-1 px-6 py-4 rounded-lg font-bold text-xs text-ink-500 dark:text-ink-100 hover:bg-ink-50 dark:hover:bg-ink-700 transition-colors">Abort</button>
                            <button type="submit" className="flex-1 px-6 py-4 bg-signal-600 text-white rounded-lg font-bold text-xs hover:bg-signal-700 shadow-xl transition-all active:scale-95">Create Profile</button>
                        </div>
                    </form>
                </div>
            </ResponsiveModal>

            {/* Profile Price/Currency Modal */}
            <ResponsiveModal
                isOpen={showPriceModal}
                onClose={() => setShowPriceModal(false)}
                title={`Price Settings: ${selectedProfileSettings.name}`}
            >
                <form onSubmit={handleUpdatePriceSettings} className="space-y-6">
                    <div className="space-y-4">
                        <div>
                            <label className="block text-xs font-medium text-ink-500 dark:text-ink-400 mb-2">Voucher Price</label>
                            <input
                                type="number"
                                required
                                value={selectedProfileSettings.price}
                                onChange={(e) => setSelectedProfileSettings({ ...selectedProfileSettings, price: parseFloat(e.target.value) })}
                                className="placeholder:text-ink-500 dark:placeholder:text-ink-400 w-full bg-ink-50 dark:bg-ink-800 border-none rounded-lg py-3 px-4 text-sm font-bold text-ink-900 dark:text-ink-100 outline-none focus:ring-2 focus:ring-up/20"
                                placeholder="e.g. 500"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-ink-500 dark:text-ink-400 mb-2">Currency Symbol (e.g. TZS, $, UGX)</label>
                            <input
                                type="text"
                                required
                                value={selectedProfileSettings.currency || template.default_currency || 'TZS'}
                                onChange={(e) => setSelectedProfileSettings({ ...selectedProfileSettings, currency: e.target.value.toUpperCase() })}
                                className="placeholder:text-ink-500 dark:placeholder:text-ink-400 w-full bg-ink-50 dark:bg-ink-800 border-none rounded-lg py-3 px-4 text-sm font-bold text-ink-900 dark:text-ink-100 outline-none focus:ring-2 focus:ring-up/20"
                                placeholder="TZS"
                            />
                        </div>
                    </div>
                    <div className="flex gap-4">
                        <button
                            type="button"
                            onClick={() => setShowPriceModal(false)}
                            className="flex-1 px-6 py-3 rounded-lg font-bold text-xs text-ink-500 dark:text-ink-100 bg-ink-50 dark:bg-ink-800 hover:bg-ink-100 dark:hover:bg-ink-700 transition-all active:scale-95"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={loading}
                            className="flex-1 bg-up text-white px-6 py-3 rounded-lg font-bold text-xs hover:bg-up/90 shadow-xl transition-all active:scale-95 flex items-center justify-center gap-2"
                        >
                            {loading ? <RefreshCw className="animate-spin" size={16} /> : <Settings size={16} />} Save Changes
                        </button>
                    </div>
                </form>
            </ResponsiveModal>
        </div >
    );
}


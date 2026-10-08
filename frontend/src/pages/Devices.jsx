import React, { useEffect, useState } from 'react';
import api from '../api';
import { Link } from 'react-router-dom';
import { Plus, X, Server, Activity, Wifi, Cpu, HardDrive, FileText } from 'lucide-react';
import ResponsiveTable from '../components/ResponsiveTable';
import ResponsiveModal from '../components/ResponsiveModal';
import { Button } from '../components/ui';
import OnboardWizard from '../components/OnboardWizard';
import PortalSettings from '../components/PortalSettings';

export default function Devices() {
    const [devices, setDevices] = useState([]);
    const [showAddModal, setShowAddModal] = useState(false);
    const [showWizard, setShowWizard] = useState(false);
    const [selectedDevice, setSelectedDevice] = useState(null);
    const [deviceMetrics, setDeviceMetrics] = useState({});
    const [newDevice, setNewDevice] = useState({
        name: '',
        ip_address: '',
        device_type: 'router',
        site_id: '',
        ssh_port: 22
    });

    useEffect(() => {
        fetchDevices();
    }, []);

    const fetchDevices = async () => {
        const res = await api.get('/inventory/devices');
        setDevices(res.data);
    }

    const fetchDeviceMetrics = async (deviceId) => {
        try {
            const res = await api.get(`/monitoring/metrics/latest?device_id=${deviceId}&limit=50`);
            // Process metrics to get latest of each type
            const metrics = {};
            res.data.forEach(m => {
                // If we haven't seen this type yet, or this one is newer (although api sorts by desc time)
                if (!metrics[m.metric_type]) {
                    metrics[m.metric_type] = m;
                }
            });
            setDeviceMetrics(metrics);
        } catch (e) {
            console.error("Failed to fetch metrics", e);
            setDeviceMetrics({});
        }
    };

    const handleDelete = async (deviceId) => {
        if (window.confirm("Are you sure you want to delete this device? All history will be lost.")) {
            try {
                await api.delete(`/inventory/devices/${deviceId}`);
                fetchDevices();
                if (selectedDevice && selectedDevice.id === deviceId) {
                    setSelectedDevice(null);
                }
            } catch (e) {
                console.error(e);
                // Show the real reason instead of a bare "failed". A generic
                // message hid a server-side foreign-key error for weeks.
                const status = e.response?.status;
                const detail = e.response?.data?.detail;
                const msg = status
                    ? `Failed to delete device (${status}): ${typeof detail === 'string' ? detail : 'see console'}`
                    : `Failed to delete device: ${e.message || 'the request did not reach the server (check your connection or sign in again)'}`;
                alert(msg);
            }
        }
    };

    const handleAdd = async (e) => {
        e.preventDefault();
        try {
            let siteId = newDevice.site_id;
            if (!siteId) {
                const sitesRes = await api.get('/inventory/sites');
                if (sitesRes.data.length > 0) {
                    siteId = sitesRes.data[0].id;
                } else {
                    alert("No sites found. Please create a Site first.");
                    return;
                }
            }
            await api.post('/inventory/devices', { ...newDevice, site_id: siteId });
            setShowAddModal(false);
            setNewDevice({ name: '', ip_address: '', device_type: 'router', site_id: '' });
            fetchDevices();
        } catch (err) {
            console.error(err);
            const msg = err.response?.data?.detail || 'Failed to add device.';
            alert(`Error: ${JSON.stringify(msg)}`);
        }
    };

    const openDetails = (device) => {
        setSelectedDevice(device);
        setDeviceMetrics({});
        fetchDeviceMetrics(device.id);
    };

    useEffect(() => {
        let interval;
        if (selectedDevice) {
            interval = setInterval(() => {
                fetchDeviceMetrics(selectedDevice.id);
            }, 10000);
        }
        return () => clearInterval(interval);
    }, [selectedDevice]);

    const [showEditModal, setShowEditModal] = useState(false);
    const [editDeviceData, setEditDeviceData] = useState({});

    const handleEditClick = (device) => {
        setEditDeviceData({ ...device });
        setShowEditModal(true);
    };

    const handleUpdate = async (e) => {
        e.preventDefault();
        try {
            const { id, ...data } = editDeviceData;
            // Only send relevant fields
            const updatePayload = {
                name: data.name,
                ip_address: data.ip_address,
                device_type: data.device_type,
                site_id: data.site_id,
                ssh_username: data.ssh_username,
                ssh_password: data.ssh_password,
                ssh_port: data.ssh_port,
                snmp_community: data.snmp_community,
                is_active: data.is_active
            };

            await api.put(`/inventory/devices/${id}`, updatePayload);
            setShowEditModal(false);
            fetchDevices();
            // Update selected device view if it's the one being edited
            if (selectedDevice && selectedDevice.id === id) {
                // Fetch fresh details or merge
                setSelectedDevice({ ...selectedDevice, ...updatePayload });
            }
        } catch (err) {
            console.error(err);
            const msg = err.response?.data?.detail || 'Failed to update device.';
            alert(`Error: ${JSON.stringify(msg)}`);
        }
    };

    const [showProvisionModal, setShowProvisionModal] = useState(false);
    const [provisionScript, setProvisionScript] = useState('');

    const handleProvision = async () => {
        if (!selectedDevice) return;
        try {
            const res = await api.post(`/inventory/devices/${selectedDevice.id}/provision-wireguard`);
            setProvisionScript(res.data.mikrotik_script);
            setShowProvisionModal(true);
        } catch (e) {
            console.error(e);
            alert("Provisioning failed: " + (e.response?.data?.detail || e.message));
        }
    };


    // ---- One-shot router setup script (POST provision-script) -------------
    // Every call ROTATES the router's credentials, so generating is always an
    // explicit click behind a warning, never a side effect of opening the modal.
    const [showScriptModal, setShowScriptModal] = useState(false);
    const [scriptSlug, setScriptSlug] = useState('');
    const [scriptTimezone, setScriptTimezone] = useState('Africa/Banjul');
    const [scriptBusy, setScriptBusy] = useState(false);
    const [scriptResult, setScriptResult] = useState(null);
    const [scriptError, setScriptError] = useState(null); // { kind, message }
    const [scriptNotice, setScriptNotice] = useState('');
    const [showRotateConfirm, setShowRotateConfirm] = useState(false);

    const slugify = (name) => (name || '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
        .slice(0, 32)
        .replace(/-+$/g, '');
    const SLUG_RE = /^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])$/;
    const slugValid = SLUG_RE.test(scriptSlug);

    const openScriptModal = () => {
        if (!selectedDevice) return;
        setScriptSlug(slugify(selectedDevice.name));
        setScriptResult(null);
        setScriptError(null);
        setScriptNotice('');
        setShowScriptModal(true);
    };

    // Secrets must not outlive the modal in component state.
    const closeScriptModal = () => {
        setShowScriptModal(false);
        setScriptResult(null);
        setScriptError(null);
        setScriptNotice('');
        setShowRotateConfirm(false);
    };

    // rotate=false by default: generating twice returns the SAME credentials, so a
    // script already downloaded stays valid. Rotating is an explicit, separate click,
    // because it invalidates any earlier file and that failure is invisible on the
    // router -- it pings fine and the API simply never authenticates.
    const handleGenerateScript = async (rotate = false) => {
        if (!selectedDevice || scriptBusy || !slugValid) return;
        setScriptBusy(true);
        setScriptError(null);
        setScriptNotice('');
        try {
            const res = await api.post(
                `/inventory/devices/${selectedDevice.id}/provision-script`,
                null,
                { params: { site_slug: scriptSlug, timezone: scriptTimezone, rotate } }
            );
            setScriptResult(res.data);
        } catch (e) {
            const status = e.response?.status;
            const detail = e.response?.data?.detail;
            const text = typeof detail === 'string' ? detail : (detail ? JSON.stringify(detail) : e.message);
            if (status === 409) {
                setScriptError({ kind: 'no-wireguard', message: text });
            } else if (status === 403) {
                setScriptError({ kind: 'forbidden', message: text });
            } else if (status === 400) {
                setScriptError({ kind: 'bad-input', message: text });
            } else if (status === 404) {
                setScriptError({ kind: 'not-found', message: text });
            } else {
                setScriptError({ kind: 'other', message: text });
            }
        } finally {
            setScriptBusy(false);
        }
    };

    // Explicit actions only. The script holds the router's WireGuard private
    // key, so nothing here runs on render or on selection.
    const handleCopyScript = async () => {
        try {
            await navigator.clipboard.writeText(scriptResult.script);
            setScriptNotice('Script copied to clipboard.');
        } catch (e) {
            setScriptNotice('Copy was blocked by the browser. Use Download .rsc instead.');
        }
    };

    const handleDownloadScript = () => {
        // Not text/plain: Chrome treats the blob's type as authoritative and appends
        // .txt, so the file lands as netguard-<slug>.rsc.txt and RouterOS /import
        // will not take it. Seen on a real install. octet-stream leaves the name alone.
        const blob = new Blob([scriptResult.script], { type: 'application/octet-stream' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `netguard-${scriptResult.site_slug}.rsc`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        setScriptNotice(`Saved as netguard-${scriptResult.site_slug}.rsc.`);
    };

    return (
        <div className="min-h-screen bg-ink-50 dark:bg-ink-900 pt-4 sm:pt-8 px-4 sm:px-6 lg:px-10 pb-12">
            <div className="max-w-7xl mx-auto">
                {/* Page Header */}
                <div className="mb-8 sm:mb-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
                    <div>
                        <h1 className="text-3xl sm:text-4xl font-bold text-ink-900 dark:text-ink-50 tracking-tight leading-none">
                            Device <span className="text-signal-600 dark:text-signal-300">Inventory</span>
                        </h1>
                        <p className="text-ink-500 dark:text-ink-400 mt-2 font-medium text-sm sm:text-base">Manage and monitor physical network assets.</p>
                    </div>
                    <div className="flex gap-3">
                        <button
                            onClick={() => setShowWizard(true)}
                            className="flex-1 md:flex-none bg-signal-600 text-ink-50 px-6 sm:px-8 py-3 rounded-lg font-bold text-xs sm:text-sm hover:bg-signal-700 shadow-xl transition-all active:scale-95 flex items-center justify-center gap-2"
                        >
                            <Plus size={20} /> Set up a router
                        </button>
                        <button
                            onClick={() => setShowAddModal(true)}
                            className="flex-1 md:flex-none text-ink-500 dark:text-ink-400 px-4 py-3 rounded-lg font-bold text-xs sm:text-sm hover:bg-ink-50 dark:hover:bg-ink-800 transition-all"
                        >
                            Add manually
                        </button>
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 sm:gap-10">
                    <div className={`${selectedDevice ? 'hidden lg:block' : 'block'} lg:col-span-2 space-y-8`}>
                        {/* Device List Table */}
                        <div className="bg-white dark:bg-ink-800 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700 overflow-hidden">
                            <div className="p-8 border-b border-ink-200 dark:border-ink-700">
                                <h2 className="text-xl font-bold text-ink-900 dark:text-ink-50">Manage Devices</h2>
                            </div>
                            <div className="overflow-hidden">
                                <ResponsiveTable
                                    data={devices}
                                    columns={[
                                        {
                                            header: 'Device Identity',
                                            accessor: 'name',
                                            render: (device) => (
                                                <div onClick={() => openDetails(device)} className="cursor-pointer">
                                                    <div className="font-bold text-ink-900 dark:text-ink-50 group-hover:text-signal-600 transition-colors tracking-tight text-sm">{device.name}</div>
                                                    <div className="text-xs text-ink-500 dark:text-ink-400 font-mono">{device.ip_address}</div>
                                                </div>
                                            )
                                        },
                                        {
                                            header: 'Type',
                                            accessor: 'device_type',
                                            render: (device) => (
                                                <div className="flex items-center gap-2">
                                                    <Server size={14} className="text-ink-500 dark:text-ink-400" />
                                                    <span className="text-xs font-bold text-ink-500 dark:text-ink-400">{device.device_type}</span>
                                                </div>
                                            )
                                        },
                                        {
                                            header: 'Status',
                                            accessor: 'is_active',
                                            render: (device) => (
                                                <div className="flex items-center gap-2">
                                                    <div className={`w-2 h-2 rounded-full ${device.is_active ? 'bg-up' : 'bg-down animate-pulse'}`}></div>
                                                    <span className={`text-xs font-bold  ${device.is_active ? 'text-up' : 'text-down'} dark:text-ink-100`}>
                                                        {device.is_active ? 'On' : 'Off'}
                                                    </span>
                                                </div>
                                            )
                                        },
                                        {
                                            header: 'Actions',
                                            accessor: 'actions',
                                            render: (device) => (
                                                <div className="flex justify-end gap-3 lg:opacity-0 group-hover:opacity-100 transition-opacity">
                                                    <button onClick={(e) => { e.stopPropagation(); handleEditClick(device); }} className="text-warn font-bold text-xs hover:underline dark:text-ink-100">Edit</button>
                                                    <button onClick={(e) => { e.stopPropagation(); handleDelete(device.id); }} className="text-down font-bold text-xs hover:underline dark:text-ink-100">Del</button>
                                                </div>
                                            )
                                        }
                                    ]}
                                    renderCard={(device) => (
                                        <div onClick={() => openDetails(device)} className="flex flex-col gap-3 cursor-pointer">
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-2">
                                                    <Server size={16} className="text-signal-600 dark:text-signal-300" />
                                                    <span className="font-bold text-ink-900 dark:text-ink-50 text-sm">{device.name}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <div className={`w-2 h-2 rounded-full ${device.is_active ? 'bg-up' : 'bg-down anim-pulse'}`}></div>
                                                </div>
                                            </div>
                                            <div className="flex justify-between items-center text-xs text-ink-500 dark:text-ink-400">
                                                <span className="font-mono">{device.ip_address}</span>
                                                <span className="font-bold">{device.device_type}</span>
                                            </div>
                                            <div className="flex justify-end gap-4 border-t pt-3 mt-1">
                                                <button onClick={(e) => { e.stopPropagation(); handleEditClick(device); }} className="text-warn font-bold text-xs dark:text-ink-100">Edit</button>
                                                <button onClick={(e) => { e.stopPropagation(); handleDelete(device.id); }} className="text-down font-bold text-xs dark:text-ink-100">Delete</button>
                                            </div>
                                        </div>
                                    )}
                                    emptyMessage="Your inventory is empty."
                                />
                            </div>
                        </div>
                    </div>

                    <div className={`${selectedDevice ? 'block' : 'hidden lg:block'} lg:col-span-1`}>
                        {/* Device Details Info Panel */}
                        {selectedDevice ? (
                            <div className="space-y-6 sticky top-8">
                                <div className="bg-white dark:bg-ink-800 p-6 sm:p-8 rounded-lg shadow-sm border border-ink-200 dark:border-ink-700 animate-in slide-in-from-right-10 lg:slide-in-from-right-0 duration-500">
                                    <div className="flex justify-between items-start mb-6">
                                        <div>
                                            <h3 className="text-xl sm:text-2xl font-bold text-ink-900 dark:text-ink-50 tracking-tight leading-tight">{selectedDevice.name}</h3>
                                            <p className="text-ink-500 dark:text-ink-400 font-mono text-xs sm:text-sm">{selectedDevice.ip_address}</p>
                                        </div>
                                        <div className="flex gap-2">
                                            {selectedDevice.device_type === 'router' && (
                                                <button onClick={openScriptModal} className="flex items-center gap-2 px-3 py-2 hover:bg-signal-600/10 text-signal-600 rounded-md transition-colors text-xs font-bold dark:text-signal-300" title="Generate the one-shot RouterOS setup script">
                                                    <FileText size={18} /> Get setup script
                                                </button>
                                            )}
                                            {selectedDevice.device_type === 'router' && (
                                                <button onClick={handleProvision} className="p-2 hover:bg-signal-600/10 text-signal-600 rounded-md transition-colors dark:text-signal-300" title="Setup WireGuard VPN">
                                                    <Server size={24} />
                                                </button>
                                            )}
                                            <button onClick={() => handleEditClick(selectedDevice)} className="p-2 hover:bg-warn/20 text-warn rounded-md transition-colors dark:text-ink-100" title="Edit Device">
                                                <Cpu size={24} /> {/* Reusing CPU icon as edit/settings placeholder or use specialized icon if imported */}
                                            </button>
                                            <button onClick={() => setSelectedDevice(null)} className="p-2 hover:bg-ink-100 dark:hover:bg-ink-700 rounded-md transition-colors">
                                                <X size={24} className="text-ink-500 dark:text-ink-400" />
                                            </button>
                                        </div>
                                    </div>

                                    {/* Why the tiles below say N/A.
                                        CPU, memory, uptime and linked clients all come through the
                                        RouterOS API. When that login is rejected every one of them
                                        reads N/A, which looks identical to "offline" and to "never
                                        polled" -- on a real install that cost hours, because the
                                        router pinged perfectly the whole time. A missing status
                                        metric is treated as reachable on purpose: blaming the router
                                        sends the installer after a cable instead of the password. */}
                                    {deviceMetrics.api_reachable && deviceMetrics.api_reachable.value === 0 && (
                                        deviceMetrics.status && deviceMetrics.status.value === 0 ? (
                                            <div data-testid="api-offline" role="status" className="mb-6 p-4 rounded-lg bg-ink-100 dark:bg-ink-800 text-sm text-ink-900 dark:text-ink-50">
                                                <span className="font-bold">Router not responding.</span> NetGuard cannot reach this device at all, so the readings below are unavailable. Check power and the uplink.
                                            </div>
                                        ) : (
                                            <div data-testid="api-credential-mismatch" role="status" className="mb-6 p-4 rounded-lg bg-warn/10 dark:bg-warn/20 text-sm text-ink-900 dark:text-ink-50">
                                                <span className="font-bold">The router answers, but rejects NetGuard's password.</span>{' '}
                                                That is why the readings below are N/A — they all come through the router's API.
                                                It usually means the setup script for this router was never applied, or a newer one replaced it.
                                                Use <span className="font-bold">Get setup script</span>, then import the file on the router.
                                            </div>
                                        )
                                    )}

                                    <div className="grid grid-cols-2 gap-3 sm:gap-4 mb-8">
                                        <div className="bg-ink-50 dark:bg-ink-900 p-4 rounded-lg">
                                            <div className="flex items-center gap-2 mb-1">
                                                <Cpu size={14} className="text-signal-600 dark:text-signal-300" />
                                                <span className="text-xs font-bold text-ink-500 dark:text-ink-400">CPU</span>
                                            </div>
                                            <div className="text-lg sm:text-xl font-bold text-ink-900 dark:text-ink-50">{deviceMetrics.cpu_usage ? `${deviceMetrics.cpu_usage.value.toFixed(1)}%` : 'N/A'}</div>
                                        </div>
                                        <div className="bg-ink-50 dark:bg-ink-900 p-4 rounded-lg">
                                            <div className="flex items-center gap-2 mb-1">
                                                <HardDrive size={14} className="text-signal-600 dark:text-signal-300" />
                                                <span className="text-xs font-bold text-ink-500 dark:text-ink-400">Memory</span>
                                            </div>
                                            <div className="text-lg sm:text-xl font-bold text-ink-900 dark:text-ink-50">{deviceMetrics.memory_usage ? `${deviceMetrics.memory_usage.value.toFixed(1)}%` : 'N/A'}</div>
                                        </div>
                                        <div className="bg-ink-50 dark:bg-ink-900 p-4 rounded-lg col-span-2">
                                            <div className="flex items-center gap-2 mb-1">
                                                <Activity size={14} className="text-up dark:text-ink-100" />
                                                <span className="text-xs font-bold text-ink-500 dark:text-ink-400">Uptime</span>
                                            </div>
                                            <div className="text-base sm:text-lg font-bold text-ink-900 dark:text-ink-50 leading-tight">{deviceMetrics.uptime_status?.meta_data?.uptime_str || 'N/A'}</div>
                                        </div>
                                    </div>

                                    <h4 className="text-xs font-bold text-ink-900 dark:text-ink-50 mb-4 flex items-center gap-2">
                                        <Wifi size={16} className="text-signal-600 dark:text-signal-300" />
                                        Linked Clients ({deviceMetrics.connected_clients ? parseInt(deviceMetrics.connected_clients.value) : 0})
                                    </h4>

                                    <div className="space-y-2 max-h-64 overflow-y-auto pr-2 custom-scrollbar">
                                        {deviceMetrics.connected_clients?.meta_data?.clients?.map((client, idx) => (
                                            <div key={idx} className="p-3 bg-ink-50 dark:bg-ink-900 rounded-md flex justify-between items-center text-xs sm:text-xs">
                                                <div className="font-bold text-ink-900 dark:text-ink-100 truncate max-w-[120px]">{client.hostname || 'Unknown'}</div>
                                                <div className="font-mono text-ink-500 dark:text-ink-400">{client.ip}</div>
                                            </div>
                                        )) || <div className="text-center py-6 text-ink-500 dark:text-ink-400 text-sm font-medium italic">No data.</div>}
                                    </div>
                                </div>

                                {selectedDevice.device_type === 'router' && <PortalSettings device={selectedDevice} />}
                            </div>
                        ) : (
                            <div className="bg-white dark:bg-ink-800 p-12 rounded-lg border border-dashed border-ink-200 dark:border-ink-700 text-center text-ink-500 dark:text-ink-400 flex flex-col items-center justify-center sticky top-8 h-[500px]">
                                <Server size={48} className="mb-4 opacity-20" />
                                <p className="font-bold text-lg text-ink-900 dark:text-ink-50">Select Entity</p>
                                <p className="text-sm">Click a device to view deep metrics.</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* ADD DEVICE MODAL */}
            {showWizard && <OnboardWizard onClose={() => setShowWizard(false)} onComplete={fetchDevices} />}

            <ResponsiveModal
                isOpen={showAddModal}
                onClose={() => setShowAddModal(false)}
                title="Add New Infrastructure"
                size="lg"
            >
                <div className="pb-4">
                    <p className="text-ink-500 dark:text-ink-400 text-xs sm:text-sm mb-6">Expand your NetGuard network by registering a new device.</p>
                    <form onSubmit={handleAdd} className="space-y-6">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                            <div className="sm:col-span-2">
                                <label className="block text-xs font-bold text-ink-500 mb-2 dark:text-ink-400">Device Name</label>
                                <input className="w-full bg-ink-50 dark:bg-ink-800 dark:text-ink-100 border-none rounded-lg px-5 py-3.5 focus:ring-2 focus:ring-signal-500 transition-all font-bold text-sm" value={newDevice.name} onChange={e => setNewDevice({ ...newDevice, name: e.target.value })} required placeholder="e.g. Core_Switch_01" />
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-ink-500 mb-2 dark:text-ink-400">IP Address</label>
                                <input className="w-full bg-ink-50 dark:bg-ink-800 dark:text-ink-100 border-none rounded-lg px-5 py-3.5 focus:ring-2 focus:ring-signal-500 transition-all font-mono font-bold text-sm" value={newDevice.ip_address} onChange={e => setNewDevice({ ...newDevice, ip_address: e.target.value })} required placeholder="192.168.1.1" />
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-ink-500 mb-2 dark:text-ink-400">Device Type</label>
                                <select className="w-full bg-ink-50 dark:bg-ink-800 dark:text-ink-100 border-none rounded-lg px-5 py-3.5 focus:ring-2 focus:ring-signal-500 transition-all font-bold text-sm" value={newDevice.device_type} onChange={e => setNewDevice({ ...newDevice, device_type: e.target.value })}>
                                    <option value="router">Router</option>
                                    <option value="switch">Switch</option>
                                    <option value="server">Server</option>
                                </select>
                            </div>
                            <div className="sm:col-span-2 bg-ink-50 dark:bg-ink-800/50 p-6 rounded-lg space-y-4">
                                <div className="text-xs font-bold text-signal-600 dark:text-signal-300">Control Credentials (Optional)</div>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-xs font-bold text-ink-500 mb-1 dark:text-ink-400">Username</label>
                                        <input className="w-full bg-white dark:bg-ink-800 dark:text-ink-100 border border-ink-200 dark:border-ink-700 rounded-md px-4 py-2 text-xs sm:text-sm font-bold" placeholder="admin" value={newDevice.ssh_username || ''} onChange={e => setNewDevice({ ...newDevice, ssh_username: e.target.value })} />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-ink-500 mb-1 dark:text-ink-400">Password</label>
                                        <input type="password" className="w-full bg-white dark:bg-ink-800 dark:text-ink-100 border border-ink-200 dark:border-ink-700 rounded-md px-4 py-2 text-xs sm:text-sm font-bold" placeholder="••••••••" value={newDevice.ssh_password || ''} onChange={e => setNewDevice({ ...newDevice, ssh_password: e.target.value })} />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-ink-500 mb-1 dark:text-ink-400">Port</label>
                                        <input type="number" className="w-full bg-white dark:bg-ink-800 dark:text-ink-100 border border-ink-200 dark:border-ink-700 rounded-md px-4 py-2 text-xs sm:text-sm font-bold" placeholder="22" value={newDevice.ssh_port || 22} onChange={e => setNewDevice({ ...newDevice, ssh_port: parseInt(e.target.value) })} />
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 pt-4">
                            <button type="button" onClick={() => setShowAddModal(false)} className="order-2 sm:order-1 flex-1 px-6 py-4 rounded-lg font-bold text-xs text-ink-500 hover:bg-ink-50 dark:hover:bg-ink-700 transition-colors dark:text-ink-400">Discard</button>
                            <button type="submit" className="order-1 sm:order-2 flex-1 px-6 py-4 bg-signal-600 text-ink-50 rounded-lg font-bold text-xs hover:bg-signal-700 shadow-xl transition-all active:scale-95">Register</button>
                        </div>
                    </form>
                </div>
            </ResponsiveModal>

            {/* EDIT DEVICE MODAL */}
            <ResponsiveModal
                isOpen={showEditModal}
                onClose={() => setShowEditModal(false)}
                title="Edit Device"
                size="lg"
            >
                <div className="pb-4">
                    <p className="text-ink-500 dark:text-ink-400 text-xs sm:text-sm mb-6">Update configuration for {editDeviceData.name}</p>
                    <form onSubmit={handleUpdate} className="space-y-6">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                            <div className="sm:col-span-2">
                                <label className="block text-xs font-bold text-ink-500 mb-2 dark:text-ink-400">Device Name</label>
                                <input className="w-full bg-ink-50 dark:bg-ink-800 dark:text-ink-100 border-none rounded-lg px-5 py-3.5 focus:ring-2 focus:ring-warn transition-all font-bold text-sm" value={editDeviceData.name || ''} onChange={e => setEditDeviceData({ ...editDeviceData, name: e.target.value })} required />
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-ink-500 mb-2 dark:text-ink-400">IP Address</label>
                                <input className="w-full bg-ink-50 dark:bg-ink-800 dark:text-ink-100 border-none rounded-lg px-5 py-3.5 focus:ring-2 focus:ring-warn transition-all font-mono font-bold text-sm" value={editDeviceData.ip_address || ''} onChange={e => setEditDeviceData({ ...editDeviceData, ip_address: e.target.value })} required />
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-ink-500 mb-2 dark:text-ink-400">Device Type</label>
                                <select className="w-full bg-ink-50 dark:bg-ink-800 dark:text-ink-100 border-none rounded-lg px-5 py-3.5 focus:ring-2 focus:ring-warn transition-all font-bold text-sm" value={editDeviceData.device_type} onChange={e => setEditDeviceData({ ...editDeviceData, device_type: e.target.value })}>
                                    <option value="router">Router</option>
                                    <option value="switch">Switch</option>
                                    <option value="server">Server</option>
                                </select>
                            </div>
                            <div className="sm:col-span-2 bg-ink-50 dark:bg-ink-800/50 p-6 rounded-lg space-y-4">
                                <div className="text-xs font-bold text-warn dark:text-ink-100">Control Credentials</div>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-xs font-bold text-ink-500 mb-1 dark:text-ink-400">Username</label>
                                        <input className="w-full bg-white dark:bg-ink-800 dark:text-ink-100 border border-ink-200 dark:border-ink-700 rounded-md px-4 py-2 text-xs sm:text-sm font-bold" value={editDeviceData.ssh_username || ''} onChange={e => setEditDeviceData({ ...editDeviceData, ssh_username: e.target.value })} />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-ink-500 mb-1 dark:text-ink-400">Password</label>
                                        <input type="password" className="w-full bg-white dark:bg-ink-800 dark:text-ink-100 border border-ink-200 dark:border-ink-700 rounded-md px-4 py-2 text-xs sm:text-sm font-bold" placeholder="• • • • •" value={editDeviceData.ssh_password || ''} onChange={e => setEditDeviceData({ ...editDeviceData, ssh_password: e.target.value })} />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-ink-500 mb-1 dark:text-ink-400">Port</label>
                                        <input type="number" className="w-full bg-white dark:bg-ink-800 dark:text-ink-100 border border-ink-200 dark:border-ink-700 rounded-md px-4 py-2 text-xs sm:text-sm font-bold" value={editDeviceData.ssh_port || 22} onChange={e => setEditDeviceData({ ...editDeviceData, ssh_port: parseInt(e.target.value) })} />
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 pt-4">
                            <button type="button" onClick={() => setShowEditModal(false)} className="order-2 sm:order-1 flex-1 px-6 py-4 rounded-lg font-bold text-xs text-ink-500 hover:bg-ink-50 dark:hover:bg-ink-700 transition-colors dark:text-ink-400">Discard</button>
                            <button type="submit" className="order-1 sm:order-2 flex-1 px-6 py-4 bg-warn text-ink-50 rounded-lg font-bold text-xs hover:bg-warn/90 shadow-xl transition-all active:scale-95">Save Changes</button>
                        </div>
                    </form>
                </div>
            </ResponsiveModal>

            {/* WireGuard Provisioning Modal */}
            <ResponsiveModal
                isOpen={showProvisionModal}
                onClose={() => setShowProvisionModal(false)}
                title="WireGuard Setup"
                size="lg"
            >
                <div className="pb-4">
                    <p className="text-up text-xs sm:text-sm mb-4 font-bold dark:text-ink-100">Config for {selectedDevice?.name}</p>
                    <p className="text-sm text-ink-500 mb-4 dark:text-ink-400">Copy and paste this script into your Mikrotik Terminal:</p>
                    <pre className="bg-ink-900 text-up p-4 rounded-md text-xs sm:text-sm font-mono overflow-auto whitespace-pre-wrap max-h-[300px] border border-ink-700 dark:text-ink-100">
                        {provisionScript}
                    </pre>
                    <div className="mt-6 flex justify-end">
                        <button onClick={() => { navigator.clipboard.writeText(provisionScript); alert('Copied to clipboard!'); }} className="bg-up text-ink-50 px-6 py-3 rounded-md font-bold text-sm hover:bg-up/90 transition-colors shadow-lg">
                            Copy Script
                        </button>
                    </div>
                </div>
            </ResponsiveModal>

            {/* Router setup script modal */}
            <ResponsiveModal
                isOpen={showScriptModal}
                onClose={closeScriptModal}
                title="Router Setup Script"
                size="xl"
            >
                <div className="pb-4 space-y-4">
                    <p className="text-ink-900 text-xs sm:text-sm font-bold dark:text-ink-50">Setup for {selectedDevice?.name}</p>

                    {!scriptResult && (
                        <>
                            <div className="bg-warn/10 dark:bg-warn/20 p-4 rounded-md text-sm text-ink-900 dark:text-ink-50" role="note">
                                <p className="font-bold mb-1">Generating a script replaces this router's passwords.</p>
                                <p>
                                    Every time you generate, NetGuard creates new API and admin passwords. A script you generated
                                    earlier, or already pasted into the router, will no longer match what NetGuard holds. Only generate
                                    again if you are about to install the new script.
                                </p>
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div>
                                    <label htmlFor="script-site-slug" className="block text-xs font-bold text-ink-500 mb-1 dark:text-ink-400">Site name on the router</label>
                                    <input
                                        id="script-site-slug"
                                        className="w-full bg-ink-50 dark:bg-ink-800 dark:text-ink-100 border border-ink-200 dark:border-ink-700 rounded-md px-4 py-2 text-sm font-mono"
                                        value={scriptSlug}
                                        onChange={e => setScriptSlug(e.target.value.toLowerCase())}
                                        maxLength={32}
                                        autoComplete="off"
                                    />
                                    <p className="text-xs text-ink-500 dark:text-ink-400 mt-1">2 to 32 characters: lowercase letters, digits and hyphens, starting and ending with a letter or digit.</p>
                                </div>
                                <div>
                                    <label htmlFor="script-timezone" className="block text-xs font-bold text-ink-500 mb-1 dark:text-ink-400">Timezone</label>
                                    <input
                                        id="script-timezone"
                                        className="w-full bg-ink-50 dark:bg-ink-800 dark:text-ink-100 border border-ink-200 dark:border-ink-700 rounded-md px-4 py-2 text-sm font-mono"
                                        value={scriptTimezone}
                                        onChange={e => setScriptTimezone(e.target.value)}
                                        autoComplete="off"
                                    />
                                </div>
                            </div>

                            {scriptError && (
                                <div className="bg-down/10 dark:bg-down/20 p-4 rounded-md text-sm text-ink-900 dark:text-ink-50" role="alert">
                                    {scriptError.kind === 'no-wireguard' && (
                                        <>
                                            <p className="font-bold mb-1">Provision WireGuard for this router first.</p>
                                            <p>
                                                The setup script needs this router's WireGuard tunnel, and none exists yet. Close this window,
                                                use the Setup WireGuard VPN button (the server icon) on this panel, then come back and get the setup script.
                                            </p>
                                        </>
                                    )}
                                    {scriptError.kind === 'forbidden' && (
                                        <>
                                            <p className="font-bold mb-1">Your account cannot generate setup scripts.</p>
                                            <p>
                                                Generating a script changes the router's passwords, so it is limited to organisation admins and
                                                super admins. Ask an admin on your organisation to do this for you.
                                            </p>
                                        </>
                                    )}
                                    {scriptError.kind === 'bad-input' && (
                                        <>
                                            <p className="font-bold mb-1">The site name or timezone was not accepted.</p>
                                            <p>{scriptError.message}</p>
                                        </>
                                    )}
                                    {scriptError.kind === 'not-found' && (
                                        <>
                                            <p className="font-bold mb-1">This device no longer exists.</p>
                                            <p>Close this window and refresh the device list.</p>
                                        </>
                                    )}
                                    {scriptError.kind === 'other' && (
                                        <>
                                            <p className="font-bold mb-1">The setup script could not be generated.</p>
                                            <p>{scriptError.message}</p>
                                        </>
                                    )}
                                </div>
                            )}

                            {/* Arrow functions on purpose: onClick passes the click EVENT as the
                                first argument, so `onClick={handleGenerateScript}` would hand a
                                truthy event in as `rotate` and silently rotate every time -- the
                                exact bug this flow exists to remove. */}
                            {/* The ordinary path is ONE primary button. Rotation is a text link
                                behind a confirmation, because it was clicked three times in a row
                                by someone who thought it was how you get a script -- each click
                                invalidating the file from the one before. The confirmation used to
                                be on the safe action and the destructive one had none. */}
                            <div className="flex justify-end">
                                <Button onClick={() => handleGenerateScript(false)} disabled={scriptBusy || !slugValid}>
                                    {scriptBusy ? 'Generating...' : 'Get script'}
                                </Button>
                            </div>
                            <p className="text-xs text-ink-500 dark:text-ink-400 text-right">
                                This reuses the password NetGuard already holds, so a file you downloaded earlier still works,
                                and the router&rsquo;s <span className="font-mono">admin</span> password is never touched &mdash; that is set once, on the first install.
                            </p>

                            {!showRotateConfirm ? (
                                <p className="text-xs text-ink-500 dark:text-ink-400 text-right">
                                    <button
                                        type="button"
                                        onClick={() => setShowRotateConfirm(true)}
                                        disabled={scriptBusy}
                                        className="underline hover:text-warn disabled:opacity-50"
                                    >
                                        Replace the password instead
                                    </button>
                                </p>
                            ) : (
                                <div data-testid="rotate-confirm" role="alert" className="p-4 rounded-md bg-warn/10 dark:bg-warn/20 text-sm text-ink-900 dark:text-ink-50">
                                    <p className="font-bold mb-1">Replace this router&rsquo;s API password?</p>
                                    <p className="mb-3">
                                        Any script you downloaded earlier will stop working on this router, and you will have to
                                        import the new one before NetGuard can reach it again. You only need this if you think the
                                        current password has leaked.
                                    </p>
                                    <div className="flex flex-col sm:flex-row justify-end gap-3">
                                        <Button variant="secondary" onClick={() => setShowRotateConfirm(false)} disabled={scriptBusy}>
                                            Cancel
                                        </Button>
                                        <Button onClick={() => { setShowRotateConfirm(false); handleGenerateScript(true); }} disabled={scriptBusy || !slugValid}>
                                            {scriptBusy ? 'Working...' : 'Yes, replace it'}
                                        </Button>
                                    </div>
                                </div>
                            )}
                        </>
                    )}

                    {scriptResult && (
                        <>
                            <div className="bg-warn/10 dark:bg-warn/20 p-4 rounded-md text-sm text-ink-900 dark:text-ink-50" role="alert">
                                <p className="font-bold mb-1">Save both passwords now. They are shown only once.</p>
                                <p>
                                    The script does not print them, NetGuard cannot show the admin password again, and closing this
                                    window discards both. Generating again creates new passwords and breaks any router already set up from this script.
                                </p>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div className="bg-ink-50 dark:bg-ink-900 p-4 rounded-md">
                                    <div className="text-xs font-bold text-ink-500 dark:text-ink-400 mb-1">Recovery login (netguard-recovery)</div>
                                    <div className="text-xs text-ink-500 dark:text-ink-400 mb-2">A full-access break-glass account, for WinBox, WebFig and the console.</div>
                                    {/* The recovery password is always returned; the script APPLIES it
                                        only to a new or factory-reset router (gated on the router's own
                                        state). The router's own `admin` password is never set by the
                                        script -- the operator owns it. */}
                                    <code data-testid="recovery-password" className="block font-mono text-sm text-ink-900 dark:text-ink-50 break-all select-all">{scriptResult.recovery_password}</code>
                                    <div className="text-xs text-ink-500 dark:text-ink-400 mt-2">
                                        Set <span className="font-bold">only if this router is new or factory-reset</span>, and shown once. Save it: NetGuard never stores it, and it is your way back in if the admin password is lost.
                                    </div>
                                    <div className="text-xs text-warn dark:text-warn mt-2 font-bold">
                                        The router&rsquo;s own <span className="font-mono">admin</span> password is never set by NetGuard. A new router starts with a BLANK admin password &mdash; set one in WinBox right after importing.
                                    </div>
                                </div>
                                <div className="bg-ink-50 dark:bg-ink-900 p-4 rounded-md">
                                    <div className="text-xs font-bold text-ink-500 dark:text-ink-400 mb-1">NetGuard API password</div>
                                    <div className="text-xs text-ink-500 dark:text-ink-400 mb-2">
                                        For user <span className="font-mono">{scriptResult.api_username}</span>. NetGuard already stores this one; keep a copy for recovery.
                                    </div>
                                    <code data-testid="api-password" className="block font-mono text-sm text-ink-900 dark:text-ink-50 break-all select-all">{scriptResult.api_password}</code>
                                </div>
                            </div>

                            {scriptResult.warnings?.length > 0 && (
                                <ul className="list-disc pl-5 space-y-1 text-sm text-ink-900 dark:text-ink-50">
                                    {scriptResult.warnings.map((w, i) => <li key={i}>{w}</li>)}
                                </ul>
                            )}

                            <div className="text-sm text-ink-700 dark:text-ink-200 space-y-2">
                                <p className="font-bold text-ink-900 dark:text-ink-50">How to install</p>
                                <p>
                                    <span className="font-bold">Quickest:</span> click <span className="font-bold">Copy script</span>, open the router&rsquo;s
                                    WinBox or WebFig terminal, and paste the whole thing in one go. The entire script is one block, so a single paste
                                    applies all of it &mdash; or none of it if anything is wrong, so you never get a half-configured router.
                                </p>
                                <p>
                                    <span className="font-bold">For a remote or unattended install</span>, download the file, upload it (WinBox Files or WebFig Files),
                                    and run <span className="font-mono">/import file-name=netguard-{scriptResult.site_slug}.rsc</span>. Same result;
                                    an import isn&rsquo;t limited by paste size and reports a bad line more cleanly, so it&rsquo;s the safer choice when you can&rsquo;t watch it run.
                                </p>
                                <p>
                                    Your connection will drop partway through. The script moves ports ether2 to ether8 onto a new bridge, which ends
                                    the session you installed from. This is expected and the router keeps running the script. Afterwards the router
                                    answers on a new address in 10.15.x.
                                </p>
                            </div>

                            <pre className="bg-ink-900 text-ink-100 p-4 rounded-md text-xs sm:text-sm font-mono overflow-auto whitespace-pre-wrap max-h-[300px] border border-ink-700" data-testid="script-body">
                                {scriptResult.script}
                            </pre>
                            <p className="text-xs text-ink-500 dark:text-ink-400">This script contains the router's WireGuard private key. Treat it like a password.</p>

                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                                <span className="text-xs text-ink-500 dark:text-ink-400" role="status">{scriptNotice}</span>
                                <div className="flex gap-3">
                                    <Button variant="outline" onClick={handleDownloadScript}>Download .rsc</Button>
                                    <Button onClick={handleCopyScript}>Copy script</Button>
                                </div>
                            </div>
                        </>
                    )}
                </div>
            </ResponsiveModal>
        </div>
    );
}

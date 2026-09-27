import React, { useEffect, useState } from 'react';
import api from '../api';
import { Link } from 'react-router-dom';
import { Plus, X, Server, Activity, Wifi, Cpu, HardDrive } from 'lucide-react';
import ResponsiveTable from '../components/ResponsiveTable';
import ResponsiveModal from '../components/ResponsiveModal';

export default function Devices() {
    const [devices, setDevices] = useState([]);
    const [showAddModal, setShowAddModal] = useState(false);
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
                alert("Failed to delete device.");
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
                            onClick={() => setShowAddModal(true)}
                            className="flex-1 md:flex-none bg-signal-600 text-ink-50 px-6 sm:px-8 py-3 rounded-lg font-bold text-xs sm:text-sm hover:bg-signal-700 shadow-xl transition-all active:scale-95 flex items-center justify-center gap-2"
                        >
                            <Plus size={20} /> Add Device
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
        </div>
    );
}

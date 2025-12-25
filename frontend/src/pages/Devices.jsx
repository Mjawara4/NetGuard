import React, { useEffect, useState } from 'react';
import api from '../api';
import { Link } from 'react-router-dom';
import { Plus, X, Server, Activity, Wifi, Cpu, HardDrive } from 'lucide-react';

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
            }, 3000);
        }
        return () => clearInterval(interval);
    }, [selectedDevice]);

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
        <div className="min-h-screen bg-gray-50 pt-4 sm:pt-8 px-4 sm:px-6 lg:px-10 pb-12">
            <div className="max-w-7xl mx-auto">
                {/* Page Header */}
                <div className="mb-8 sm:mb-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
                    <div>
                        <h1 className="text-3xl sm:text-4xl font-black text-gray-900 tracking-tight leading-none">
                            Device <span className="text-blue-600">Inventory</span>
                        </h1>
                        <p className="text-gray-500 mt-2 font-medium text-sm sm:text-base">Manage and monitor physical network assets.</p>
                    </div>
                    <div className="flex gap-3">
                        <button
                            onClick={() => setShowAddModal(true)}
                            className="flex-1 md:flex-none bg-blue-600 text-white px-6 sm:px-8 py-3 rounded-2xl font-black text-xs sm:text-sm uppercase tracking-widest hover:bg-blue-700 shadow-xl shadow-blue-100 transition-all active:scale-95 flex items-center justify-center gap-2"
                        >
                            <Plus size={20} /> Add Device
                        </button>
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 sm:gap-10">
                    <div className={`${selectedDevice ? 'hidden lg:block' : 'block'} lg:col-span-2 space-y-8`}>
                        {/* Device List Table */}
                        <div className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
                            <div className="p-8 border-b border-gray-50">
                                <h2 className="text-xl font-black text-gray-900">Manage Devices</h2>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="min-w-full">
                                    <thead className="bg-gray-50 text-[10px] font-black text-gray-400 uppercase tracking-widest text-left">
                                        <tr>
                                            <th className="px-6 sm:px-8 py-4">Device Identity</th>
                                            <th className="px-6 sm:px-8 py-4 hidden sm:table-cell">Type</th>
                                            <th className="px-6 sm:px-8 py-4">Status</th>
                                            <th className="px-6 sm:px-8 py-4 text-right">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-50">
                                        {devices.map((device) => (
                                            <tr key={device.id} className={`hover:bg-blue-50 transition-colors cursor-pointer group ${selectedDevice?.id === device.id ? 'bg-blue-50' : ''}`} onClick={() => openDetails(device)}>
                                                <td className="px-6 sm:px-8 py-5">
                                                    <div className="font-bold text-gray-900 group-hover:text-blue-600 transition-colors uppercase tracking-tight text-sm">{device.name}</div>
                                                    <div className="text-[10px] text-gray-400 font-mono">{device.ip_address}</div>
                                                </td>
                                                <td className="px-6 sm:px-8 py-5 hidden sm:table-cell">
                                                    <div className="flex items-center gap-2">
                                                        <Server size={14} className="text-gray-400" />
                                                        <span className="text-[10px] font-black text-gray-500 uppercase">{device.device_type}</span>
                                                    </div>
                                                </td>
                                                <td className="px-6 sm:px-8 py-5">
                                                    <div className="flex items-center gap-2">
                                                        <div className={`w-2 h-2 rounded-full ${device.is_active ? 'bg-emerald-500' : 'bg-red-500 anim-pulse'}`}></div>
                                                        <span className={`text-[10px] font-black uppercase ${device.is_active ? 'text-emerald-600' : 'text-red-600'}`}>
                                                            {device.is_active ? 'On' : 'Off'}
                                                        </span>
                                                    </div>
                                                </td>
                                                <td className="px-6 sm:px-8 py-5 text-right">
                                                    <div className="flex justify-end gap-3 lg:opacity-0 group-hover:opacity-100 transition-opacity">
                                                        <button onClick={(e) => { e.stopPropagation(); openDetails(device); }} className="text-blue-600 font-bold text-[10px] uppercase hover:underline">View</button>
                                                        <button onClick={(e) => { e.stopPropagation(); handleDelete(device.id); }} className="text-red-500 font-bold text-[10px] uppercase hover:underline">Del</button>
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                        {devices.length === 0 && (
                                            <tr>
                                                <td colSpan="4" className="px-8 py-12 text-center text-gray-400 font-medium italic text-sm">Your inventory is empty.</td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>

                    <div className={`${selectedDevice ? 'block' : 'hidden lg:block'} lg:col-span-1`}>
                        {/* Device Details Info Panel */}
                        {selectedDevice ? (
                            <div className="space-y-6 sticky top-8">
                                <div className="bg-white p-6 sm:p-8 rounded-3xl shadow-sm border border-gray-100 animate-in slide-in-from-right-10 lg:slide-in-from-right-0 duration-500">
                                    <div className="flex justify-between items-start mb-6">
                                        <div>
                                            <h3 className="text-xl sm:text-2xl font-black text-gray-900 tracking-tight uppercase leading-tight">{selectedDevice.name}</h3>
                                            <p className="text-gray-400 font-mono text-xs sm:text-sm">{selectedDevice.ip_address}</p>
                                        </div>
                                        <div className="flex gap-2">
                                            {selectedDevice.device_type === 'router' && (
                                                <button onClick={handleProvision} className="p-2 hover:bg-blue-50 text-blue-600 rounded-xl transition-colors" title="Setup WireGuard VPN">
                                                    <Server size={24} />
                                                </button>
                                            )}
                                            <button onClick={() => setSelectedDevice(null)} className="p-2 hover:bg-gray-100 rounded-xl transition-colors">
                                                <X size={24} className="text-gray-400" />
                                            </button>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-3 sm:gap-4 mb-8">
                                        <div className="bg-gray-50 p-4 rounded-2xl">
                                            <div className="flex items-center gap-2 mb-1">
                                                <Cpu size={14} className="text-blue-500" />
                                                <span className="text-[10px] font-black text-gray-400 uppercase">CPU</span>
                                            </div>
                                            <div className="text-lg sm:text-xl font-black text-gray-900">{deviceMetrics.cpu_usage ? `${deviceMetrics.cpu_usage.value.toFixed(1)}%` : 'N/A'}</div>
                                        </div>
                                        <div className="bg-gray-50 p-4 rounded-2xl">
                                            <div className="flex items-center gap-2 mb-1">
                                                <HardDrive size={14} className="text-purple-500" />
                                                <span className="text-[10px] font-black text-gray-400 uppercase">Memory</span>
                                            </div>
                                            <div className="text-lg sm:text-xl font-black text-gray-900">{deviceMetrics.memory_usage ? `${deviceMetrics.memory_usage.value.toFixed(1)}%` : 'N/A'}</div>
                                        </div>
                                        <div className="bg-gray-50 p-4 rounded-2xl col-span-2">
                                            <div className="flex items-center gap-2 mb-1">
                                                <Activity size={14} className="text-emerald-500" />
                                                <span className="text-[10px] font-black text-gray-400 uppercase">Uptime</span>
                                            </div>
                                            <div className="text-base sm:text-lg font-black text-gray-900 leading-tight">{deviceMetrics.uptime_status?.meta_data?.uptime_str || 'N/A'}</div>
                                        </div>
                                    </div>

                                    <h4 className="text-[10px] font-black text-gray-900 uppercase tracking-widest mb-4 flex items-center gap-2">
                                        <Wifi size={16} className="text-blue-500" />
                                        Linked Clients ({deviceMetrics.connected_clients ? parseInt(deviceMetrics.connected_clients.value) : 0})
                                    </h4>

                                    <div className="space-y-2 max-h-64 overflow-y-auto pr-2 custom-scrollbar">
                                        {deviceMetrics.connected_clients?.meta_data?.clients?.map((client, idx) => (
                                            <div key={idx} className="p-3 bg-gray-50 rounded-xl flex justify-between items-center text-[10px] sm:text-xs">
                                                <div className="font-bold text-gray-700 truncate max-w-[120px]">{client.hostname || 'Unknown'}</div>
                                                <div className="font-mono text-gray-400">{client.ip}</div>
                                            </div>
                                        )) || <div className="text-center py-6 text-gray-400 text-sm font-medium italic">No data.</div>}
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="bg-white p-12 rounded-3xl border border-dashed border-gray-200 text-center text-gray-400 flex flex-col items-center justify-center sticky top-8 h-[500px]">
                                <Server size={48} className="mb-4 opacity-20" />
                                <p className="font-bold text-lg text-gray-900">Select Entity</p>
                                <p className="text-sm">Click a device to view deep metrics.</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* ADD DEVICE MODAL - Redesigned */}
            {showAddModal && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 sm:p-6 z-[60] animate-in fade-in duration-300">
                    <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg overflow-hidden animate-in zoom-in-95 duration-300 max-h-[90vh] flex flex-col">
                        <div className="bg-blue-600 p-6 sm:p-8 text-white relative flex-shrink-0">
                            <h3 className="text-xl sm:text-2xl font-black uppercase tracking-tight pr-8">Add New Infrastructure</h3>
                            <p className="text-blue-100 mt-1 font-medium text-xs sm:text-sm">Expand your NetGuard network.</p>
                            <button onClick={() => setShowAddModal(false)} className="absolute top-6 right-6 text-blue-200 hover:text-white transition-colors p-2">
                                <X size={24} />
                            </button>
                        </div>
                        <form onSubmit={handleAdd} className="p-6 sm:p-8 space-y-6 overflow-y-auto">
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                                <div className="sm:col-span-2">
                                    <label className="block text-[10px] font-black text-gray-400 uppercase mb-2 tracking-widest">Device Name</label>
                                    <input className="w-full bg-gray-50 border-none rounded-2xl px-5 py-3.5 focus:ring-2 focus:ring-blue-500 transition-all font-bold text-sm" value={newDevice.name} onChange={e => setNewDevice({ ...newDevice, name: e.target.value })} required placeholder="e.g. Core_Switch_01" />
                                </div>
                                <div>
                                    <label className="block text-[10px] font-black text-gray-400 uppercase mb-2 tracking-widest">IP Address</label>
                                    <input className="w-full bg-gray-50 border-none rounded-2xl px-5 py-3.5 focus:ring-2 focus:ring-blue-500 transition-all font-mono font-bold text-sm" value={newDevice.ip_address} onChange={e => setNewDevice({ ...newDevice, ip_address: e.target.value })} required placeholder="192.168.1.1" />
                                </div>
                                <div>
                                    <label className="block text-[10px] font-black text-gray-400 uppercase mb-2 tracking-widest">Device Type</label>
                                    <select className="w-full bg-gray-50 border-none rounded-2xl px-5 py-3.5 focus:ring-2 focus:ring-blue-500 transition-all font-bold text-sm" value={newDevice.device_type} onChange={e => setNewDevice({ ...newDevice, device_type: e.target.value })}>
                                        <option value="router">Router</option>
                                        <option value="switch">Switch</option>
                                        <option value="server">Server</option>
                                    </select>
                                </div>
                                <div className="sm:col-span-2 bg-gray-50 p-6 rounded-2xl space-y-4">
                                    <div className="text-[10px] font-black text-blue-600 uppercase tracking-widest">Control Credentials (Optional)</div>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        <div>
                                            <label className="block text-[10px] font-bold text-gray-400 uppercase mb-1">Username</label>
                                            <input className="w-full bg-white border border-gray-100 rounded-xl px-4 py-2 text-xs sm:text-sm font-bold" placeholder="admin" value={newDevice.ssh_username || ''} onChange={e => setNewDevice({ ...newDevice, ssh_username: e.target.value })} />
                                        </div>
                                        <div>
                                            <label className="block text-[10px] font-bold text-gray-400 uppercase mb-1">Password</label>
                                            <input type="password" className="w-full bg-white border border-gray-100 rounded-xl px-4 py-2 text-xs sm:text-sm font-bold" placeholder="••••••••" value={newDevice.ssh_password || ''} onChange={e => setNewDevice({ ...newDevice, ssh_password: e.target.value })} />
                                        </div>
                                        <div>
                                            <label className="block text-[10px] font-bold text-gray-400 uppercase mb-1">Port</label>
                                            <input type="number" className="w-full bg-white border border-gray-100 rounded-xl px-4 py-2 text-xs sm:text-sm font-bold" placeholder="22" value={newDevice.ssh_port || 22} onChange={e => setNewDevice({ ...newDevice, ssh_port: parseInt(e.target.value) })} />
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 pt-4">
                                <button type="button" onClick={() => setShowAddModal(false)} className="order-2 sm:order-1 flex-1 px-6 py-4 rounded-2xl font-black text-xs uppercase tracking-widest text-gray-400 hover:bg-gray-50 transition-colors">Discard</button>
                                <button type="submit" className="order-1 sm:order-2 flex-1 px-6 py-4 bg-blue-600 text-white rounded-2xl font-black text-xs uppercase tracking-widest hover:bg-blue-700 shadow-xl shadow-blue-100 transition-all active:scale-95">Register</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* WireGuard Provisioning Modal */}
            {showProvisionModal && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 sm:p-6 z-[60] animate-in fade-in duration-300">
                    <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl overflow-hidden animate-in zoom-in-95 duration-300 max-h-[90vh] flex flex-col">
                        <div className="bg-emerald-600 p-6 sm:p-8 text-white relative flex-shrink-0">
                            <h3 className="text-xl sm:text-2xl font-black uppercase tracking-tight pr-8">WireGuard Setup</h3>
                            <p className="text-emerald-100 mt-1 font-medium text-xs sm:text-sm">Config for {selectedDevice?.name}</p>
                            <button onClick={() => setShowProvisionModal(false)} className="absolute top-6 right-6 text-emerald-200 hover:text-white transition-colors p-2">
                                <X size={24} />
                            </button>
                        </div>
                        <div className="p-6 sm:p-8 overflow-y-auto">
                            <p className="text-sm text-gray-600 mb-4 font-bold">Copy and paste this script into your Mikrotik Terminal:</p>
                            <pre className="bg-gray-900 text-green-400 p-4 rounded-xl text-xs sm:text-sm font-mono overflow-auto whitespace-pre-wrap max-h-[300px] border border-gray-800">
                                {provisionScript}
                            </pre>
                            <div className="mt-6 flex justify-end">
                                <button onClick={() => { navigator.clipboard.writeText(provisionScript); alert('Copied to clipboard!'); }} className="bg-emerald-600 text-white px-6 py-3 rounded-xl font-black text-sm uppercase tracking-widest hover:bg-emerald-700 transition-colors shadow-lg shadow-emerald-100">
                                    Copy Script
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

import React, { useEffect, useState } from 'react';
import api from '../api';
import { Link } from 'react-router-dom';
import { Plus, MapPin, Activity } from 'lucide-react';
import ResponsiveModal from '../components/ResponsiveModal';

export default function Sites() {
    const [sites, setSites] = useState([]);
    const [showModal, setShowModal] = useState(false);
    const [newSite, setNewSite] = useState({
        name: '',
        location: '',
        auto_fix_enabled: false
    }); // Will need to fetch from user or hardcode for MVP

    useEffect(() => {
        fetchSites();
    }, []);

    const fetchSites = async () => {
        try {
            const res = await api.get('/inventory/sites');
            setSites(res.data);
            // Assuming for MVP we just use the first site's org ID for new sites, 
            // or we might need an endpoint to get current user's org.
            // For now, let's rely on the backend to handle organization assignment or 
            // we default to the first site's org if available.
        } catch (err) {
            console.error(err);
        }
    }

    const handleAdd = async (e) => {
        e.preventDefault();
        try {
            // Backend handles organization_id from current user
            // Ensure we don't send empty strings for optional fields or invalid UUIDs
            const payload = {
                name: newSite.name,
                location: newSite.location,
                auto_fix_enabled: newSite.auto_fix_enabled
            };

            await api.post('/inventory/sites', payload);
            setShowModal(false);
            setNewSite({ name: '', location: '', auto_fix_enabled: false });
            fetchSites();
        } catch (err) {
            console.error(err);
            let errorMessage = 'Failed to add site.';
            if (err.response?.data?.detail) {
                errorMessage += ' ' + (typeof err.response.data.detail === 'object'
                    ? JSON.stringify(err.response.data.detail)
                    : err.response.data.detail);
            } else if (err.message) {
                errorMessage += ' ' + err.message;
            }
            alert(errorMessage);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 pt-4 sm:pt-8 px-4 sm:px-6 lg:px-10 pb-12">
            <div className="max-w-7xl mx-auto">
                {/* Page Header */}
                <div className="mb-8 sm:mb-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
                    <div>
                        <h1 className="text-3xl sm:text-4xl font-black text-gray-900 tracking-tight leading-none">
                            Operational <span className="text-blue-600">Sites</span>
                        </h1>
                        <p className="text-gray-500 mt-2 font-medium text-sm sm:text-base">Network locations and logical segmentation.</p>
                    </div>
                    <button
                        onClick={() => setShowModal(true)}
                        className="bg-blue-600 text-white px-6 sm:px-8 py-3 rounded-2xl font-black text-xs sm:text-sm uppercase tracking-widest hover:bg-blue-700 shadow-xl shadow-blue-100 transition-all active:scale-95 flex items-center justify-center gap-2 w-full md:w-auto"
                    >
                        <Plus size={20} /> Add Site
                    </button>
                </div>

                <ResponsiveModal
                    isOpen={showModal}
                    onClose={() => setShowModal(false)}
                    title="New Site"
                    size="md"
                >
                    <div className="pb-4">
                        <p className="text-blue-600 text-xs sm:text-sm mb-6 font-medium">Define a new operational area.</p>
                        <form onSubmit={handleAdd} className="space-y-6">
                            <div>
                                <label className="block text-[10px] font-black text-gray-400 uppercase mb-2 tracking-widest">Site Name</label>
                                <input className="w-full bg-gray-50 border-none rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 transition-all font-bold text-sm" value={newSite.name} onChange={e => setNewSite({ ...newSite, name: e.target.value })} required />
                            </div>
                            <div>
                                <label className="block text-[10px] font-black text-gray-400 uppercase mb-2 tracking-widest">Physical Location</label>
                                <input className="w-full bg-gray-50 border-none rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 transition-all font-bold text-sm" value={newSite.location} onChange={e => setNewSite({ ...newSite, location: e.target.value })} />
                            </div>
                            <div className="flex items-center gap-3">
                                <input type="checkbox" className="w-5 h-5 rounded-lg border-gray-200 text-blue-600 focus:ring-blue-500" checked={newSite.auto_fix_enabled} onChange={e => setNewSite({ ...newSite, auto_fix_enabled: e.target.checked })} />
                                <label className="text-[10px] font-black text-gray-600 uppercase tracking-widest">Enable Auto-Fix</label>
                            </div>
                            <div className="flex flex-col sm:flex-row gap-3 pt-2">
                                <button type="button" onClick={() => setShowModal(false)} className="order-2 sm:order-1 flex-1 px-4 py-3 rounded-xl font-black text-xs uppercase text-gray-400 hover:bg-gray-50 transition-colors">Discard</button>
                                <button type="submit" className="order-1 sm:order-2 flex-1 px-4 py-3 bg-blue-600 text-white rounded-xl font-black text-xs uppercase shadow-lg shadow-blue-100">Save Site</button>
                            </div>
                        </form>
                    </div>
                </ResponsiveModal>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
                    {sites.map((site) => (
                        <div key={site.id} className="bg-white p-6 sm:p-8 rounded-3xl shadow-sm border border-gray-100 hover:shadow-xl hover:-translate-y-1 transition-all duration-300 group">
                            <div className="flex justify-between items-start mb-6">
                                <div className="p-4 bg-blue-50 text-blue-600 rounded-2xl group-hover:bg-blue-600 group-hover:text-white transition-colors">
                                    <MapPin size={24} />
                                </div>
                                <div className={`px-3 py-1 rounded-lg text-[10px] font-black uppercase ${site.auto_fix_enabled ? 'bg-emerald-100 text-emerald-600' : 'bg-gray-100 text-gray-400'}`}>
                                    AF {site.auto_fix_enabled ? 'ON' : 'OFF'}
                                </div>
                            </div>

                            <h3 className="text-xl sm:text-2xl font-black text-gray-900 tracking-tight mb-2 truncate">{site.name}</h3>
                            <p className="text-gray-400 text-xs sm:text-sm font-medium mb-8 truncate">{site.location || 'Remote Location'}</p>

                            <div className="pt-6 border-t border-gray-50">
                                <Link to="/devices" className="text-[10px] font-black text-blue-600 uppercase tracking-widest flex items-center gap-2 group/link">
                                    View Hardware
                                    <Plus size={14} className="group-hover/link:rotate-90 transition-transform" />
                                </Link>
                            </div>
                        </div>
                    ))}
                    {sites.length === 0 && (
                        <div className="col-span-full py-24 text-center">
                            <div className="w-20 h-20 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-6">
                                <MapPin size={32} className="text-gray-200" />
                            </div>
                            <h3 className="text-xl font-black text-gray-900 mb-2">No Active Sites</h3>
                            <p className="text-gray-400 font-medium max-w-xs mx-auto text-sm">Create an operational site to begin mapping your infrastructure.</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

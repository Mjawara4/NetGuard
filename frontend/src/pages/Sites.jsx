import React, { useEffect, useState } from 'react';
import api from '../api';
import { Link } from 'react-router-dom';
import { Plus, MapPin, Activity } from 'lucide-react';
import ResponsiveModal from '../components/ResponsiveModal';
import { Card, Badge } from '../components/ui';

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
        <div className="min-h-screen bg-ink-50 dark:bg-ink-900 pt-4 sm:pt-8 px-4 sm:px-6 lg:px-10 pb-12">
            <div className="max-w-7xl mx-auto">
                {/* Page Header */}
                <div className="mb-8 sm:mb-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
                    <div>
                        <h1 className="text-3xl sm:text-4xl font-semibold text-ink-900 dark:text-ink-50 tracking-tight leading-none">
                            Operational <span className="text-signal-600 dark:text-signal-300">Sites</span>
                        </h1>
                        <p className="text-ink-500 dark:text-ink-400 mt-2 font-medium text-sm sm:text-base">Network locations and logical segmentation.</p>
                    </div>
                    <button
                        onClick={() => setShowModal(true)}
                        className="bg-signal-600 text-white px-6 sm:px-8 py-3 rounded-md font-semibold text-xs sm:text-sm hover:bg-signal-700 shadow-xl transition-all active:scale-95 flex items-center justify-center gap-2 w-full md:w-auto"
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
                        <p className="text-signal-600 dark:text-signal-300 text-xs sm:text-sm mb-6 font-medium">Define a new operational area.</p>
                        <form onSubmit={handleAdd} className="space-y-6">
                            <div>
                                <label className="block text-xs font-medium text-ink-500 dark:text-ink-400 mb-2">Site name</label>
                                <input className="w-full bg-ink-50 dark:bg-ink-700 text-ink-900 dark:text-ink-100 border-none rounded-sm px-4 py-3 focus:ring-2 focus:ring-signal-500 transition-all font-medium text-sm" value={newSite.name} onChange={e => setNewSite({ ...newSite, name: e.target.value })} required />
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-ink-500 dark:text-ink-400 mb-2">Physical location</label>
                                <input className="w-full bg-ink-50 dark:bg-ink-700 text-ink-900 dark:text-ink-100 border-none rounded-sm px-4 py-3 focus:ring-2 focus:ring-signal-500 transition-all font-medium text-sm" value={newSite.location} onChange={e => setNewSite({ ...newSite, location: e.target.value })} />
                            </div>
                            <div className="flex items-center gap-3">
                                <input type="checkbox" className="w-5 h-5 rounded-sm border-ink-200 dark:border-ink-600 text-signal-600 focus:ring-signal-500" checked={newSite.auto_fix_enabled} onChange={e => setNewSite({ ...newSite, auto_fix_enabled: e.target.checked })} />
                                <label className="text-xs font-medium text-ink-500 dark:text-ink-400">Enable auto-fix</label>
                            </div>
                            <div className="flex flex-col sm:flex-row gap-3 pt-2">
                                <button type="button" onClick={() => setShowModal(false)} className="order-2 sm:order-1 flex-1 px-4 py-3 rounded-md font-semibold text-xs text-ink-500 dark:text-ink-400 hover:bg-ink-50 dark:hover:bg-ink-700 transition-colors">Discard</button>
                                <button type="submit" className="order-1 sm:order-2 flex-1 px-4 py-3 bg-signal-600 text-white rounded-md font-semibold text-xs shadow-lg">Save site</button>
                            </div>
                        </form>
                    </div>
                </ResponsiveModal>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
                    {sites.map((site) => (
                        <Card key={site.id} hover>
                            <div className="flex justify-between items-start mb-6">
                                <div className="p-4 bg-signal-600/10 dark:bg-signal-600/20 text-signal-600 dark:text-signal-300 rounded-md group-hover:bg-signal-600 group-hover:text-white transition-colors">
                                    <MapPin size={24} />
                                </div>
                                <Badge variant={site.auto_fix_enabled ? 'success' : 'neutral'}>
                                    AF {site.auto_fix_enabled ? 'ON' : 'OFF'}
                                </Badge>
                            </div>

                            <h3 className="text-xl sm:text-2xl font-semibold text-ink-900 dark:text-ink-50 tracking-tight mb-2 truncate">{site.name}</h3>
                            <p className="text-ink-500 dark:text-ink-400 text-xs sm:text-sm font-medium mb-8 truncate">{site.location || 'Remote location'}</p>

                            <div className="pt-6 border-t border-ink-200 dark:border-ink-700">
                                <Link to="/devices" className="text-xs font-semibold text-signal-600 dark:text-signal-300 flex items-center gap-2 group/link">
                                    View hardware
                                    <Plus size={14} className="group-hover/link:rotate-90 transition-transform" />
                                </Link>
                            </div>
                        </Card>
                    ))}
                    {sites.length === 0 && (
                        <div className="col-span-full py-24 text-center">
                            <div className="w-20 h-20 bg-ink-100 dark:bg-ink-800 rounded-full flex items-center justify-center mx-auto mb-6">
                                <MapPin size={32} className="text-ink-300 dark:text-ink-600" />
                            </div>
                            <h3 className="text-xl font-semibold text-ink-900 dark:text-ink-50 mb-2">No active sites</h3>
                            <p className="text-ink-500 dark:text-ink-400 font-medium max-w-xs mx-auto text-sm">Create an operational site to begin mapping your infrastructure.</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

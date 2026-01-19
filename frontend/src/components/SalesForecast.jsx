import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { TrendingUp, Calendar, AlertCircle, Loader } from 'lucide-react';
import axios from 'axios';

const SalesForecast = () => {
    const [data, setData] = useState([]);
    const [trend, setTrend] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetchForecast();
    }, []);

    const fetchForecast = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await axios.get('/api/v1/analytics/predictions?days=7', {
                headers: { Authorization: `Bearer ${token}` }
            });
            setData(response.data.forecast);
            setTrend(response.data.trend_analysis);
            setLoading(false);
        } catch (err) {
            console.error("Forecast Error:", err);
            setError("Failed to load forecast data.");
            setLoading(false);
        }
    };

    if (loading) return (
        <div className="p-8 flex justify-center items-center text-gray-500">
            <Loader className="animate-spin mr-2" /> Loading AI Forecast...
        </div>
    );

    if (error) return (
        <div className="p-8 text-center text-red-500 bg-red-50 rounded-xl border border-red-100">
            <AlertCircle className="mx-auto mb-2" />
            {error}
        </div>
    );

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Summary Card */}
            <div className="bg-gradient-to-r from-violet-600 to-indigo-600 rounded-2xl p-6 text-white shadow-lg">
                <div className="flex items-start justify-between">
                    <div>
                        <h3 className="text-lg font-semibold opacity-90 mb-1">AI Sales Prediction</h3>
                        <p className="text-2xl font-bold tracking-tight">Next 7 Days</p>
                    </div>
                    <div className="p-3 bg-white/20 rounded-xl backdrop-blur-sm">
                        <TrendingUp size={24} className="text-white" />
                    </div>
                </div>
                <div className="mt-4 pt-4 border-t border-white/20">
                    <p className="text-sm font-medium opacity-95 flex items-start gap-2">
                        <span className="bg-white/20 p-1 rounded text-xs px-2">Analysis</span>
                        {trend || "Sales are expected to follow current trends."}
                    </p>
                </div>
            </div>

            {/* Chart */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
                <h4 className="font-semibold text-gray-700 mb-6 flex items-center gap-2">
                    <Calendar size={18} className="text-gray-400" />
                    Forecast Visualization
                </h4>
                <div className="h-[300px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={data}>
                            <defs>
                                <linearGradient id="colorSales" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                            <XAxis
                                dataKey="date"
                                axisLine={false}
                                tickLine={false}
                                tick={{ fill: '#9ca3af', fontSize: 12 }}
                                dy={10}
                            />
                            <YAxis
                                axisLine={false}
                                tickLine={false}
                                tick={{ fill: '#9ca3af', fontSize: 12 }}
                                tickFormatter={(value) => `${value.toLocaleString()}`}
                            />
                            <Tooltip
                                contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                cursor={{ stroke: '#8b5cf6', strokeWidth: 2 }}
                            />
                            <Area
                                type="monotone"
                                dataKey="predicted_sales"
                                stroke="#8b5cf6"
                                strokeWidth={3}
                                fillOpacity={1}
                                fill="url(#colorSales)"
                                name="Predicted Sales"
                            />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    );
};

export default SalesForecast;

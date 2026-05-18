import React from 'react';

const colorMap = {
    blue: { bg: 'bg-blue-50', text: 'text-blue-600', border: 'border-blue-100', darkBg: 'dark:bg-blue-900/20', darkText: 'dark:text-blue-400', darkBorder: 'dark:border-blue-900/30' },
    indigo: { bg: 'bg-indigo-50', text: 'text-indigo-600', border: 'border-indigo-100', darkBg: 'dark:bg-indigo-900/20', darkText: 'dark:text-indigo-400', darkBorder: 'dark:border-indigo-900/30' },
    emerald: { bg: 'bg-emerald-50', text: 'text-emerald-600', border: 'border-emerald-100', darkBg: 'dark:bg-emerald-900/20', darkText: 'dark:text-emerald-400', darkBorder: 'dark:border-emerald-900/30' },
    red: { bg: 'bg-red-50', text: 'text-red-600', border: 'border-red-100', darkBg: 'dark:bg-red-900/20', darkText: 'dark:text-red-400', darkBorder: 'dark:border-red-900/30' },
    orange: { bg: 'bg-orange-50', text: 'text-orange-600', border: 'border-orange-100', darkBg: 'dark:bg-orange-900/20', darkText: 'dark:text-orange-400', darkBorder: 'dark:border-orange-900/30' },
    pink: { bg: 'bg-pink-50', text: 'text-pink-600', border: 'border-pink-100', darkBg: 'dark:bg-pink-900/20', darkText: 'dark:text-pink-400', darkBorder: 'dark:border-pink-900/30' },
    cyan: { bg: 'bg-cyan-50', text: 'text-cyan-600', border: 'border-cyan-100', darkBg: 'dark:bg-cyan-900/20', darkText: 'dark:text-cyan-400', darkBorder: 'dark:border-cyan-900/30' },
};

export function MetricCard({ title, value, icon: Icon, color = 'blue' }) {
    const c = colorMap[color] || colorMap.blue;
    return (
        <div className={`bg-white dark:bg-gray-800 p-6 rounded-[32px] border ${c.border} ${c.darkBorder} shadow-sm flex items-center gap-5 transition-all hover:scale-[1.02]`}>
            <div className={`p-4 rounded-2xl ${c.bg} ${c.darkBg} ${c.text} ${c.darkText}`}>
                <Icon size={24} />
            </div>
            <div>
                <p className="text-[10px] font-black uppercase tracking-widest opacity-60 text-gray-500 dark:text-gray-400">{title}</p>
                <h4 className="text-2xl font-black tracking-tight text-gray-900 dark:text-white">{value}</h4>
            </div>
        </div>
    );
}

export function TabButton({ id, label, icon: Icon, activeTab, setActiveTab }) {
    return (
        <button
            onClick={() => setActiveTab(id)}
            className={`flex-1 min-w-[140px] px-8 py-4 rounded-2xl font-black text-[10px] uppercase tracking-widest flex items-center justify-center gap-3 transition-all duration-300 whitespace-nowrap ${activeTab === id
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-100 dark:shadow-blue-900/30 scale-[1.02]'
                : 'text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'
                }`}
        >
            <Icon size={16} /> {label}
        </button>
    );
}

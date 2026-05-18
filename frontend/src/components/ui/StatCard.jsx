import React from 'react';

const colorMap = {
    blue: { bg: 'bg-blue-50', text: 'text-blue-600', darkBg: 'dark:bg-blue-900/20', darkText: 'dark:text-blue-400' },
    indigo: { bg: 'bg-indigo-50', text: 'text-indigo-600', darkBg: 'dark:bg-indigo-900/20', darkText: 'dark:text-indigo-400' },
    emerald: { bg: 'bg-emerald-50', text: 'text-emerald-600', darkBg: 'dark:bg-emerald-900/20', darkText: 'dark:text-emerald-400' },
    red: { bg: 'bg-red-50', text: 'text-red-600', darkBg: 'dark:bg-red-900/20', darkText: 'dark:text-red-400' },
    purple: { bg: 'bg-purple-50', text: 'text-purple-600', darkBg: 'dark:bg-purple-900/20', darkText: 'dark:text-purple-400' },
    orange: { bg: 'bg-orange-50', text: 'text-orange-600', darkBg: 'dark:bg-orange-900/20', darkText: 'dark:text-orange-400' },
    pink: { bg: 'bg-pink-50', text: 'text-pink-600', darkBg: 'dark:bg-pink-900/20', darkText: 'dark:text-pink-400' },
    cyan: { bg: 'bg-cyan-50', text: 'text-cyan-600', darkBg: 'dark:bg-cyan-900/20', darkText: 'dark:text-cyan-400' },
    yellow: { bg: 'bg-yellow-50', text: 'text-yellow-600', darkBg: 'dark:bg-yellow-900/20', darkText: 'dark:text-yellow-400' },
    gray: { bg: 'bg-gray-50', text: 'text-gray-600', darkBg: 'dark:bg-gray-900/20', darkText: 'dark:text-gray-400' },
};

export default function StatCard({ label, value, icon: Icon, color = 'blue', className = '' }) {
    const colors = colorMap[color] || colorMap.blue;

    return (
        <div className={`bg-white dark:bg-gray-800 p-6 rounded-3xl shadow-sm border border-gray-100 dark:border-gray-700 ${className}`}>
            <div className={`w-12 h-12 rounded-2xl ${colors.bg} ${colors.darkBg} ${colors.text} ${colors.darkText} flex items-center justify-center mb-4`}>
                <Icon size={24} />
            </div>
            <div className="text-3xl font-black text-gray-900 dark:text-white mb-1">{value}</div>
            <div className="text-xs font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider">{label}</div>
        </div>
    );
}

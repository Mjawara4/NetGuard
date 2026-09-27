import React from 'react';

const colorMap = {
    blue: { bg: 'bg-signal-600/10', text: 'text-signal-600', darkBg: 'dark:bg-signal-600/20', darkText: 'dark:text-signal-400' },
    indigo: { bg: 'bg-signal-600/10', text: 'text-signal-600', darkBg: 'dark:bg-signal-600/20', darkText: 'dark:text-signal-400' },
    emerald: { bg: 'bg-up/10', text: 'text-ink-900', darkBg: 'dark:bg-up/20', darkText: 'dark:text-ink-50' },
    red: { bg: 'bg-down/10', text: 'text-ink-900', darkBg: 'dark:bg-down/20', darkText: 'dark:text-ink-50' },
    orange: { bg: 'bg-warn/10', text: 'text-ink-900', darkBg: 'dark:bg-warn/20', darkText: 'dark:text-ink-50' },
    pink: { bg: 'bg-pink-50', text: 'text-pink-600', darkBg: 'dark:bg-pink-900/20', darkText: 'dark:text-pink-400' },
    cyan: { bg: 'bg-cyan-50', text: 'text-cyan-600', darkBg: 'dark:bg-cyan-900/20', darkText: 'dark:text-cyan-400' },
    yellow: { bg: 'bg-warn/10', text: 'text-ink-900', darkBg: 'dark:bg-warn/20', darkText: 'dark:text-ink-50' },
    gray: { bg: 'bg-ink-50', text: 'text-ink-600', darkBg: 'dark:bg-ink-900/20', darkText: 'dark:text-ink-400' },
};

export default function StatCard({ label, value, icon: Icon, color = 'blue', className = '' }) {
    const colors = colorMap[color] || colorMap.blue;

    return (
        <div className={`bg-white dark:bg-ink-800 p-6 rounded-md border border-ink-200 dark:border-ink-800 ${className}`}>
            {Icon && (
                <div className={`w-12 h-12 rounded-md ${colors.bg} ${colors.darkBg} ${colors.text} ${colors.darkText} flex items-center justify-center mb-4`}>
                    <Icon size={24} />
                </div>
            )}
            <div className="text-3xl font-bold font-display tabular-nums text-ink-900 dark:text-white mb-1">{value}</div>
            <div className="text-xs font-bold text-ink-400 dark:text-ink-500">{label}</div>
        </div>
    );
}

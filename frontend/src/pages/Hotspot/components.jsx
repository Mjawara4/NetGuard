import React from 'react';

// The spec allows one accent and three semantics, so the seven decorative hues
// this map used to carry collapse to four roles. The caller-facing keys are
// unchanged (no prop changes in this migration) -- they are now aliases, written
// as aliases rather than as seven near-identical literals so it is obvious that
// `blue`, `indigo`, `pink` and `cyan` are one colour and not four.
const accent = { bg: 'bg-signal-600/10', text: 'text-signal-600', border: 'border-signal-600/20', darkBg: 'dark:bg-signal-600/20', darkText: 'dark:text-signal-300', darkBorder: 'dark:border-signal-600/30' };
const positive = { bg: 'bg-up/10', text: 'text-up', border: 'border-up/20', darkBg: 'dark:bg-up/20', darkText: 'dark:text-ink-100', darkBorder: 'dark:border-up/30' };
const negative = { bg: 'bg-down/10', text: 'text-down', border: 'border-down/20', darkBg: 'dark:bg-down/20', darkText: 'dark:text-ink-100', darkBorder: 'dark:border-down/30' };
const caution = { bg: 'bg-warn/10', text: 'text-warn', border: 'border-warn/20', darkBg: 'dark:bg-warn/20', darkText: 'dark:text-ink-100', darkBorder: 'dark:border-warn/30' };

const colorMap = {
    blue: accent,
    indigo: accent,
    pink: accent,
    cyan: accent,
    emerald: positive,
    red: negative,
    orange: caution,
};

export function MetricCard({ title, value, icon: Icon, color = 'blue' }) {
    const c = colorMap[color] || colorMap.blue;
    return (
        <div className={`bg-white dark:bg-ink-800 p-6 rounded-lg border ${c.border} ${c.darkBorder} shadow-sm flex items-center gap-5 transition-all hover:scale-[1.02]`}>
            <div className={`p-4 rounded-lg ${c.bg} ${c.darkBg} ${c.text} ${c.darkText}`}>
                <Icon size={24} />
            </div>
            <div>
                {/* `opacity-60` dropped: it multiplied the caption token's measured
                    4.62:1 down to roughly 2.2:1, and element opacity is invisible to
                    a colour-pair grep. The token already carries the muted step. */}
                <p className="text-xs font-medium text-ink-500 dark:text-ink-400">{title}</p>
                <h4 className="text-2xl font-bold tracking-tight text-ink-900 dark:text-ink-50">{value}</h4>
            </div>
        </div>
    );
}

export function TabButton({ id, label, icon: Icon, activeTab, setActiveTab }) {
    return (
        <button
            onClick={() => setActiveTab(id)}
            className={`flex-1 min-w-[140px] px-8 py-4 rounded-lg font-semibold text-xs flex items-center justify-center gap-3 transition-all duration-300 whitespace-nowrap ${activeTab === id
                ? 'bg-signal-600 text-white shadow-lg scale-[1.02]'
                : 'text-ink-500 dark:text-ink-400 hover:text-ink-900 dark:hover:text-ink-100 hover:bg-ink-50 dark:hover:bg-ink-800'
                }`}
        >
            <Icon size={16} /> {label}
        </button>
    );
}

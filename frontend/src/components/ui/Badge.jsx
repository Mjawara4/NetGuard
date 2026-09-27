import React from 'react';

const variants = {
    critical: 'bg-down/10 text-down dark:bg-down/20 dark:text-down',
    warning: 'bg-warn/10 text-warn dark:bg-warn/20 dark:text-warn',
    success: 'bg-up/10 text-up dark:bg-up/20 dark:text-up',
    info: 'bg-signal-600/10 text-signal-600 dark:bg-signal-600/20 dark:text-signal-400',
    neutral: 'bg-ink-100 text-ink-600 dark:bg-ink-700 dark:text-ink-300',
    purple: 'bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400',
};

export default function Badge({ children, variant = 'neutral', className = '' }) {
    const base = 'inline-flex items-center px-3 py-1 text-xs font-semibold rounded-sm';
    return (
        <span className={`${base} ${variants[variant] || variants.neutral} ${className}`}>
            {children}
        </span>
    );
}

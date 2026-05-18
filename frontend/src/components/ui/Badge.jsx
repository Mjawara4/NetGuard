import React from 'react';

const variants = {
    critical: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400',
    warning: 'bg-yellow-100 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400',
    success: 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400',
    info: 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
    neutral: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300',
    purple: 'bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400',
};

export default function Badge({ children, variant = 'neutral', className = '' }) {
    const base = 'inline-flex items-center px-3 py-1 text-[10px] font-black uppercase rounded-lg';
    return (
        <span className={`${base} ${variants[variant] || variants.neutral} ${className}`}>
            {children}
        </span>
    );
}

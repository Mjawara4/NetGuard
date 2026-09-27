import React from 'react';

export default function Card({
    children,
    className = '',
    hover = false,
    padding = 'p-6 sm:p-8',
    icon: Icon,
    iconColor = 'text-signal-600',
    iconBg = 'bg-signal-600/10',
}) {
    return (
        <div
            className={`bg-white dark:bg-ink-800 rounded-md border border-ink-200 dark:border-ink-700 overflow-hidden ${padding} ${
                hover ? 'hover:shadow-xl hover:-translate-y-1 transition-all duration-300 group' : ''
            } ${className}`}
        >
            {Icon && (
                <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity pointer-events-none">
                    <Icon size={80} />
                </div>
            )}
            {children}
        </div>
    );
}

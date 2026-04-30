import React from 'react';

export default function Card({
    children,
    className = '',
    hover = false,
    padding = 'p-6 sm:p-8',
    icon: Icon,
    iconColor = 'text-blue-600',
    iconBg = 'bg-blue-50',
}) {
    return (
        <div
            className={`bg-white dark:bg-gray-800 rounded-3xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden ${padding} ${
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

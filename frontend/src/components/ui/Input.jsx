import React from 'react';

export default function Input({
    label,
    icon: Icon,
    error,
    className = '',
    inputClassName = '',
    labelClassName = '',
    containerClassName = '',
    ...props
}) {
    return (
        <div className={`space-y-1.5 ${containerClassName}`}>
            {label && (
                <label className={`block text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-widest ${labelClassName}`}>
                    {label}
                </label>
            )}
            <div className={`relative group ${className}`}>
                {Icon && (
                    <Icon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
                )}
                <input
                    className={`w-full bg-gray-50 dark:bg-gray-900 border-none rounded-2xl py-4 ${Icon ? 'pl-12' : 'pl-4'} pr-4 text-sm font-bold text-gray-900 dark:text-white placeholder:text-gray-300 dark:placeholder:text-gray-600 focus:ring-2 focus:ring-blue-500/20 dark:focus:ring-blue-500/40 transition-all outline-none ${inputClassName}`}
                    {...props}
                />
            </div>
            {error && <p className="text-xs text-red-500 font-medium">{error}</p>}
        </div>
    );
}

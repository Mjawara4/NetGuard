import React from 'react';

export default function Input({
    label,
    icon: Icon,
    error,
    className = '',
    inputClassName = '',
    labelClassName = '',
    containerClassName = '',
    id,
    textSize = 'text-sm',
    ...props
}) {
    return (
        <div className={`space-y-1.5 ${containerClassName}`}>
            {label && (
                <label htmlFor={id} className={`block text-xs font-medium text-ink-500 dark:text-ink-400 ${labelClassName}`}>
                    {label}
                </label>
            )}
            <div className={`relative group ${className}`}>
                {Icon && (
                    <Icon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-ink-500 dark:text-ink-400 group-focus-within:text-signal-500 transition-colors" />
                )}
                <input
                    id={id}
                    className={`w-full bg-ink-50 dark:bg-ink-900 border-none rounded-md py-4 ${Icon ? 'pl-12' : 'pl-4'} pr-4 ${textSize} font-medium text-ink-900 dark:text-ink-50 placeholder:text-ink-500 dark:placeholder:text-ink-400 focus:ring-2 focus:ring-signal-500/20 dark:focus:ring-signal-500/40 transition-all outline-none ${inputClassName}`}
                    {...props}
                />
            </div>
            {error && <p className="text-xs text-down font-medium">{error}</p>}
        </div>
    );
}

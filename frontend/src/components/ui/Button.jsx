import React from 'react';

const variants = {
    primary: 'bg-signal-600 text-white hover:bg-signal-700 shadow-xl active:scale-[0.98]',
    secondary: 'bg-ink-100 dark:bg-ink-700 text-ink-700 dark:text-ink-200 hover:bg-ink-200 dark:hover:bg-ink-600 active:scale-[0.98]',
    danger: 'bg-down text-white hover:bg-down/90 shadow-xl active:scale-[0.98]',
    ghost: 'text-ink-500 dark:text-ink-400 hover:bg-ink-50 dark:hover:bg-ink-800 hover:text-ink-700 dark:hover:text-ink-200',
    pill: 'rounded-md text-xs font-bold px-4 py-2',
    outline: 'border border-ink-200 dark:border-ink-600 text-ink-700 dark:text-ink-200 hover:bg-ink-50 dark:hover:bg-ink-800 active:scale-[0.98]',
};

const sizes = {
    sm: 'px-3 py-2 text-xs',
    md: 'px-6 py-3 text-sm',
    lg: 'px-8 py-4 text-sm',
    icon: 'p-3',
};

export default function Button({
    children,
    variant = 'primary',
    size = 'md',
    className = '',
    disabled = false,
    type = 'button',
    onClick,
    ...props
}) {
    const base = 'inline-flex items-center justify-center gap-2 rounded-md font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100';
    const variantClass = variants[variant] || variants.primary;
    const sizeClass = sizes[size] || sizes.md;

    return (
        <button
            type={type}
            onClick={onClick}
            disabled={disabled}
            className={`${base} ${variantClass} ${sizeClass} ${className}`}
            {...props}
        >
            {children}
        </button>
    );
}

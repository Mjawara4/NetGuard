import React from 'react';

const variants = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700 shadow-xl shadow-blue-100 active:scale-[0.98]',
    secondary: 'bg-gray-100 text-gray-700 hover:bg-gray-200 active:scale-[0.98]',
    danger: 'bg-red-600 text-white hover:bg-red-700 shadow-xl shadow-red-100 active:scale-[0.98]',
    ghost: 'text-gray-500 hover:bg-gray-50 hover:text-gray-700',
    pill: 'rounded-xl text-xs font-bold uppercase tracking-wider px-4 py-2',
    outline: 'border border-gray-200 text-gray-700 hover:bg-gray-50 active:scale-[0.98]',
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
    const base = 'inline-flex items-center justify-center gap-2 rounded-2xl font-black uppercase tracking-widest transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100';
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

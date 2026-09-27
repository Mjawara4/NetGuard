import React from 'react';

export default function PageHeader({ title, accent, subtitle, children }) {
    return (
        <div className="mb-8 sm:mb-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div>
                <h1 className="text-3xl sm:text-4xl font-semibold text-ink-900 dark:text-white tracking-tight leading-none">
                    {title} {accent && <span className="text-signal-600">{accent}</span>}
                </h1>
                {subtitle && (
                    <p className="text-ink-500 dark:text-ink-400 mt-2 font-medium text-sm sm:text-base">
                        {subtitle}
                    </p>
                )}
            </div>
            {children && <div className="flex items-center gap-3 flex-wrap">{children}</div>}
        </div>
    );
}

import React from 'react';

export default function PageHeader({ title, accent, subtitle, children }) {
    return (
        <div className="mb-8 sm:mb-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div>
                <h1 className="text-3xl sm:text-4xl font-semibold font-display text-ink-900 dark:text-ink-50 tracking-tight leading-none">
                    {/* signal-600 is 2.40:1 on a dark ground; the accent must drop to
                        signal-300 in dark mode, exactly as it does on the auth pages. */}
                    {title} {accent && <span className="text-signal-600 dark:text-signal-300">{accent}</span>}
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

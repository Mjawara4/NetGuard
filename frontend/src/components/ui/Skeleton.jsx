import React from 'react';

export default function Skeleton({ className = '', count = 1 }) {
    return (
        <>
            {Array.from({ length: count }).map((_, i) => (
                <div
                    key={i}
                    className={`animate-pulse bg-ink-200 dark:bg-ink-700 rounded-md ${className}`}
                />
            ))}
        </>
    );
}

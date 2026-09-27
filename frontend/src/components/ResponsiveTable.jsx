import React from 'react';

const ResponsiveTable = ({ columns, data, renderCard, keyField = 'id', emptyMessage = 'No data available' }) => {
    if (!data || data.length === 0) {
        return (
            <div className="p-8 text-center text-ink-500 dark:text-ink-400 bg-white dark:bg-ink-800 rounded-md border border-ink-200 dark:border-ink-700">
                {emptyMessage}
            </div>
        );
    }

    return (
        <>
            {/* Desktop Table View */}
            <div className="hidden md:block overflow-x-auto bg-white dark:bg-ink-800 rounded-md shadow-sm border border-ink-200 dark:border-ink-700">
                <table className="w-full text-left">
                    <thead>
                        <tr className="bg-ink-50/50 dark:bg-ink-800/50 border-b border-ink-200 dark:border-ink-700">
                            {columns.map((col, index) => (
                                <th key={index} className="p-4 text-xs font-semibold text-ink-500 dark:text-ink-400">
                                    {col.header}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-ink-200 dark:divide-ink-700">
                        {data.map((item, index) => (
                            <tr key={item[keyField] || index} className="hover:bg-ink-50/50 dark:hover:bg-ink-700/30 transition-colors">
                                {columns.map((col, colIndex) => (
                                    <td key={colIndex} className="p-4 text-sm text-ink-900 dark:text-ink-100">
                                        {col.render ? col.render(item) : item[col.accessor]}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Mobile Card View */}
            <div className="md:hidden space-y-4">
                {data.map((item, index) => (
                    <div key={item[keyField] || index} className="bg-white dark:bg-ink-800 p-4 rounded-md shadow-sm border border-ink-200 dark:border-ink-700">
                        {renderCard(item)}
                    </div>
                ))}
            </div>
        </>
    );
};

export default ResponsiveTable;

import React from 'react';

const ResponsiveTable = ({ columns, data, renderCard, keyField = 'id', emptyMessage = 'No data available' }) => {
    if (!data || data.length === 0) {
        return (
            <div className="p-8 text-center text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700">
                {emptyMessage}
            </div>
        );
    }

    return (
        <>
            {/* Desktop Table View */}
            <div className="hidden md:block overflow-x-auto bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700">
                <table className="w-full text-left">
                    <thead>
                        <tr className="bg-gray-50/50 dark:bg-gray-700/50 border-b border-gray-100 dark:border-gray-700">
                            {columns.map((col, index) => (
                                <th key={index} className="p-4 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                    {col.header}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50 dark:divide-gray-700">
                        {data.map((item, index) => (
                            <tr key={item[keyField] || index} className="hover:bg-gray-50/50 dark:hover:bg-gray-700/30 transition-colors">
                                {columns.map((col, colIndex) => (
                                    <td key={colIndex} className="p-4 text-sm text-gray-700 dark:text-gray-200">
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
                    <div key={item[keyField] || index} className="bg-white dark:bg-gray-800 p-4 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700">
                        {renderCard(item)}
                    </div>
                ))}
            </div>
        </>
    );
};

export default ResponsiveTable;

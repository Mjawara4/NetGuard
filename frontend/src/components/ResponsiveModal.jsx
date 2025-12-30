import React, { useEffect } from 'react';
import { X } from 'lucide-react';

const ResponsiveModal = ({ isOpen, onClose, title, children, size = 'md' }) => {
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = 'unset';
        }
        return () => {
            document.body.style.overflow = 'unset';
        };
    }, [isOpen]);

    if (!isOpen) return null;

    const sizeClasses = {
        sm: 'md:max-w-sm',
        md: 'md:max-w-md',
        lg: 'md:max-w-lg',
        xl: 'md:max-w-xl',
        '2xl': 'md:max-w-2xl',
        'full': 'md:max-w-full md:mx-4'
    };

    return (
        <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
                onClick={onClose}
            ></div>

            {/* Modal Container */}
            <div
                className={`
                    relative w-full bg-white md:rounded-2xl shadow-xl 
                    flex flex-col max-h-[90vh] md:max-h-[85vh]
                    ${sizeClasses[size]}
                    animate-slide-up md:animate-scale-in
                    rounded-t-2xl md:mx-4
                `}
            >
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-gray-100 shrink-0">
                    <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-gray-100 rounded-full transition-colors text-gray-500"
                    >
                        <X size={20} />
                    </button>
                </div>

                {/* Content - Scrollable */}
                <div className="p-4 overflow-y-auto overscroll-contain flex-1">
                    {children}
                </div>
            </div>
        </div>
    );
};

export default ResponsiveModal;

import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { MessageSquare, Send, X, Terminal, Loader } from 'lucide-react';
import useFocusTrap from '../hooks/useFocusTrap';

const AIChatParams = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [query, setQuery] = useState('');
    const [messages, setMessages] = useState([
        { role: 'assistant', text: 'Hello! I am your Network AI Assistant. Ask me anything about your sites, devices, or alerts.' }
    ]);
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef(null);
    const containerRef = useFocusTrap(isOpen);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, isOpen]);

    // Handle Cmd+K to open
    useEffect(() => {
        const handleKeyDown = (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                setIsOpen(prev => !prev);
            }
            if (e.key === 'Escape' && isOpen) {
                setIsOpen(false);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isOpen]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!query.trim()) return;

        const userMessage = { role: 'user', text: query };
        setMessages(prev => [...prev, userMessage]);
        setQuery('');
        setIsLoading(true);

        try {
            const token = localStorage.getItem('token');
            const response = await axios.post('/api/v1/ai-ops/chat',
                { query: userMessage.text },
                { headers: { Authorization: `Bearer ${token}` } }
            );

            const aiMessage = {
                role: 'assistant',
                text: response.data.response,
                sql: response.data.sql_query
            };
            setMessages(prev => [...prev, aiMessage]);
        } catch (error) {
            console.error("Chat Error:", error);
            setMessages(prev => [...prev, { role: 'assistant', text: "Sorry, I encountered an error connecting to the AI brain.", isError: true }]);
        } finally {
            setIsLoading(false);
        }
    };

    if (!isOpen) {
        return (
            <button
                onClick={() => setIsOpen(true)}
                className="fixed bottom-6 right-6 p-4 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-full shadow-lg hover:shadow-xl transition-all z-30 animate-bounce-slow"
                aria-label="Open AI Assistant (Cmd+K)"
                title="Open AI Assistant (Cmd+K)"
            >
                <MessageSquare size={24} />
            </button>
        );
    }

    return (
        <div
            ref={containerRef}
            className="fixed bottom-0 right-0 w-full sm:bottom-6 sm:right-6 sm:w-96 h-[80vh] max-h-[500px] bg-white dark:bg-gray-800 sm:rounded-2xl rounded-t-2xl shadow-2xl flex flex-col z-40 border border-gray-100 dark:border-gray-700 overflow-hidden font-sans transition-all duration-300"
            role="dialog"
            aria-label="AI Assistant Chat"
        >
            {/* Header */}
            <div className="p-4 bg-gradient-to-r from-blue-600 to-indigo-600 text-white flex justify-between items-center shrink-0">
                <div className="flex items-center gap-2">
                    <Terminal size={18} />
                    <h3 className="font-semibold text-sm">NetGuard AI Assistant</h3>
                </div>
                <button
                    onClick={() => setIsOpen(false)}
                    className="hover:bg-white/20 p-1 rounded-full text-white/80 hover:text-white transition"
                    aria-label="Close chat"
                >
                    <X size={18} />
                </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50 dark:bg-gray-900/50">
                {messages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[85%] p-3 rounded-2xl text-sm leading-relaxed shadow-sm ${msg.role === 'user'
                            ? 'bg-blue-600 text-white rounded-tr-none'
                            : 'bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 border border-gray-100 dark:border-gray-600 rounded-tl-none'
                            } ${msg.isError ? 'bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400 border-red-100 dark:border-red-800' : ''}`}>
                            <p>{msg.text}</p>
                        </div>
                    </div>
                ))}
                {isLoading && (
                    <div className="flex justify-start">
                        <div className="bg-white dark:bg-gray-700 p-3 rounded-2xl rounded-tl-none border dark:border-gray-600 shadow-sm flex items-center gap-2 text-gray-500 dark:text-gray-400 text-xs">
                            <Loader size={14} className="animate-spin" />
                            <span>Thinking...</span>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <form onSubmit={handleSubmit} className="p-3 bg-white dark:bg-gray-800 border-t dark:border-gray-700 flex gap-2 shrink-0">
                <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Ask about your network..."
                    className="flex-1 bg-gray-100 dark:bg-gray-900 border-none rounded-xl px-4 py-2 text-sm dark:text-white focus:ring-2 focus:ring-blue-500/50 focus:bg-white dark:focus:bg-gray-900 transition-all outline-none"
                    autoFocus
                />
                <button
                    type="submit"
                    disabled={isLoading || !query.trim()}
                    className="p-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    aria-label="Send message"
                >
                    <Send size={18} />
                </button>
            </form>
        </div>
    );
};

export default AIChatParams;

import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { MessageSquare, Send, X, Terminal, Loader } from 'lucide-react';

const AIChatParams = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [query, setQuery] = useState('');
    const [messages, setMessages] = useState([
        { role: 'assistant', text: 'Hello! I am your Network AI Assistant. Ask me anything about your sites, devices, or alerts.' }
    ]);
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef(null);

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
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, []);

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
                className="fixed bottom-6 right-6 p-4 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-full shadow-lg hover:shadow-xl transition-all z-50 animate-bounce-slow"
                title="Open AI Assistant (Cmd+K)"
            >
                <MessageSquare size={24} />
            </button>
        );
    }

    return (
        <div className="fixed bottom-6 right-6 w-96 h-[500px] bg-white rounded-2xl shadow-2xl flex flex-col z-50 border border-gray-100 overflow-hidden font-sans">
            {/* Header */}
            <div className="p-4 bg-gradient-to-r from-blue-600 to-indigo-600 text-white flex justify-between items-center">
                <div className="flex items-center gap-2">
                    <Terminal size={18} />
                    <h3 className="font-semibold text-sm">NetGuard AI Assistant</h3>
                </div>
                <button onClick={() => setIsOpen(false)} className="hover:bg-white/20 p-1 rounded-full text-white/80 hover:text-white transition">
                    <X size={18} />
                </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
                {messages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[85%] p-3 rounded-2xl text-sm leading-relaxed shadow-sm ${msg.role === 'user'
                            ? 'bg-blue-600 text-white rounded-tr-none'
                            : 'bg-white text-gray-800 border border-gray-100 rounded-tl-none'
                            } ${msg.isError ? 'bg-red-50 text-red-600 border-red-100' : ''}`}>
                            <p>{msg.text}</p>
                            {/* SQL display hidden as per user request */}
                        </div>
                    </div>
                ))}
                {isLoading && (
                    <div className="flex justify-start">
                        <div className="bg-white p-3 rounded-2xl rounded-tl-none border shadow-sm flex items-center gap-2 text-gray-500 text-xs">
                            <Loader size={14} className="animate-spin" />
                            <span>Thinking...</span>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <form onSubmit={handleSubmit} className="p-3 bg-white border-t flex gap-2">
                <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Ask about your network..."
                    className="flex-1 bg-gray-100 border-none rounded-xl px-4 py-2 text-sm focus:ring-2 focus:ring-blue-500/50 focus:bg-white transition-all outline-none"
                    autoFocus
                />
                <button
                    type="submit"
                    disabled={isLoading || !query.trim()}
                    className="p-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                    <Send size={18} />
                </button>
            </form>
        </div>
    );
};

export default AIChatParams;

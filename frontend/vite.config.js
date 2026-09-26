import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    build: {
        rollupOptions: {
            output: {
                manualChunks: {
                    // React changes rarely; a separate chunk stays cached
                    // across deploys.
                    react: ['react', 'react-dom', 'react-router-dom'],
                    // Charting and graph libraries are large and used by only
                    // a few routes.
                    charts: ['recharts'],
                    flow: ['reactflow'],
                },
            },
        },
    },
    server: {
        host: true,
        port: 3000,
        strictPort: true,
        proxy: {
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            }
        }
    },
    test: {
        environment: 'jsdom',
        globals: true,
        setupFiles: ['./src/test/setup.js'],
    }
})

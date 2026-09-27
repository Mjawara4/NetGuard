/** @type {import('tailwindcss').Config} */
export default {
    darkMode: 'class',
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            padding: {
                'safe-top': 'env(safe-area-inset-top)',
                'safe-bottom': 'env(safe-area-inset-bottom)',
                'safe-left': 'env(safe-area-inset-left)',
                'safe-right': 'env(safe-area-inset-right)',
            },
            margin: {
                'safe-top': 'env(safe-area-inset-top)',
                'safe-bottom': 'env(safe-area-inset-bottom)',
                'safe-left': 'env(safe-area-inset-left)',
                'safe-right': 'env(safe-area-inset-right)',
            },
            height: {
                'safe-screen': 'calc(100vh - env(safe-area-inset-top) - env(safe-area-inset-bottom))',
            },
            colors: {
                ink: {
                    50:  '#F6F8F7',
                    100: '#ECEFEE',
                    200: '#D9DEDC',
                    300: '#BAC2BF',
                    400: '#939E9A',
                    500: '#67736F',
                    600: '#55605D',
                    700: '#424B49',
                    800: '#2B3231',
                    900: '#1A1F1E',
                    950: '#101413',
                },
                signal: {
                    300: '#BB86D4',
                    400: '#A971C4',
                    500: '#8F4FAF',
                    600: '#7C3E9C',
                    700: '#653180',
                },
                up:   '#2F7D62',
                down: '#9A3A22',
                warn: '#8A6114',
            },
            fontFamily: {
                display: ['"Instrument Sans"', 'system-ui', 'sans-serif'],
            },
        },
    },
    plugins: [],
}

/** @type {import('tailwindcss').Config} */
export default {
    darkMode: 'class',
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        // At `theme` level, NOT inside `extend`: this REPLACES Tailwind's
        // default radius scale, so every off-ladder spelling (`rounded-xl`,
        // `rounded-2xl`, `rounded-t-3xl`, `rounded-[32px]`) stops resolving and
        // emits nothing at all. `no-banned-classes.test.js` proves that no such
        // spelling survives anywhere under src/.
        //
        // DEFAULT is mandatory and must stay: a bare `rounded`, `rounded-t` or
        // `rounded-tl` resolves to `borderRadius.DEFAULT`, and the app has ten
        // of those. Dropping this key squares all ten silently, with no error.
        borderRadius: {
            none: '0',
            DEFAULT: '4px',
            sm: '4px',
            md: '8px',
            lg: '14px',
            full: '9999px',
        },
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

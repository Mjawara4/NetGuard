// A voucher profile's colour band, the way denominations are coded on
// prepaid cards: it lets an operator tell profiles apart at a glance
// without reading. The colour is data, not decoration, so it is the same
// everywhere a profile appears.
//
// An unknown profile gets a neutral band rather than nothing — a router
// can hold profiles this map has never seen, and an invisible band would
// read as "no profile" instead of "a profile I don't have a colour for".

const BANDS = {
    'default': 'bg-signal-600',
    'day-pass': 'bg-up',
    'week': 'bg-warn',
};

const FALLBACK = 'bg-ink-400';

export function bandFor(profileName) {
    if (!profileName) return FALLBACK;
    return BANDS[profileName] ?? FALLBACK;
}

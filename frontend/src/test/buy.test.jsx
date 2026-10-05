import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Buy from '../pages/Buy';
import api from '../api';

vi.mock('../api', () => ({ default: { get: vi.fn(), post: vi.fn() } }));

describe('Buy', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        window.history.pushState({}, '', '/buy?router=11111111-1111-1111-1111-111111111111&mac=AA:BB');
        api.get.mockResolvedValue({
            data: { enabled: true, plans: [{ profile: '3-Hours', price: 10, currency: 'GMD' }] },
        });
        api.post.mockRejectedValue({ response: { data: { detail: 'redirect intercepted' } } });
    });

    it('renders server plans and sends the selected plan to checkout', async () => {
        render(<Buy />);
        expect(await screen.findByText('D10')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Buy' }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith('/buy/pay', {
            router: '11111111-1111-1111-1111-111111111111',
            mac: 'AA:BB',
            plan: '3-Hours',
        }));
    });

    it('shows an unavailable message when payments are disabled', async () => {
        api.get.mockResolvedValue({ data: { enabled: false, plans: [] } });
        render(<Buy />);
        expect(await screen.findByText(/payments are not available/i)).toBeInTheDocument();
    });
});

import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PaymentSettings from '../pages/PaymentSettings';
import api from '../api';

vi.mock('../api', () => ({
    default: { get: vi.fn(), put: vi.fn() },
}));

describe('PaymentSettings', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        api.get.mockResolvedValue({ data: { configured: true, payments_enabled: false } });
        api.put.mockResolvedValue({ data: { configured: true, payments_enabled: true } });
    });

    it('never renders stored credentials and posts newly entered credentials', async () => {
        render(<PaymentSettings />);
        expect(await screen.findByText('Credentials configured')).toBeInTheDocument();
        expect(screen.queryByDisplayValue(/sk_test|whsec/)).not.toBeInTheDocument();

        fireEvent.change(screen.getByLabelText('Modem Pay secret key'), { target: { value: 'sk_test_NEW' } });
        fireEvent.change(screen.getByLabelText('Modem Pay webhook secret'), { target: { value: 'whsec_NEW' } });
        fireEvent.click(screen.getByLabelText('Enable captive-portal payments'));
        fireEvent.click(screen.getByRole('button', { name: 'Save payment settings' }));

        await waitFor(() => expect(api.put).toHaveBeenCalledWith('/payments/settings', {
            modempay_secret_key: 'sk_test_NEW',
            modempay_webhook_secret: 'whsec_NEW',
            payments_enabled: true,
        }));
    });
});

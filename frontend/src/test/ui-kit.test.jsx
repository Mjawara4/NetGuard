import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { Button, Card, StatCard, Badge, Input } from '../components/ui';

describe('UI kit after tokenisation', () => {
    it('a primary button uses the accent, not default blue', () => {
        const { container } = render(<Button>Save changes</Button>);
        const html = container.innerHTML;
        expect(html).not.toMatch(/blue-\d/);
        expect(html).toMatch(/signal-600/);
    });

    it('no kit component uses font-black or uppercase', () => {
        const { container } = render(
            <div>
                <Button>Save changes</Button>
                <Card><span>body</span></Card>
                <StatCard label="Active sessions" value="38" />
                <Badge>Online</Badge>
            </div>
        );
        expect(container.innerHTML).not.toMatch(/font-black/);
        expect(container.innerHTML).not.toMatch(/uppercase/);
        expect(container.innerHTML).not.toMatch(/tracking-widest/);
    });

    it('no kit component uses a 10px label', () => {
        const { container } = render(<StatCard label="Active sessions" value="38" />);
        expect(container.innerHTML).not.toMatch(/text-\[10px\]/);
    });

    it('StatCard still renders its label and value', () => {
        render(<StatCard label="Active sessions" value="38" />);
        expect(screen.getByText('Active sessions')).toBeInTheDocument();
        expect(screen.getByText('38')).toBeInTheDocument();
    });

    it('numerals are tabular so columns of figures line up', () => {
        const { container } = render(<StatCard label="Vouchers" value="11,237" />);
        expect(container.innerHTML).toMatch(/tabular-nums/);
    });

    it('Input still associates its label with its control', () => {
        render(<Input id="qty" label="How many" />);
        expect(screen.getByLabelText('How many')).toBeInTheDocument();
    });

    // Review Focus #1: a token swap can look right in light and wrong in dark.
    it('renders under the dark class without throwing', () => {
        const { container } = render(
            <div className="dark">
                <Card><StatCard label="Active sessions" value="38" /></Card>
            </div>
        );
        expect(container.querySelector('.dark')).toBeInTheDocument();
    });
});

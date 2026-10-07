import { describe, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router';
import { render, screen } from '@testing-library/react';
import { FtsProcessStepper, funnelStagePath } from '@features/master/ui/FtsProcessStepper';
import { StrategyTreeStepper, treeStagePath } from '@features/master/ui/StrategyTreeStepper';

describe('FTS funnel navigation', () => {
  it('builds stable stage URLs with preset and symbol', () => {
    expect(funnelStagePath('technical', 'trend', 'فولاد')).toContain('/master?');
    expect(funnelStagePath('technical', 'trend', 'فولاد')).toContain('stage=technical');
    expect(funnelStagePath('technical', 'trend', 'فولاد')).toContain('preset=trend');
    expect(funnelStagePath('technical', 'trend', 'فولاد')).toContain(encodeURIComponent('فولاد'));
  });

  it('renders all four funnel destinations', () => {
    render(
      <MemoryRouter>
        <FtsProcessStepper active="technical" preset="trend" />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('fts-process-stepper')).toBeInTheDocument();
    for (const stage of ['tape', 'technical', 'fundamental', 'handover']) {
      expect(screen.getByRole('link', { name: new RegExp(stage === 'tape' ? 'تابلوخوانی' : stage === 'technical' ? 'تکنیکال' : stage === 'fundamental' ? 'بنیادی' : 'تحویل') })).toBeInTheDocument();
    }
  });
});

describe('FTS strategy tree navigation', () => {
  it('builds separate page URLs for all four chart pages', () => {
    for (const zone of ['S', 'T', 'F', 'M'] as const) {
      const url = treeStagePath(zone, 'trend', 'فولاد');
      expect(url).toContain('/strategy-tree?');
      expect(url).toContain(`page=${zone}`);
      expect(url).toContain('preset=trend');
    }
  });

  it('renders a four-page roadmap stepper', () => {
    render(
      <MemoryRouter>
        <StrategyTreeStepper active="T" preset="trend" />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('strategy-tree-stepper')).toBeInTheDocument();
    expect(screen.getAllByRole('link')).toHaveLength(4);
  });
});

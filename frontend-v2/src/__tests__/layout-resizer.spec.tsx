import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LayoutResizer } from '@shared/workspace/LayoutResizer';

const rect = { left: 0, top: 0, width: 1000, height: 600 };

function mount(patch: Partial<Parameters<typeof LayoutResizer>[0]> = {}) {
  const onChange = vi.fn();
  render(
    <LayoutResizer
      orientation="vertical"
      value={320}
      min={260}
      max={420}
      step={8}
      defaultValue={320}
      label="عرض سایدبار"
      testId="resize-test"
      increaseKey="ArrowRight"
      decreaseKey="ArrowLeft"
      fromPointer={(box, x) => x - box.left}
      measure={() => rect}
      onChange={onChange}
      {...patch}
    />,
  );
  return onChange;
}

afterEach(cleanup);

describe('LayoutResizer', () => {
  it('exposes separator semantics', () => {
    mount();
    const separator = screen.getByTestId('resize-test');
    expect(separator.getAttribute('role')).toBe('separator');
    expect(separator.getAttribute('aria-orientation')).toBe('vertical');
    expect(separator.getAttribute('aria-valuenow')).toBe('320');
    expect(separator.getAttribute('aria-valuemin')).toBe('260');
    expect(separator.getAttribute('aria-valuemax')).toBe('420');
  });

  it('reports the pointer-derived value while dragging', () => {
    const onChange = mount();
    const separator = screen.getByTestId('resize-test');
    fireEvent.mouseDown(separator, { clientX: 320, clientY: 100 });
    fireEvent.mouseMove(window, { clientX: 372, clientY: 100 });
    expect(onChange).toHaveBeenLastCalledWith(372);
  });

  it('clamps to the declared range', () => {
    const onChange = mount();
    const separator = screen.getByTestId('resize-test');
    fireEvent.mouseDown(separator, { clientX: 320 });
    fireEvent.mouseMove(window, { clientX: 900 });
    expect(onChange).toHaveBeenLastCalledWith(420);
    fireEvent.mouseMove(window, { clientX: 10 });
    expect(onChange).toHaveBeenLastCalledWith(260);
  });

  it('does not resize before a mouse down', () => {
    const onChange = mount();
    fireEvent.mouseMove(window, { clientX: 400 });
    expect(onChange).not.toHaveBeenCalled();
  });

  it('moves by keyboard and resets on double click and Enter', () => {
    const onChange = mount({ value: 340 });
    const separator = screen.getByTestId('resize-test');
    fireEvent.keyDown(separator, { key: 'ArrowRight' });
    expect(onChange).toHaveBeenLastCalledWith(348);
    fireEvent.keyDown(separator, { key: 'ArrowLeft' });
    expect(onChange).toHaveBeenLastCalledWith(332);
    fireEvent.doubleClick(separator);
    expect(onChange).toHaveBeenLastCalledWith(320);
    fireEvent.keyDown(separator, { key: 'Enter' });
    expect(onChange).toHaveBeenLastCalledWith(320);
  });
});

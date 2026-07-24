import { describe, expect, it } from 'vitest';
import { cn } from './cn';
import { buttonVariants } from '@/components/ui/Button';

/**
 * Regression guard for the bug where tailwind-merge, not knowing our custom
 * type scale (§4.3), filed `text-body` under `text-color` and deleted whichever
 * colour class came before it. Every Button rendered with inherited `--ink`.
 * It was invisible in dark mode — there `--brand-fg` and `--ink` are the same
 * value — and unreadable in light mode.
 */
describe('cn — custom scales survive the merge', () => {
  it.each([
    ['display-lg', 'text-display-lg'],
    ['display', 'text-display'],
    ['h1', 'text-h1'],
    ['h2', 'text-h2'],
    ['h3', 'text-h3'],
    ['body-lg', 'text-body-lg'],
    ['body', 'text-body'],
    ['body-sm', 'text-body-sm'],
    ['caption', 'text-caption'],
    ['label', 'text-label'],
    ['data', 'text-data'],
    ['data-lg', 'text-data-lg'],
    ['data-xl', 'text-data-xl'],
  ])('keeps a colour alongside text-%s, in either order', (_name, size) => {
    expect(cn('text-ink', size).split(' ').sort()).toEqual(['text-ink', size].sort());
    expect(cn(size, 'text-ink').split(' ').sort()).toEqual(['text-ink', size].sort());
  });

  it('still resolves genuine conflicts', () => {
    expect(cn('text-body', 'text-h1')).toBe('text-h1');
    expect(cn('text-ink', 'text-brand-fg')).toBe('text-brand-fg');
    expect(cn('shadow-e1', 'shadow-e2')).toBe('shadow-e2');
    expect(cn('h-row', 'h-badge')).toBe('h-badge');
    expect(cn('duration-micro', 'duration-page')).toBe('duration-page');
  });

  it('keeps elevation and motion tokens next to their colour counterparts', () => {
    expect(cn('shadow-e2', 'text-ink')).toContain('shadow-e2');
    expect(cn('h-app-bar', 'w-sidebar', 'min-h-dvh', 'max-w-content').split(' ')).toHaveLength(4);
  });
});

describe('Button variants keep their foreground colour', () => {
  it.each([
    ['primary', 'text-brand-fg'],
    ['secondary', 'text-ink'],
    ['ghost', 'text-text-secondary'],
    ['danger', 'text-canvas'],
    ['link', 'text-brand'],
  ] as const)('%s renders %s', (variant, colour) => {
    for (const size of ['sm', 'md', 'lg'] as const) {
      expect(cn(buttonVariants({ variant, size }))).toContain(colour);
    }
  });
});

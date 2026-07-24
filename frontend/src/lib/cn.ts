import { clsx, type ClassValue } from 'clsx';
import { extendTailwindMerge } from 'tailwind-merge';

/**
 * tailwind-merge only knows Tailwind's *stock* scales. Our type scale (§4.3) is
 * fully custom — `text-body`, `text-h1`, `text-data-lg` — and none of those names
 * look like a font size to it, so it filed them under `text-color` instead and
 * treated them as conflicting with real colours.
 *
 * The damage was silent and one-directional: `cn('text-brand-fg', 'text-body')`
 * returned just `text-body`, dropping the colour and letting the button inherit
 * `--ink` from <body>. In dark mode `--brand-fg` and `--ink` are the same value,
 * so it looked fine; in light mode it rendered #09004a text on a #19154e fill.
 *
 * Declaring the custom scales below puts every class back in its real group.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      // §4.3 type scale — must outrank the `text-color` catch-all.
      'font-size': [
        {
          text: [
            'display-lg',
            'display',
            'h1',
            'h2',
            'h3',
            'body-lg',
            'body',
            'body-sm',
            'caption',
            'label',
            'data',
            'data-lg',
            'data-xl',
          ],
        },
      ],
      // §4.4 elevation — otherwise read as `shadow-color`.
      'shadow': [{ shadow: ['e1', 'e2', 'e3'] }],
      // §5.3 fixed component dimensions.
      'w': [{ w: ['sidebar', 'sidebar-collapsed'] }],
      'h': [{ h: ['row', 'badge', 'app-bar', 'classification', 'dvh'] }],
      'min-w': [{ 'min-w': ['menu'] }],
      'min-h': [{ 'min-h': ['dvh', 'panel'] }],
      'max-w': [{ 'max-w': ['content', 'form', 'card'] }],
      // §4.6 motion tokens.
      'duration': [{ duration: ['micro', 'panel', 'page'] }],
      'ease': [{ ease: ['entry', 'exit'] }],
    },
  },
});

/**
 * Merge conditional class names and resolve Tailwind conflicts.
 * The single class-composition helper used across every component.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

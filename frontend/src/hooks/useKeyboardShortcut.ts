import { useEffect } from 'react';

/**
 * Register a global keyboard shortcut. Used for the command palette (⌘K / Ctrl+K).
 * Ignores keystrokes originating in text inputs unless `allowInInputs` is set.
 */
export function useKeyboardShortcut(
  key: string,
  handler: (e: KeyboardEvent) => void,
  opts: { meta?: boolean; ctrl?: boolean; allowInInputs?: boolean } = {},
): void {
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const inField =
        target &&
        (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);
      if (inField && !opts.allowInInputs) return;
      const modOk = opts.meta || opts.ctrl ? e.metaKey || e.ctrlKey : true;
      if (e.key.toLowerCase() === key.toLowerCase() && modOk) {
        handler(e);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [key, handler, opts.meta, opts.ctrl, opts.allowInInputs]);
}

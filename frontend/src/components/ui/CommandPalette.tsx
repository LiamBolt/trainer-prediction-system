import { Fragment } from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { VisuallyHidden } from '@radix-ui/react-visually-hidden';
import { cn } from '@/lib/cn';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from './Command';

/**
 * CommandPalette — cmdk in a glass Dialog, opened with ⌘K / Ctrl+K (§10.1, §4.5).
 * Commands are grouped; selecting one runs its action and closes the palette.
 */
export interface PaletteCommand {
  id: string;
  label: string;
  icon?: React.ReactNode;
  hint?: string;
  keywords?: string;
  run: () => void;
}

export interface PaletteGroup {
  heading: string;
  commands: PaletteCommand[];
}

export function CommandPalette({
  open,
  onOpenChange,
  groups,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  groups: PaletteGroup[];
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-overlay backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content
          className={cn(
            'glass fixed left-1/2 top-24 z-50 w-full max-w-xl -translate-x-1/2 overflow-hidden rounded-lg shadow-e3',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 duration-panel',
          )}
        >
          <DialogPrimitive.Title asChild>
            <VisuallyHidden>Command palette</VisuallyHidden>
          </DialogPrimitive.Title>
          <Command loop>
            <CommandInput placeholder="Search commands, screens and trainers…" autoFocus />
            <CommandList>
              <CommandEmpty>No results found.</CommandEmpty>
              {groups.map((group) => (
                <Fragment key={group.heading}>
                  {group.commands.length > 0 && (
                    <CommandGroup heading={group.heading}>
                      {group.commands.map((cmd) => (
                        <CommandItem
                          key={cmd.id}
                          value={`${group.heading} ${cmd.label} ${cmd.keywords ?? ''}`}
                          onSelect={() => {
                            onOpenChange(false);
                            cmd.run();
                          }}
                        >
                          {cmd.icon && <span className="shrink-0 text-text-muted">{cmd.icon}</span>}
                          <span className="flex-1 truncate">{cmd.label}</span>
                          {cmd.hint && (
                            <span className="font-mono text-label uppercase text-text-disabled">
                              {cmd.hint}
                            </span>
                          )}
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  )}
                </Fragment>
              ))}
            </CommandList>
          </Command>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

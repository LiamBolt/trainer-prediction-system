import { useState } from 'react';
import { Check, ChevronsUpDown, X } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Popover, PopoverContent, PopoverTrigger } from './Popover';
import { Command, CommandEmpty, CommandInput, CommandItem, CommandList } from './Command';
import { useField } from './Field';

/**
 * Combobox — a searchable, keyboard-navigable, clearable single-select (§10.1).
 * Used wherever a Select would have too many options (e.g. required
 * specialisation, station, category).
 */
export interface ComboboxOption {
  value: string;
  label: string;
}

export interface ComboboxProps {
  value?: string;
  onChange: (value: string) => void;
  options: ComboboxOption[];
  placeholder?: string;
  searchPlaceholder?: string;
  emptyText?: string;
  clearable?: boolean;
  disabled?: boolean;
  invalid?: boolean;
  id?: string;
  className?: string;
}

export function Combobox({
  value,
  onChange,
  options,
  placeholder = 'Select…',
  searchPlaceholder = 'Search…',
  emptyText = 'No match found.',
  clearable = true,
  disabled,
  invalid,
  id,
  className,
}: ComboboxProps) {
  const [open, setOpen] = useState(false);
  const field = useField();
  const hasError = invalid ?? field?.hasError ?? false;
  const selected = options.find((o) => o.value === value);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          id={id ?? field?.id}
          role="combobox"
          aria-expanded={open}
          aria-invalid={hasError || undefined}
          disabled={disabled}
          className={cn(
            'flex h-10 w-full items-center justify-between gap-2 rounded-sm border bg-surface px-3.5 text-body transition-colors duration-micro ' +
              'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ' +
              'disabled:cursor-not-allowed disabled:opacity-50',
            hasError ? 'border-danger-fg' : 'border-strong',
            selected ? 'text-ink' : 'text-text-disabled',
            className,
          )}
        >
          <span className="truncate">{selected?.label ?? placeholder}</span>
          <span className="flex shrink-0 items-center gap-1">
            {clearable && selected && (
              <span
                role="button"
                tabIndex={-1}
                aria-label="Clear"
                onClick={(e) => {
                  e.stopPropagation();
                  onChange('');
                }}
                className="rounded-sm text-text-muted hover:text-ink"
              >
                <X size={14} className="shrink-0" />
              </span>
            )}
            <ChevronsUpDown size={16} className="shrink-0 text-text-muted" />
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[--radix-popover-trigger-width] p-0">
        <Command>
          <CommandInput placeholder={searchPlaceholder} />
          <CommandList>
            <CommandEmpty>{emptyText}</CommandEmpty>
            {options.map((opt) => (
              <CommandItem
                key={opt.value}
                value={opt.label}
                onSelect={() => {
                  onChange(opt.value);
                  setOpen(false);
                }}
              >
                <Check
                  size={16}
                  className={cn('shrink-0 text-brand', opt.value === value ? 'opacity-100' : 'opacity-0')}
                />
                <span className="truncate">{opt.label}</span>
              </CommandItem>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

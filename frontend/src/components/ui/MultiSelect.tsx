import { useState } from 'react';
import { Check, ChevronsUpDown, X } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Popover, PopoverContent, PopoverTrigger } from './Popover';
import { Command, CommandEmpty, CommandInput, CommandItem, CommandList } from './Command';
import { useField } from './Field';
import type { ComboboxOption } from './Combobox';

export interface MultiSelectProps {
  values: string[];
  onChange: (values: string[]) => void;
  options: ComboboxOption[];
  placeholder?: string;
  searchPlaceholder?: string;
  emptyText?: string;
  disabled?: boolean;
  invalid?: boolean;
  id?: string;
  className?: string;
}

/** MultiSelect — searchable multi-choice with removable chips (§10.1). */
export function MultiSelect({
  values,
  onChange,
  options,
  placeholder = 'Select…',
  searchPlaceholder = 'Search…',
  emptyText = 'No match found.',
  disabled,
  invalid,
  id,
  className,
}: MultiSelectProps) {
  const [open, setOpen] = useState(false);
  const field = useField();
  const hasError = invalid ?? field?.hasError ?? false;
  const selected = options.filter((o) => values.includes(o.value));

  const toggle = (value: string) => {
    onChange(values.includes(value) ? values.filter((v) => v !== value) : [...values, value]);
  };

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
            'flex min-h-10 w-full items-center justify-between gap-2 rounded-sm border bg-surface px-2 py-1 text-body transition-colors duration-micro ' +
              'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ' +
              'disabled:cursor-not-allowed disabled:opacity-50',
            hasError ? 'border-danger-fg' : 'border-strong',
            className,
          )}
        >
          <span className="flex flex-1 flex-wrap items-center gap-1">
            {selected.length === 0 && <span className="pl-1.5 text-text-disabled">{placeholder}</span>}
            {selected.map((o) => (
              <span
                key={o.value}
                className="inline-flex h-6 items-center gap-1 rounded-sm bg-surface-sunken pl-2 pr-1 text-body-sm text-ink"
              >
                {o.label}
                <span
                  role="button"
                  tabIndex={-1}
                  aria-label={`Remove ${o.label}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    toggle(o.value);
                  }}
                  className="text-text-muted hover:text-ink"
                >
                  <X size={14} className="shrink-0" />
                </span>
              </span>
            ))}
          </span>
          <ChevronsUpDown size={16} className="shrink-0 text-text-muted" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[--radix-popover-trigger-width] p-0">
        <Command>
          <CommandInput placeholder={searchPlaceholder} />
          <CommandList>
            <CommandEmpty>{emptyText}</CommandEmpty>
            {options.map((opt) => {
              const isSelected = values.includes(opt.value);
              return (
                <CommandItem key={opt.value} value={opt.label} onSelect={() => toggle(opt.value)}>
                  <span
                    className={cn(
                      'flex h-5 w-5 shrink-0 items-center justify-center rounded-sm border',
                      isSelected ? 'border-brand bg-brand text-brand-fg' : 'border-strong',
                    )}
                  >
                    {isSelected && <Check size={14} strokeWidth={3} className="shrink-0" />}
                  </span>
                  <span className="truncate">{opt.label}</span>
                </CommandItem>
              );
            })}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

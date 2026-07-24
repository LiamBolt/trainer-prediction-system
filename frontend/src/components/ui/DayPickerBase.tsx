/* eslint-disable react-refresh/only-export-components -- variants/hooks are intentionally co-located with their component; this rule only affects dev-time Fast Refresh. */
import { DayPicker, type DayPickerProps } from 'react-day-picker';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/cn';

/**
 * Shared react-day-picker configuration + Tailwind classNames. Consumed by both
 * <DatePicker/> and <DateRangePicker/> so the calendar looks identical in both.
 */
export function CalendarBase(props: DayPickerProps) {
  return (
    <DayPicker
      showOutsideDays
      captionLayout="dropdown-buttons"
      fromYear={2020}
      toYear={2030}
      className="p-3"
      classNames={{
        months: 'flex flex-col',
        month: 'space-y-3',
        caption: 'relative flex items-center justify-center gap-2 px-1',
        caption_label: 'hidden',
        caption_dropdowns: 'flex items-center gap-1',
        dropdown:
          'h-8 rounded-sm border border-strong bg-surface px-2 text-body-sm text-ink outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
        nav: 'flex items-center gap-1',
        nav_button:
          'inline-flex h-8 w-8 items-center justify-center rounded-sm text-text-secondary hover:bg-surface-sunken',
        nav_button_previous: 'absolute left-1',
        nav_button_next: 'absolute right-1',
        table: 'w-full border-collapse',
        head_row: 'flex',
        head_cell: 'w-9 font-mono text-label uppercase text-text-muted',
        row: 'mt-1 flex w-full',
        cell: 'p-0',
        day: 'inline-flex h-9 w-9 items-center justify-center rounded-sm text-body-sm tabular-nums text-ink transition-colors hover:bg-surface-sunken focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
        day_today: 'font-semibold text-brand',
        day_outside: 'text-text-disabled',
        day_disabled: 'opacity-40',
        day_selected: 'bg-brand text-brand-fg hover:bg-brand',
        day_range_middle: 'rounded-none bg-surface-sunken text-ink',
        day_range_start: 'rounded-l-sm',
        day_range_end: 'rounded-r-sm',
        ...props.classNames,
      }}
      components={{
        IconLeft: () => <ChevronLeft size={16} className="shrink-0" />,
        IconRight: () => <ChevronRight size={16} className="shrink-0" />,
      }}
      {...props}
    />
  );
}

export function calendarTriggerClass(hasValue: boolean, hasError: boolean, extra?: string): string {
  return cn(
    'flex h-10 w-full items-center justify-between gap-2 rounded-sm border bg-surface px-3.5 text-body transition-colors duration-micro ' +
      'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ' +
      'disabled:cursor-not-allowed disabled:opacity-50',
    hasError ? 'border-danger-fg' : 'border-strong',
    hasValue ? 'text-ink' : 'text-text-disabled',
    extra,
  );
}

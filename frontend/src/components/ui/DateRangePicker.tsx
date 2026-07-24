import { useState } from 'react';
import { CalendarDays } from 'lucide-react';
import dayjs from 'dayjs';
import type { DateRange } from 'react-day-picker';
import { Popover, PopoverContent, PopoverTrigger } from './Popover';
import { CalendarBase, calendarTriggerClass } from './DayPickerBase';
import { useField } from './Field';
import { formatDate } from '@/lib/format';

export interface DateRangeValue {
  from?: string;
  to?: string;
}

/** DateRangePicker — used by the report and table date-range filters (§11.9). */
export interface DateRangePickerProps {
  value: DateRangeValue;
  onChange: (value: DateRangeValue) => void;
  placeholder?: string;
  disabled?: boolean;
  id?: string;
  className?: string;
}

export function DateRangePicker({
  value,
  onChange,
  placeholder = 'Select a date range',
  disabled,
  id,
  className,
}: DateRangePickerProps) {
  const [open, setOpen] = useState(false);
  const field = useField();
  const selectedRange: DateRange | undefined = value.from
    ? { from: dayjs(value.from).toDate(), to: value.to ? dayjs(value.to).toDate() : undefined }
    : undefined;

  const label =
    value.from && value.to
      ? `${formatDate(value.from)} – ${formatDate(value.to)}`
      : value.from
        ? `${formatDate(value.from)} – …`
        : placeholder;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          id={id ?? field?.id}
          disabled={disabled}
          className={calendarTriggerClass(Boolean(value.from), false, className)}
        >
          <span className="truncate">{label}</span>
          <CalendarDays size={16} className="shrink-0 text-text-muted" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-auto p-0">
        <CalendarBase
          mode="range"
          numberOfMonths={1}
          selected={selectedRange}
          defaultMonth={selectedRange?.from}
          onSelect={(range) => {
            onChange({
              from: range?.from ? dayjs(range.from).format('YYYY-MM-DD') : undefined,
              to: range?.to ? dayjs(range.to).format('YYYY-MM-DD') : undefined,
            });
          }}
        />
      </PopoverContent>
    </Popover>
  );
}

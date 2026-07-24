import { useState } from 'react';
import { CalendarDays } from 'lucide-react';
import dayjs from 'dayjs';
import { Popover, PopoverContent, PopoverTrigger } from './Popover';
import { CalendarBase, calendarTriggerClass } from './DayPickerBase';
import { useField } from './Field';
import { formatDate } from '@/lib/format';

/** DatePicker — single date, react-day-picker with month/year jump (§10.1). */
export interface DatePickerProps {
  value?: string; // ISO date
  onChange: (value: string | undefined) => void;
  placeholder?: string;
  disabled?: boolean;
  invalid?: boolean;
  id?: string;
  minDate?: string;
  className?: string;
}

export function DatePicker({
  value,
  onChange,
  placeholder = 'Select a date',
  disabled,
  invalid,
  id,
  minDate,
  className,
}: DatePickerProps) {
  const [open, setOpen] = useState(false);
  const field = useField();
  const hasError = invalid ?? field?.hasError ?? false;
  const selected = value ? dayjs(value).toDate() : undefined;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          id={id ?? field?.id}
          disabled={disabled}
          aria-invalid={hasError || undefined}
          className={calendarTriggerClass(Boolean(value), hasError, className)}
        >
          <span>{value ? formatDate(value) : placeholder}</span>
          <CalendarDays size={16} className="shrink-0 text-text-muted" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-auto p-0">
        <CalendarBase
          mode="single"
          selected={selected}
          defaultMonth={selected}
          disabled={minDate ? { before: dayjs(minDate).toDate() } : undefined}
          onSelect={(d) => {
            onChange(d ? dayjs(d).format('YYYY-MM-DD') : undefined);
            setOpen(false);
          }}
        />
      </PopoverContent>
    </Popover>
  );
}

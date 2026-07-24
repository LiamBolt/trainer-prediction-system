/* eslint-disable react-refresh/only-export-components -- variants/hooks are intentionally co-located with their component; this rule only affects dev-time Fast Refresh. */
import { createContext, useContext, useId } from 'react';
import { cn } from '@/lib/cn';

/**
 * Field primitives — Label / HelpText / FieldError / FormField / FormSection.
 * Spacing follows §5.2: label 6px above its control, help 6px below,
 * field groups 20px apart. FormField wires ids + aria automatically.
 */

interface FieldCtx {
  id: string;
  errorId: string;
  helpId: string;
  hasError: boolean;
  hasHelp: boolean;
}
const FieldContext = createContext<FieldCtx | null>(null);

export function useField(): FieldCtx | null {
  return useContext(FieldContext);
}

export function Label({
  className,
  required,
  children,
  ...props
}: React.LabelHTMLAttributes<HTMLLabelElement> & { required?: boolean }) {
  const field = useField();
  return (
    <label
      htmlFor={field?.id}
      className={cn('block text-body-sm font-semibold text-ink', className)}
      {...props}
    >
      {children}
      {required && (
        <span className="ml-1 text-danger-fg" aria-hidden="true">
          *
        </span>
      )}
    </label>
  );
}

export function HelpText({ className, children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  const field = useField();
  return (
    <p
      id={field?.helpId}
      className={cn('mt-1.5 text-body-sm text-text-muted', className)}
      {...props}
    >
      {children}
    </p>
  );
}

export function FieldError({ className, children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  const field = useField();
  if (!children) return null;
  return (
    <p
      id={field?.errorId}
      role="alert"
      className={cn('mt-1.5 text-body-sm font-medium text-danger-fg', className)}
      {...props}
    >
      {children}
    </p>
  );
}

export interface FormFieldProps {
  label?: React.ReactNode;
  required?: boolean;
  error?: string;
  help?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

/** Composes label + control + error + help with the exact spacing from §5.2. */
export function FormField({ label, required, error, help, className, children }: FormFieldProps) {
  const base = useId();
  const ctx: FieldCtx = {
    id: `${base}-control`,
    errorId: `${base}-error`,
    helpId: `${base}-help`,
    hasError: Boolean(error),
    hasHelp: Boolean(help),
  };
  return (
    <FieldContext.Provider value={ctx}>
      <div className={cn('flex flex-col', className)}>
        {label && (
          <div className="mb-1.5">
            <Label required={required}>{label}</Label>
          </div>
        )}
        {children}
        {error ? <FieldError>{error}</FieldError> : help ? <HelpText>{help}</HelpText> : null}
      </div>
    </FieldContext.Provider>
  );
}

export function FormSection({
  title,
  description,
  className,
  children,
}: {
  title?: string;
  description?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={cn('flex flex-col gap-5', className)}>
      {(title || description) && (
        <div className="flex flex-col gap-1">
          {title && <h3 className="text-h3 text-ink">{title}</h3>}
          {description && <p className="text-body-sm text-text-muted">{description}</p>}
        </div>
      )}
      <div className="flex flex-col gap-5">{children}</div>
    </section>
  );
}

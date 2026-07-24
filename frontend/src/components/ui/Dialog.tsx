import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { cn } from '@/lib/cn';

/**
 * Dialog — glass panel + glass backdrop (allowed per §4.5). Modal padding 24px;
 * footer separated by a hairline with 20px above and below (§5.2). Focus is
 * trapped and returned to the trigger by Radix (§14.1).
 */
export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({
  className,
  children,
  showClose = true,
  size = 'md',
  ...props
}: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
  showClose?: boolean;
  size?: 'sm' | 'md' | 'lg';
}) {
  const width = { sm: 'max-w-md', md: 'max-w-lg', lg: 'max-w-2xl' }[size];
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay
        className={cn(
          'fixed inset-0 z-50 bg-overlay backdrop-blur-sm',
          'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
        )}
      />
      {/* Full-screen centring layer; the padded gutter falls through to the overlay to close. */}
      <DialogPrimitive.Content
        className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center p-4"
        {...props}
      >
        <div
          className={cn(
            'glass pointer-events-auto relative w-full rounded-lg shadow-e3',
            width,
            'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 ' +
              'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 duration-panel',
            className,
          )}
        >
          {children}
          {showClose && (
            <DialogPrimitive.Close
              className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-sm text-text-muted transition-colors hover:bg-surface-sunken hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
              aria-label="Close"
            >
              <X size={16} className="shrink-0" />
            </DialogPrimitive.Close>
          )}
        </div>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export function DialogHeader({ className, children }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex flex-col gap-1 p-6 pb-4', className)}>{children}</div>;
}

export function DialogTitle({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title className={cn('pr-8 text-h2 text-ink', className)} {...props}>
      {children}
    </DialogPrimitive.Title>
  );
}

export function DialogDescription({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      className={cn('text-body text-text-secondary', className)}
      {...props}
    >
      {children}
    </DialogPrimitive.Description>
  );
}

export function DialogBody({ className, children }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('px-6 py-2', className)}>{children}</div>;
}

export function DialogFooter({ className, children }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'mt-5 flex items-center justify-end gap-3 border-t border-hairline px-6 pb-6 pt-5',
        className,
      )}
    >
      {children}
    </div>
  );
}

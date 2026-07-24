import * as TabsPrimitive from '@radix-ui/react-tabs';
import { cn } from '@/lib/cn';

/** Tabs — underline register. Active tab carries a 2px brand underline. */
export const Tabs = TabsPrimitive.Root;

export function TabsList({
  className,
  ...props
}: React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn('flex items-center gap-1 border-b border-hairline', className)}
      {...props}
    />
  );
}

export function TabsTrigger({
  className,
  ...props
}: React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        'relative -mb-px inline-flex h-10 items-center whitespace-nowrap border-b-2 border-transparent px-3 text-body font-medium text-text-muted transition-colors duration-default ' +
          'hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ' +
          'data-[state=active]:border-brand data-[state=active]:text-ink',
        className,
      )}
      {...props}
    />
  );
}

export function TabsContent({
  className,
  ...props
}: React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      className={cn(
        'mt-6 focus-visible:outline-none data-[state=inactive]:hidden data-[state=active]:animate-in data-[state=active]:fade-in-0',
        className,
      )}
      {...props}
    />
  );
}

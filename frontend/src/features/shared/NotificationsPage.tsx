import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BellOff, CheckCheck } from 'lucide-react';
import { cn } from '@/lib/cn';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Button,
  Card,
  CardBody,
  EmptyState,
  ErrorState,
  Select,
  Skeleton,
  Badge,
} from '@/components/ui';
import { notificationsApi } from '@/api/endpoints';
import { useAuth } from '@/hooks/useAuth';
import { formatRelative } from '@/lib/format';
import type { NotificationType } from '@/types/domain';

const TYPES: NotificationType[] = ['ASSIGNMENT', 'APPROVAL', 'EVALUATION', 'SYSTEM', 'REMINDER'];
const label = (t: string) => t.charAt(0) + t.slice(1).toLowerCase();

export function NotificationsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [type, setType] = useState('');

  const query = useQuery({
    queryKey: ['notifications', user?.userId],
    queryFn: () => notificationsApi.listNotifications(user?.userId),
    enabled: Boolean(user),
  });

  const markAll = useMutation({
    mutationFn: () => notificationsApi.markAllNotificationsRead(user?.userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  });
  const markOne = useMutation({
    mutationFn: (id: number) => notificationsApi.markNotificationRead(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  });

  const items = (query.data ?? []).filter((n) => !type || n.type === type);
  const unread = (query.data ?? []).filter((n) => n.status === 'UNREAD').length;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Shared"
        title="Notifications"
        description={unread > 0 ? `${unread} unread` : 'You are up to date.'}
        actions={
          unread > 0 ? (
            <Button
              variant="secondary"
              onClick={() => markAll.mutate()}
              loading={markAll.isPending}
              icon={<CheckCheck size={16} className="shrink-0" />}
            >
              Mark all read
            </Button>
          ) : undefined
        }
      />

      <div className="w-full sm:w-56">
        <Select
          value={type}
          onValueChange={(v) => setType(v === 'all' ? '' : v)}
          options={[{ value: 'all', label: 'All types' }, ...TYPES.map((t) => ({ value: t, label: label(t) }))]}
          placeholder="Type"
          aria-label="Filter by type"
        />
      </div>

      {query.isLoading ? (
        <Skeleton className="h-80 rounded-md" />
      ) : query.isError ? (
        <Card>
          <CardBody>
            <ErrorState onRetry={() => query.refetch()} />
          </CardBody>
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <CardBody>
            <EmptyState
              icon={<BellOff size={20} className="shrink-0" />}
              title="No notifications"
              description="You will be notified about assignments, approvals, and evaluations here."
            />
          </CardBody>
        </Card>
      ) : (
        <Card>
          <CardBody className="p-0">
            <ul className="flex flex-col divide-y divide-hairline">
              {items.map((n) => (
                <li key={n.notificationId} className="flex items-start gap-3 px-4 py-4 md:px-6">
                  <span
                    className={cn('mt-2 h-2 w-2 shrink-0 rounded-full', n.status === 'UNREAD' ? 'bg-brand' : 'bg-transparent')}
                    aria-hidden="true"
                  />
                  <span className="flex min-w-0 flex-1 flex-col gap-1">
                    <span className="text-body text-ink">{n.message}</span>
                    <span className="flex flex-wrap items-center gap-2">
                      <Badge tone="neutral" dot={false}>
                        {label(n.type)}
                      </Badge>
                      <span className="font-mono text-label text-text-muted">{formatRelative(n.sentDate)}</span>
                      {n.status === 'UNREAD' && (
                        <button
                          type="button"
                          onClick={() => markOne.mutate(n.notificationId)}
                          className="text-body-sm text-brand hover:underline"
                        >
                          Mark read
                        </button>
                      )}
                    </span>
                  </span>
                  {n.linkTo && (
                    <Button asChild variant="ghost" size="sm">
                      <Link to={n.linkTo}>Open</Link>
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}
    </div>
  );
}

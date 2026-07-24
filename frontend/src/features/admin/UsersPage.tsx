import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createColumnHelper } from '@tanstack/react-table';
import { MoreHorizontal, Plus } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { DataTable } from '@/components/table/DataTable';
import {
  Button,
  Card,
  CardBody,
  ConfirmDialog,
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  FormField,
  IconButton,
  Input,
  Select,
  StatusBadge,
  toast,
} from '@/components/ui';
import { usersApi } from '@/api/endpoints';
import { ROLE_LABELS } from '@/lib/constants';
import { formatDate } from '@/lib/format';
import type { RoleName, User } from '@/types/domain';

const col = createColumnHelper<User>();
const ROLES: RoleName[] = ['TRAINING_ADMINISTRATOR', 'TRAINING_OFFICER', 'TRAINER', 'SYSTEM_ADMINISTRATOR'];

/** Users and roles (FR-12). Create, edit, deactivate, assign role. A deactivated
 *  account cannot sign in; a role change takes effect at next sign-in. */
export function UsersPage() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [deactivating, setDeactivating] = useState<User | null>(null);
  const [form, setForm] = useState({ username: '', fullName: '', email: '', role: 'TRAINER' as RoleName });

  const query = useQuery({ queryKey: ['users'], queryFn: () => usersApi.listUsers() });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['users'] });

  const createUser = useMutation({
    mutationFn: () => usersApi.createUser(form),
    onSuccess: () => {
      invalidate();
      setCreateOpen(false);
      setForm({ username: '', fullName: '', email: '', role: 'TRAINER' });
      toast.success('User created', { description: 'They can sign in with the initial password.' });
    },
    onError: () => toast.error('Could not create the user.'),
  });

  const updateUser = useMutation({
    mutationFn: (args: { userId: number; body: Parameters<typeof usersApi.updateUser>[1] }) =>
      usersApi.updateUser(args.userId, args.body),
    onSuccess: () => {
      invalidate();
      setDeactivating(null);
      toast.success('User updated');
    },
    onError: () => toast.error('Could not update the user.'),
  });

  const columns = useMemo(
    () => [
      col.accessor('fullName', {
        header: 'Name',
        cell: (c) => <span className="font-medium text-ink">{c.getValue()}</span>,
      }),
      col.accessor('username', {
        header: 'Username',
        cell: (c) => <span className="font-mono text-data">{c.getValue()}</span>,
      }),
      col.accessor('email', { header: 'Email' }),
      col.accessor('role', {
        header: 'Role',
        cell: (c) => ROLE_LABELS[c.getValue()],
      }),
      col.accessor('accountStatus', {
        header: 'Status',
        cell: (c) => <StatusBadge kind="account" value={c.getValue()} />,
      }),
      col.accessor('lastLoginAt', {
        header: 'Last sign-in',
        cell: (c) => (
          <span className="font-mono text-data tabular-nums">
            {c.getValue() ? formatDate(c.getValue()!) : 'Never'}
          </span>
        ),
      }),
      col.display({
        id: 'actions',
        header: '',
        cell: (c) => (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <IconButton label={`Actions for ${c.row.original.fullName}`} variant="ghost" size="sm">
                <MoreHorizontal size={16} className="shrink-0" />
              </IconButton>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              {ROLES.filter((r) => r !== c.row.original.role).map((r) => (
                <DropdownMenuItem
                  key={r}
                  onSelect={() => updateUser.mutate({ userId: c.row.original.userId, body: { role: r } })}
                >
                  Change role to {ROLE_LABELS[r]}
                </DropdownMenuItem>
              ))}
              {c.row.original.accountStatus !== 'DEACTIVATED' ? (
                <DropdownMenuItem tone="danger" onSelect={() => setDeactivating(c.row.original)}>
                  Deactivate account
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem
                  onSelect={() => updateUser.mutate({ userId: c.row.original.userId, body: { accountStatus: 'ACTIVE' } })}
                >
                  Reactivate account
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        ),
      }),
    ],
    [updateUser],
  );

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Administration"
        title="Users and roles"
        description="Accounts are created here — there is no self-registration anywhere in the system."
        actions={
          <Button onClick={() => setCreateOpen(true)} icon={<Plus size={16} className="shrink-0" />}>
            Create user
          </Button>
        }
      />

      <Card>
        <CardBody>
          <p className="text-body-sm text-text-muted">
            A role change takes effect at the user’s next sign-in. A deactivated account cannot sign
            in at all.
          </p>
        </CardBody>
      </Card>

      <DataTable
        columns={columns as never}
        data={query.data ?? []}
        isLoading={query.isLoading}
        isError={query.isError}
        onRetry={() => query.refetch()}
        getRowId={(u) => String(u.userId)}
        empty={{ title: 'No users', description: 'Create the first account to get started.' }}
      />

      {/* Create user */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent size="md">
          <DialogHeader>
            <DialogTitle>Create user</DialogTitle>
            <DialogDescription>
              The account is created with an initial password issued by ICT RP&amp;I.
            </DialogDescription>
          </DialogHeader>
          <DialogBody>
            <div className="flex flex-col gap-5">
              <FormField label="Full name" required>
                <Input
                  value={form.fullName}
                  onChange={(e) => setForm((f) => ({ ...f, fullName: e.target.value }))}
                  placeholder="e.g. ASP Joseph Okello"
                />
              </FormField>
              <FormField label="Username" required>
                <Input
                  value={form.username}
                  onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
                  placeholder="e.g. joseph.okello"
                  className="font-mono"
                />
              </FormField>
              <FormField label="Email" required>
                <Input
                  value={form.email}
                  onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  placeholder="joseph.okello@upf.go.ug"
                />
              </FormField>
              <FormField label="Role" required help="Determines which screens and actions are available.">
                <Select
                  value={form.role}
                  onValueChange={(v) => setForm((f) => ({ ...f, role: v as RoleName }))}
                  options={ROLES.map((r) => ({ value: r, label: ROLE_LABELS[r] }))}
                />
              </FormField>
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => createUser.mutate()}
              loading={createUser.isPending}
              disabled={!form.fullName || !form.username || !form.email}
            >
              Create user
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deactivating)}
        onOpenChange={(o) => !o && setDeactivating(null)}
        title="Deactivate this account?"
        description={`${deactivating?.fullName ?? ''} will be unable to sign in. This can be reversed later.`}
        confirmLabel="Deactivate"
        tone="danger"
        loading={updateUser.isPending}
        onConfirm={() => {
          if (deactivating) {
            updateUser.mutate({ userId: deactivating.userId, body: { accountStatus: 'DEACTIVATED' } });
          }
        }}
      />
    </div>
  );
}

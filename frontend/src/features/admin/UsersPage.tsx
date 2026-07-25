import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createColumnHelper } from '@tanstack/react-table';
import { Copy, KeyRound, MoreHorizontal, Plus } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { DataTable } from '@/components/table/DataTable';
import { FilterBar } from '@/components/table/FilterBar';
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
  Pagination,
  Select,
  StatusBadge,
  toast,
} from '@/components/ui';
import { usersApi } from '@/api/endpoints';
import { useDebounce } from '@/hooks/useDebounce';
import { ROLE_LABELS } from '@/lib/constants';
import { formatDate } from '@/lib/format';
import type { RoleName, User } from '@/types/domain';

const col = createColumnHelper<User>();
const ROLES: RoleName[] = ['TRAINING_ADMINISTRATOR', 'TRAINING_OFFICER', 'TRAINER', 'SYSTEM_ADMINISTRATOR'];

/** Pull a human-readable message out of an axios error, falling back to a default. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function serverMessage(error: any, fallback: string): string {
  return error?.response?.data?.detail ?? error?.response?.data?.message ?? fallback;
}

type Issued = { title: string; username: string; password: string; message: string };

/** Users and roles (FR-12). Create, edit, deactivate, reset password/unlock, assign role.
 *  A deactivated account cannot sign in; a role change takes effect at next sign-in. */
export function UsersPage() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [deactivating, setDeactivating] = useState<User | null>(null);
  const [resetting, setResetting] = useState<User | null>(null);
  const [issued, setIssued] = useState<Issued | null>(null);
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState('');
  const search = useDebounce(searchInput, 300);
  const [form, setForm] = useState({ username: '', fullName: '', email: '', role: 'TRAINING_OFFICER' as RoleName });

  const query = useQuery({
    queryKey: ['users', { search, page }],
    queryFn: () => usersApi.listUsers({ search: search || undefined, page }),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['users'] });

  const copy = (text: string) => {
    navigator.clipboard?.writeText(text).then(
      () => toast.success('Copied to clipboard'),
      () => toast.error('Could not copy'),
    );
  };

  const createUser = useMutation({
    mutationFn: () => usersApi.createUser(form),
    onSuccess: (created) => {
      invalidate();
      setCreateOpen(false);
      setIssued({
        title: 'User created',
        username: created.user.username,
        password: created.temporaryPassword,
        message: created.message,
      });
      setForm({ username: '', fullName: '', email: '', role: 'TRAINING_OFFICER' });
    },
    onError: (e) => toast.error(serverMessage(e, 'Could not create the user.')),
  });

  const resetPassword = useMutation({
    mutationFn: (u: User) => usersApi.resetPassword(u.userId),
    onSuccess: (reset, u) => {
      invalidate();
      setResetting(null);
      setIssued({
        title: `Password reset for ${u.fullName}`,
        username: u.username,
        password: reset.temporaryPassword,
        message: reset.message,
      });
    },
    onError: (e) => toast.error(serverMessage(e, 'Could not reset the password.')),
  });

  const updateUser = useMutation({
    mutationFn: (args: { userId: number; body: Parameters<typeof usersApi.updateUser>[1] }) =>
      usersApi.updateUser(args.userId, args.body),
    onSuccess: () => {
      invalidate();
      setDeactivating(null);
      toast.success('User updated');
    },
    onError: (e) => toast.error(serverMessage(e, 'Could not update the user.')),
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
              <DropdownMenuItem onSelect={() => setResetting(c.row.original)}>
                Reset password / unlock
              </DropdownMenuItem>
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
            in at all. Forgotten password or locked out? Use <span className="font-medium text-ink">Reset
            password / unlock</span> — it issues a fresh one-time password and clears the lock.
          </p>
        </CardBody>
      </Card>

      <FilterBar
        search={searchInput}
        onSearchChange={(v) => {
          setSearchInput(v);
          setPage(1);
        }}
        searchPlaceholder="Search by name, username, or email…"
        hasActiveFilters={Boolean(search)}
        onClear={() => {
          setSearchInput('');
          setPage(1);
        }}
      />

      <DataTable
        columns={columns as never}
        data={query.data?.items ?? []}
        isLoading={query.isLoading}
        isError={query.isError}
        onRetry={() => query.refetch()}
        getRowId={(u) => String(u.userId)}
        empty={{ title: 'No users match', description: 'Try a different search, or create an account.' }}
      />

      {query.data && query.data.pageCount > 1 && (
        <Pagination
          page={query.data.page}
          pageCount={query.data.pageCount}
          total={query.data.total}
          pageSize={query.data.pageSize}
          onPageChange={setPage}
        />
      )}

      {/* Create user */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent size="md">
          <DialogHeader>
            <DialogTitle>Create user</DialogTitle>
            <DialogDescription>
              The account is created with a generated one-time password, shown to you once. Give it
              to the user — they must change it at first sign-in. (No email is sent.)
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
              <FormField
                label="Role"
                required
                help="Determines which screens and actions are available. Trainer accounts also need a posting and are created from the Trainer directory."
              >
                <Select
                  value={form.role}
                  onValueChange={(v) => setForm((f) => ({ ...f, role: v as RoleName }))}
                  options={ROLES.filter((r) => r !== 'TRAINER').map((r) => ({ value: r, label: ROLE_LABELS[r] }))}
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

      {/* One-time credentials — shown after create or reset */}
      <Dialog open={Boolean(issued)} onOpenChange={(o) => !o && setIssued(null)}>
        <DialogContent size="md">
          <DialogHeader>
            <DialogTitle>
              <span className="flex items-center gap-2">
                <KeyRound size={18} className="shrink-0 text-brand" />
                {issued?.title}
              </span>
            </DialogTitle>
            <DialogDescription>{issued?.message}</DialogDescription>
          </DialogHeader>
          <DialogBody>
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between rounded-sm border border-hairline bg-surface-sunken px-3 py-2">
                <span className="font-mono text-label uppercase text-text-muted">Username</span>
                <span className="font-mono text-data text-ink">{issued?.username}</span>
              </div>
              <div className="flex items-center justify-between gap-2 rounded-sm border border-hairline bg-surface-sunken px-3 py-2">
                <span className="font-mono text-label uppercase text-text-muted">Temporary password</span>
                <span className="flex items-center gap-2">
                  <span className="select-all font-mono text-data-lg font-semibold text-ink">{issued?.password}</span>
                  <IconButton label="Copy password" size="sm" variant="ghost" onClick={() => issued && copy(issued.password)}>
                    <Copy size={16} className="shrink-0" />
                  </IconButton>
                </span>
              </div>
              <p className="text-body-sm text-warning-fg">
                This password is shown once and cannot be retrieved again. Copy it now and give it to
                the user through a channel you trust.
              </p>
            </div>
          </DialogBody>
          <DialogFooter>
            <Button
              variant="secondary"
              onClick={() => issued && copy(`${issued.username} / ${issued.password}`)}
              icon={<Copy size={16} className="shrink-0" />}
            >
              Copy both
            </Button>
            <Button onClick={() => setIssued(null)}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={Boolean(resetting)}
        onOpenChange={(o) => !o && setResetting(null)}
        title="Reset this user’s password?"
        description={`${resetting?.fullName ?? ''} will get a new one-time password, any lockout is cleared, and all their sessions are signed out. You will see the new password once.`}
        confirmLabel="Reset password"
        loading={resetPassword.isPending}
        onConfirm={() => {
          if (resetting) resetPassword.mutate(resetting);
        }}
      />

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

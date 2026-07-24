import { Link, useRouteError } from 'react-router-dom';
import { ShieldX, FileQuestion, ServerCrash, RotateCw } from 'lucide-react';
import { Button } from '@/components/ui';
import { Crest } from '@/components/brand/Crest';
import { useAuth } from '@/hooks/useAuth';
import { ROLE_LABELS, ORG_UNIT } from '@/lib/constants';

function ErrorFrame({
  icon,
  code,
  title,
  children,
  actions,
}: {
  icon: React.ReactNode;
  code: string;
  title: string;
  children: React.ReactNode;
  actions: React.ReactNode;
}) {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-canvas px-4 text-center">
      <Crest size={48} className="text-brand" />
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-surface-sunken text-text-muted">
        {icon}
      </div>
      <div className="flex flex-col gap-2">
        <span className="font-mono text-label uppercase text-text-muted">Error {code}</span>
        <h1 className="text-h1 text-ink">{title}</h1>
        <div className="mx-auto max-w-md text-body text-text-muted">{children}</div>
      </div>
      <div className="flex flex-wrap items-center justify-center gap-3">{actions}</div>
    </div>
  );
}

/** /403 — states the user's role and what it can reach (§11.1). */
export function NotAuthorised() {
  const { role } = useAuth();
  return (
    <ErrorFrame
      icon={<ShieldX size={24} className="shrink-0" />}
      code="403"
      title="Not authorised"
      actions={
        <Button asChild>
          <Link to="/dashboard">Back to dashboard</Link>
        </Button>
      }
    >
      {role ? (
        <>
          You are signed in as a <span className="font-semibold text-ink">{ROLE_LABELS[role]}</span>.
          This area is reserved for other roles. Use the navigation to reach the screens available to
          you.
        </>
      ) : (
        <>You do not have permission to view this page.</>
      )}
    </ErrorFrame>
  );
}

export function NotFound() {
  return (
    <ErrorFrame
      icon={<FileQuestion size={24} className="shrink-0" />}
      code="404"
      title="Page not found"
      actions={
        <Button asChild>
          <Link to="/dashboard">Back to dashboard</Link>
        </Button>
      }
    >
      The page you were looking for does not exist or may have moved.
    </ErrorFrame>
  );
}

/** /500 — retry plus report to ICT RP&I (§11.1). Also the router errorElement. */
export function SystemError() {
  const error = useRouteError();
  return (
    <ErrorFrame
      icon={<ServerCrash size={24} className="shrink-0" />}
      code="500"
      title="Something went wrong"
      actions={
        <>
          <Button icon={<RotateCw size={16} className="shrink-0" />} onClick={() => window.location.reload()}>
            Try again
          </Button>
          <Button asChild variant="secondary">
            <Link to="/dashboard">Back to dashboard</Link>
          </Button>
        </>
      }
    >
      A system error occurred. If it persists, report it to {ORG_UNIT}.
      {import.meta.env.DEV && error instanceof Error && (
        <span className="mt-3 block font-mono text-label text-danger-fg">{error.message}</span>
      )}
    </ErrorFrame>
  );
}

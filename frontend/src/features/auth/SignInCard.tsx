import { useEffect, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Eye, EyeOff, Lock, ShieldAlert } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Button, FormField, Input } from '@/components/ui';
import { Wordmark } from '@/components/brand/Wordmark';
import { NeedAccessDialog } from './NeedAccessDialog';
import { DemoAccounts } from './DemoAccounts';
import { loginSchema, type LoginForm } from '@/schemas/auth';
import { useAuth } from '@/hooks/useAuth';

/** Persisted lockouts so the countdown survives a reload (§13.2). */
const LOCKOUT_KEY = 'tps-lockouts';
function readLockout(username: string): string | null {
  try {
    const map = JSON.parse(localStorage.getItem(LOCKOUT_KEY) ?? '{}') as Record<string, string>;
    return map[username.toLowerCase()] ?? null;
  } catch {
    return null;
  }
}
function writeLockout(username: string, unlockAt: string | null): void {
  try {
    const map = JSON.parse(localStorage.getItem(LOCKOUT_KEY) ?? '{}') as Record<string, string>;
    if (unlockAt) map[username.toLowerCase()] = unlockAt;
    else delete map[username.toLowerCase()];
    localStorage.setItem(LOCKOUT_KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

function countdown(unlockAt: string, now: number): string {
  const remaining = Math.max(0, Math.floor((new Date(unlockAt).getTime() - now) / 1000));
  const mm = String(Math.floor(remaining / 60)).padStart(2, '0');
  const ss = String(remaining % 60).padStart(2, '0');
  return `${mm}:${ss}`;
}

export function SignInCard({
  expired = false,
  onSuccess,
}: {
  expired?: boolean;
  onSuccess: () => void;
}) {
  const { signIn } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [lockedUntil, setLockedUntil] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const [shaking, setShaking] = useState(false);
  const [needAccessOpen, setNeedAccessOpen] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  const form = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    mode: 'onBlur',
    defaultValues: { username: '', password: '' },
  });
  const username = form.watch('username');

  // Restore a persisted lockout for the entered username.
  useEffect(() => {
    const stored = username ? readLockout(username) : null;
    if (stored && new Date(stored).getTime() > Date.now()) setLockedUntil(stored);
    else if (!stored) setLockedUntil(null);
  }, [username]);

  // Tick the countdown while locked.
  useEffect(() => {
    if (!lockedUntil) return;
    const id = setInterval(() => {
      const t = Date.now();
      setNow(t);
      if (new Date(lockedUntil).getTime() <= t) {
        writeLockout(username, null);
        setLockedUntil(null);
      }
    }, 1000);
    return () => clearInterval(id);
  }, [lockedUntil, username]);

  const triggerShake = () => {
    setShaking(true);
  };

  const onSubmit = form.handleSubmit(async (values) => {
    setServerError(null);
    const result = await signIn(values.username, values.password);
    switch (result.outcome) {
      case 'SUCCESS':
        onSuccess();
        break;
      case 'INVALID':
        setServerError(
          `Incorrect username or password. ${result.attemptsRemaining} attempt${
            result.attemptsRemaining === 1 ? '' : 's'
          } remaining before this account is locked.`,
        );
        triggerShake();
        break;
      case 'LOCKED':
        writeLockout(values.username, result.unlockAt);
        setLockedUntil(result.unlockAt);
        break;
      case 'DEACTIVATED':
        setServerError('This account has been deactivated. Contact your System Administrator.');
        triggerShake();
        break;
    }
  });

  const fill = (u: string, p: string) => {
    form.setValue('username', u);
    form.setValue('password', p);
    setServerError(null);
  };

  const isLocked = Boolean(lockedUntil && new Date(lockedUntil).getTime() > now);

  return (
    <div
      ref={cardRef}
      onAnimationEnd={() => setShaking(false)}
      className={cn(
        'glass w-full max-w-card rounded-lg p-8 shadow-e3',
        shaking && 'animate-shake',
      )}
    >
      <div className="mb-6 flex flex-col gap-4">
        <Wordmark variant="full" className="text-ink" />
        <div className="flex flex-col gap-1">
          <span className="font-mono text-label uppercase text-text-muted">Secure access</span>
          <h1 className="text-h2 text-ink">Sign in</h1>
        </div>
      </div>

      {expired && (
        <div className="mb-4 rounded-sm border border-info-border bg-info-bg px-3 py-2 text-body-sm text-info-fg" role="status">
          Your session ended. Sign in to continue.
        </div>
      )}

      {isLocked && lockedUntil ? (
        <div className="flex flex-col gap-3 rounded-sm border border-danger-border bg-danger-bg p-4" role="alert" aria-live="polite">
          <div className="flex items-center gap-2 text-danger-fg">
            <Lock size={16} className="shrink-0" />
            <span className="text-body font-semibold">Account temporarily locked</span>
          </div>
          <p className="text-body-sm text-text-secondary">
            Too many failed attempts. Try again in{' '}
            <span className="font-mono text-data font-semibold text-danger-fg tabular-nums">
              {countdown(lockedUntil, now)}
            </span>
            , or contact your System Administrator.
          </p>
        </div>
      ) : (
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
          <FormField label="Username" error={form.formState.errors.username?.message}>
            <Input
              {...form.register('username')}
              autoComplete="username"
              autoFocus
              placeholder="e.g. officer.training"
              invalid={Boolean(form.formState.errors.username)}
            />
          </FormField>

          <FormField label="Password" error={form.formState.errors.password?.message}>
            <Input
              {...form.register('password')}
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              placeholder="Enter your password"
              invalid={Boolean(form.formState.errors.password)}
              trailing={
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="pointer-events-auto flex h-8 w-8 items-center justify-center rounded-sm text-text-muted hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
                >
                  {showPassword ? <EyeOff size={16} className="shrink-0" /> : <Eye size={16} className="shrink-0" />}
                </button>
              }
            />
          </FormField>

          {serverError && (
            <div className="flex items-start gap-2 rounded-sm border border-danger-border bg-danger-bg px-3 py-2 text-body-sm text-danger-fg" role="alert" aria-live="polite">
              <ShieldAlert size={16} className="mt-0.5 shrink-0" />
              <span>{serverError}</span>
            </div>
          )}

          <Button type="submit" size="lg" loading={form.formState.isSubmitting} className="w-full">
            Sign in
          </Button>

          <div className="flex justify-center">
            <button
              type="button"
              onClick={() => setNeedAccessOpen(true)}
              className="text-body-sm text-brand transition-colors hover:underline"
            >
              Need access?
            </button>
          </div>

          <DemoAccounts onFill={fill} />
        </form>
      )}

      <NeedAccessDialog open={needAccessOpen} onOpenChange={setNeedAccessOpen} />
    </div>
  );
}

import { useState } from 'react';
import { ChevronDown, KeyRound } from 'lucide-react';
import { cn } from '@/lib/cn';
import { DEMO_PASSWORD } from '@/hooks/useAuth';

/**
 * DemoAccounts — a collapsed disclosure of the four seeded accounts (§8.9),
 * rendered ONLY when VITE_USE_MOCKS === 'true'. One-click fill on each row.
 */
const ACCOUNTS = [
  { role: 'Training Administrator', username: 'admin.training', name: 'SSP Grace Nabirye' },
  { role: 'Training Officer', username: 'officer.training', name: 'ASP Joseph Okello' },
  { role: 'Trainer', username: 'trainer', name: 'IP Sarah Mugisha' },
  { role: 'System Administrator', username: 'sysadmin', name: 'SP Denis Byaruhanga' },
];

export function DemoAccounts({ onFill }: { onFill: (username: string, password: string) => void }) {
  const [open, setOpen] = useState(false);
  if (import.meta.env.VITE_USE_MOCKS !== 'true') return null;

  return (
    <div className="rounded-sm border border-hairline">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-3 py-2 text-left font-mono text-label uppercase text-text-muted transition-colors hover:text-ink"
      >
        <KeyRound size={14} className="shrink-0" />
        <span className="flex-1">Demo accounts</span>
        <ChevronDown size={14} className={cn('shrink-0 transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <ul className="border-t border-hairline">
          {ACCOUNTS.map((a) => (
            <li key={a.username} className="border-b border-hairline last:border-b-0">
              <button
                type="button"
                onClick={() => onFill(a.username, DEMO_PASSWORD)}
                className="flex w-full flex-col gap-0.5 px-3 py-2 text-left transition-colors hover:bg-surface-sunken"
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="text-body-sm font-medium text-ink">{a.role}</span>
                  <span className="font-mono text-label text-brand">Use</span>
                </span>
                <span className="font-mono text-label text-text-muted">
                  {a.username} · {a.name}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

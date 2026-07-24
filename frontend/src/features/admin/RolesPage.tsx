import { Check, Minus } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardBody } from '@/components/ui';
import { ROLE_LABELS } from '@/lib/constants';
import type { RoleName } from '@/types/domain';

/**
 * Roles (§11.10) — the four SRS roles as a read-only permission matrix. It exists
 * to teach new staff what each role can do.
 */
const ROLES: RoleName[] = [
  'TRAINING_OFFICER',
  'TRAINING_ADMINISTRATOR',
  'TRAINER',
  'SYSTEM_ADMINISTRATOR',
];

const CAPABILITIES: { label: string; requirement: string; roles: RoleName[] }[] = [
  { label: 'Raise a training request', requirement: 'FR-04', roles: ['TRAINING_OFFICER', 'TRAINING_ADMINISTRATOR'] },
  { label: 'Define course requirements', requirement: 'FR-05', roles: ['TRAINING_OFFICER', 'TRAINING_ADMINISTRATOR'] },
  { label: 'Run a prediction', requirement: 'FR-06', roles: ['TRAINING_OFFICER', 'TRAINING_ADMINISTRATOR'] },
  { label: 'View ranked recommendations', requirement: 'FR-07', roles: ['TRAINING_OFFICER', 'TRAINING_ADMINISTRATOR'] },
  { label: 'Tune weights in the Weight Studio', requirement: 'D6', roles: ['TRAINING_ADMINISTRATOR'] },
  { label: 'Approve an allocation', requirement: 'FR-08 / BR-06', roles: ['TRAINING_ADMINISTRATOR'] },
  { label: 'Promote the next-ranked candidate', requirement: 'FR-08', roles: ['TRAINING_ADMINISTRATOR'] },
  { label: 'Accept or decline an assignment', requirement: 'FR-09', roles: ['TRAINER'] },
  { label: 'Maintain own profile', requirement: 'FR-02', roles: ['TRAINER'] },
  { label: 'Maintain own qualifications', requirement: 'FR-03', roles: ['TRAINER'] },
  { label: 'Record a performance evaluation', requirement: 'FR-10', roles: ['TRAINING_ADMINISTRATOR'] },
  { label: 'Generate and export reports', requirement: 'FR-11', roles: ['TRAINING_ADMINISTRATOR'] },
  { label: 'Manage users and roles', requirement: 'FR-12', roles: ['SYSTEM_ADMINISTRATOR'] },
  { label: 'View the audit log', requirement: 'FR-13', roles: ['SYSTEM_ADMINISTRATOR'] },
  { label: 'Save scoring-policy weights', requirement: 'NFR-10', roles: ['SYSTEM_ADMINISTRATOR'] },
];

export function RolesPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Administration"
        title="Roles"
        description="What each of the four roles can do. This is a reference — permissions are enforced by the API."
      />

      <Card>
        <CardBody>
          <p className="text-body-sm text-text-muted">
            Hiding a control in the interface is a convenience, not a security boundary. Authorisation
            is enforced server-side (NFR-04).
          </p>
        </CardBody>
      </Card>

      <div className="overflow-hidden rounded-md border border-hairline bg-surface">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-hairline">
                <th className="px-6 py-3 text-left font-mono text-label uppercase text-text-muted">
                  Capability
                </th>
                <th className="px-4 py-3 text-left font-mono text-label uppercase text-text-muted">Ref.</th>
                {ROLES.map((r) => (
                  <th key={r} className="px-4 py-3 text-center font-mono text-label uppercase text-text-muted last:pr-6">
                    {ROLE_LABELS[r]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {CAPABILITIES.map((cap) => (
                <tr key={cap.label} className="border-b border-hairline last:border-b-0">
                  <td className="h-row whitespace-nowrap px-6 align-middle text-body text-ink">{cap.label}</td>
                  <td className="h-row whitespace-nowrap px-4 align-middle font-mono text-label text-text-muted">
                    {cap.requirement}
                  </td>
                  {ROLES.map((r) => {
                    const allowed = cap.roles.includes(r);
                    return (
                      <td key={r} className="h-row px-4 text-center align-middle last:pr-6">
                        {allowed ? (
                          <span className="inline-flex items-center justify-center text-success-fg">
                            <Check size={16} strokeWidth={3} className="shrink-0" />
                            <span className="sr-only">Allowed</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center justify-center text-text-disabled">
                            <Minus size={16} className="shrink-0" />
                            <span className="sr-only">Not allowed</span>
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

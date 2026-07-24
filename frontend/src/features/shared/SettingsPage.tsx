import { PageHeader } from '@/components/layout/PageHeader';
import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  KeyValueList,
  Switch,
  Tooltip,
} from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { useThemeStore } from '@/stores/themeStore';
import { useUiStore } from '@/stores/uiStore';
import { ROLE_LABELS } from '@/lib/constants';

/**
 * Settings (§11.11) — profile details, theme preference, the Plain language
 * toggle (§12.8, default on), and an accessibility section with a reduce-motion
 * override. Password change is issued by ICT RP&I (D3) — not self-service here.
 */
export function SettingsPage() {
  const { user, role } = useAuth();
  const { theme, setTheme } = useThemeStore();
  const { plainLanguage, setPlainLanguage, reduceMotion, setReduceMotion } = useUiStore();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader eyebrow="Shared" title="Settings" description="Your account and interface preferences." />

      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
        </CardHeader>
        <CardBody>
          <KeyValueList
            columns={2}
            items={[
              { label: 'Name', value: user?.fullName ?? '—' },
              { label: 'Username', value: user?.username ?? '—', mono: true },
              { label: 'Email', value: user?.email ?? '—' },
              {
                label: 'Role',
                value: role ? <Badge tone="info" dot={false}>{ROLE_LABELS[role]}</Badge> : '—',
              },
            ]}
          />
          <p className="mt-4 text-body-sm text-text-muted">
            Passwords are issued and reset by your System Administrator. Contact ICT Research,
            Planning &amp; Innovation if you need yours changed.
          </p>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
        </CardHeader>
        <CardBody>
          <label className="flex items-center justify-between gap-4">
            <span className="flex flex-col">
              <span className="text-body font-medium text-ink">Dark mode</span>
              <span className="text-body-sm text-text-muted">
                A navy-tinted dark theme for low-light control rooms.
              </span>
            </span>
            <Switch
              checked={theme === 'dark'}
              onCheckedChange={(checked) => setTheme(checked ? 'dark' : 'light')}
              aria-label="Dark mode"
            />
          </label>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Language and clarity</CardTitle>
        </CardHeader>
        <CardBody>
          <label className="flex items-center justify-between gap-4">
            <span className="flex flex-col">
              <span className="flex items-center gap-2 text-body font-medium text-ink">
                Plain language
                <Tooltip content="Swaps compact technical labels for fuller sentences — for example, the column header “Conf.” becomes “How much history we have”.">
                  <span className="font-mono text-label uppercase text-text-muted">What is this?</span>
                </Tooltip>
              </span>
              <span className="text-body-sm text-text-muted">
                Use fuller, non-technical wording throughout the system.
              </span>
            </span>
            <Switch checked={plainLanguage} onCheckedChange={setPlainLanguage} aria-label="Plain language" />
          </label>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Accessibility</CardTitle>
        </CardHeader>
        <CardBody>
          <label className="flex items-center justify-between gap-4">
            <span className="flex flex-col">
              <span className="text-body font-medium text-ink">Reduce motion</span>
              <span className="text-body-sm text-text-muted">
                Turns off the re-rank animation and other movement, regardless of your system setting.
              </span>
            </span>
            <Switch checked={reduceMotion} onCheckedChange={setReduceMotion} aria-label="Reduce motion" />
          </label>
        </CardBody>
      </Card>
    </div>
  );
}

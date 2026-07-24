import type { LucideIcon } from 'lucide-react';
import {
  LayoutDashboard,
  ClipboardList,
  ListChecks,
  ClipboardCheck,
  Users,
  UserCircle,
  CalendarCheck,
  Star,
  FileBarChart,
  ShieldCheck,
  ScrollText,
  Activity,
  SlidersHorizontal,
} from 'lucide-react';
import type { RoleName } from '@/types/domain';

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  roles: RoleName[];
  /** Match the route exactly (for index-like links). */
  end?: boolean;
}

export interface NavSection {
  heading: string;
  items: NavItem[];
}

const ALL: RoleName[] = [
  'TRAINING_ADMINISTRATOR',
  'TRAINING_OFFICER',
  'TRAINER',
  'SYSTEM_ADMINISTRATOR',
];

export const NAV_SECTIONS: NavSection[] = [
  {
    heading: 'Overview',
    items: [{ to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, roles: ALL, end: true }],
  },
  {
    heading: 'Training',
    items: [
      {
        to: '/programmes',
        label: 'Training requests',
        icon: ClipboardList,
        roles: ['TRAINING_ADMINISTRATOR', 'TRAINING_OFFICER', 'SYSTEM_ADMINISTRATOR'],
      },
      {
        to: '/allocations',
        label: 'Allocations',
        icon: ListChecks,
        roles: ['TRAINING_ADMINISTRATOR', 'TRAINING_OFFICER'],
      },
      {
        to: '/evaluations',
        label: 'Evaluations',
        icon: ClipboardCheck,
        roles: ['TRAINING_ADMINISTRATOR'],
      },
    ],
  },
  {
    heading: 'Trainers',
    items: [
      {
        to: '/trainers',
        label: 'Trainer directory',
        icon: Users,
        roles: ['TRAINING_ADMINISTRATOR', 'TRAINING_OFFICER', 'SYSTEM_ADMINISTRATOR'],
      },
      { to: '/my-assignments', label: 'My assignments', icon: CalendarCheck, roles: ['TRAINER'] },
      { to: '/my-profile', label: 'My profile', icon: UserCircle, roles: ['TRAINER'] },
      { to: '/my-performance', label: 'My performance', icon: Star, roles: ['TRAINER'] },
    ],
  },
  {
    heading: 'Insights',
    items: [{ to: '/reports', label: 'Reports', icon: FileBarChart, roles: ['TRAINING_ADMINISTRATOR'] }],
  },
  {
    heading: 'Administration',
    items: [
      { to: '/admin/users', label: 'Users and roles', icon: Users, roles: ['SYSTEM_ADMINISTRATOR'] },
      { to: '/admin/roles', label: 'Roles', icon: ShieldCheck, roles: ['SYSTEM_ADMINISTRATOR'] },
      { to: '/admin/audit', label: 'Audit log', icon: ScrollText, roles: ['SYSTEM_ADMINISTRATOR'] },
      { to: '/admin/system-health', label: 'System health', icon: Activity, roles: ['SYSTEM_ADMINISTRATOR'] },
      {
        to: '/admin/scoring-policy',
        label: 'Scoring policy',
        icon: SlidersHorizontal,
        roles: ['SYSTEM_ADMINISTRATOR'],
      },
    ],
  },
];

/** Sections filtered to a role, with empty sections dropped. */
export function navForRole(role: RoleName | null): NavSection[] {
  if (!role) return [];
  return NAV_SECTIONS.map((s) => ({
    ...s,
    items: s.items.filter((i) => i.roles.includes(role)),
  })).filter((s) => s.items.length > 0);
}

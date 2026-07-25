import { lazy } from 'react';
import { createBrowserRouter } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { ProtectedRoute } from '@/components/routing/ProtectedRoute';
import { RoleGate } from '@/components/routing/RoleGate';
import { LandingPage } from '@/features/landing/LandingPage';
import { SignInPage } from '@/features/auth/SignInPage';
import { NotAuthorised, NotFound, SystemError } from '@/features/errors/ErrorPages';

/**
 * React Router v6 data router (§9.4). Route-level code splitting via React.lazy;
 * AppShell wraps its <Outlet/> in a Suspense boundary with a route-shaped
 * skeleton (never a bare spinner). Guards carry the NFR-04 note that UI gating is
 * convenience, not security.
 *
 * Landing and sign-in are eagerly imported — they are the entry point and must
 * paint immediately.
 */
const named = <T extends Record<string, unknown>, K extends keyof T>(
  loader: () => Promise<T>,
  key: K,
) => lazy(() => loader().then((m) => ({ default: m[key] as React.ComponentType })));

const DashboardPage = named(() => import('@/features/dashboard/DashboardPage'), 'DashboardPage');
const PredictionPage = named(() => import('@/features/predictions/PredictionPage'), 'PredictionPage');
const ProgrammesPage = named(() => import('@/features/programmes/ProgrammesPage'), 'ProgrammesPage');
const CreateProgrammePage = named(() => import('@/features/programmes/CreateProgrammePage'), 'CreateProgrammePage');
const RequirementsPage = named(() => import('@/features/programmes/RequirementsPage'), 'RequirementsPage');
const ProgrammeDetailPage = named(() => import('@/features/programmes/ProgrammeDetailPage'), 'ProgrammeDetailPage');
const AllocationsPage = named(() => import('@/features/allocations/AllocationsPage'), 'AllocationsPage');
const AllocationDetailPage = named(() => import('@/features/allocations/AllocationDetailPage'), 'AllocationDetailPage');
const TrainersPage = named(() => import('@/features/trainers/TrainersPage'), 'TrainersPage');
const TrainerProfilePage = named(() => import('@/features/trainers/TrainerProfilePage'), 'TrainerProfilePage');
const MyProfilePage = named(() => import('@/features/trainers/MyProfilePage'), 'MyProfilePage');
const MyQualificationsPage = named(() => import('@/features/trainers/MyQualificationsPage'), 'MyQualificationsPage');
const MyAssignmentsPage = named(() => import('@/features/trainers/MyAssignmentsPage'), 'MyAssignmentsPage');
const MyPerformancePage = named(() => import('@/features/trainers/MyPerformancePage'), 'MyPerformancePage');
const EvaluationsPage = named(() => import('@/features/evaluations/EvaluationsPage'), 'EvaluationsPage');
const RecordEvaluationPage = named(() => import('@/features/evaluations/RecordEvaluationPage'), 'RecordEvaluationPage');
const ReportsPage = named(() => import('@/features/reports/ReportsPage'), 'ReportsPage');
const UsersPage = named(() => import('@/features/admin/UsersPage'), 'UsersPage');
const RolesPage = named(() => import('@/features/admin/RolesPage'), 'RolesPage');
const AuditPage = named(() => import('@/features/admin/AuditPage'), 'AuditPage');
const SystemHealthPage = named(() => import('@/features/admin/SystemHealthPage'), 'SystemHealthPage');
const ScoringPolicyPage = named(() => import('@/features/admin/ScoringPolicyPage'), 'ScoringPolicyPage');
const NotificationsPage = named(() => import('@/features/shared/NotificationsPage'), 'NotificationsPage');
const SettingsPage = named(() => import('@/features/shared/SettingsPage'), 'SettingsPage');
const KitchenSink = named(() => import('@/features/dev/KitchenSink'), 'KitchenSink');

export const router = createBrowserRouter([
  { path: '/', element: <LandingPage />, errorElement: <SystemError /> },
  { path: '/signin', element: <SignInPage /> },
  { path: '/403', element: <NotAuthorised /> },
  { path: '/404', element: <NotFound /> },
  { path: '/500', element: <SystemError /> },

  {
    element: <ProtectedRoute />,
    errorElement: <SystemError />,
    children: [
      {
        element: <AppShell />,
        children: [
          // NOTE: no index route here — a pathless layout with an index child
          // would also match "/", shadowing the public LandingPage.
          { path: 'dashboard', element: <DashboardPage /> },

          // Training programmes
          { path: 'programmes', element: <ProgrammesPage /> },
          { path: 'programmes/new', element: <CreateProgrammePage /> },
          { path: 'programmes/:id', element: <ProgrammeDetailPage /> },
          { path: 'programmes/:id/requirements', element: <RequirementsPage /> },

          // Prediction — the centrepiece
          { path: 'programmes/:id/prediction', element: <PredictionPage /> },

          // Allocations
          { path: 'allocations', element: <AllocationsPage /> },
          { path: 'allocations/:id', element: <AllocationDetailPage /> },

          // Trainers
          { path: 'trainers', element: <TrainersPage /> },
          { path: 'trainers/:id', element: <TrainerProfilePage /> },

          // Trainer self-service
          {
            element: <RoleGate roles={['TRAINER']} />,
            children: [
              { path: 'my-profile', element: <MyProfilePage /> },
              { path: 'my-profile/qualifications', element: <MyQualificationsPage /> },
              { path: 'my-assignments', element: <MyAssignmentsPage /> },
              { path: 'my-performance', element: <MyPerformancePage /> },
            ],
          },

          // Evaluations — Training Administrator only (matches the nav gating, so a
          // direct URL from another role lands on /403 rather than a broken page).
          {
            element: <RoleGate roles={['TRAINING_ADMINISTRATOR']} />,
            children: [
              { path: 'evaluations', element: <EvaluationsPage /> },
              { path: 'evaluations/new/:allocationId', element: <RecordEvaluationPage /> },
            ],
          },

          // Reports — Training Administrator / System Administrator (the API allows
          // both; officers/trainers are redirected to /403 instead of hitting a 403).
          {
            element: <RoleGate roles={['TRAINING_ADMINISTRATOR', 'SYSTEM_ADMINISTRATOR']} />,
            children: [{ path: 'reports', element: <ReportsPage /> }],
          },

          // Administration
          {
            path: 'admin',
            element: <RoleGate roles={['SYSTEM_ADMINISTRATOR']} />,
            children: [
              { path: 'users', element: <UsersPage /> },
              { path: 'roles', element: <RolesPage /> },
              { path: 'audit', element: <AuditPage /> },
              { path: 'system-health', element: <SystemHealthPage /> },
              { path: 'scoring-policy', element: <ScoringPolicyPage /> },
            ],
          },

          // Shared
          { path: 'notifications', element: <NotificationsPage /> },
          { path: 'settings', element: <SettingsPage /> },

          // Dev-only alignment proving ground (§16)
          ...(import.meta.env.DEV ? [{ path: 'kitchen-sink', element: <KitchenSink /> }] : []),

          { path: '*', element: <NotFound /> },
        ],
      },
    ],
  },

  { path: '*', element: <NotFound /> },
]);

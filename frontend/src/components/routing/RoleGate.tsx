import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import type { RoleName } from '@/types/domain';

/**
 * RoleGate — guards both routes and inline render.
 * NOTE: UI gating is convenience, not security — the API enforces authorisation
 * server-side (NFR-04). Hiding a control does not protect the action behind it.
 *
 * As a route wrapper: <Route element={<RoleGate roles={[...]} />}>…</Route>
 * As an inline guard: <RoleGate roles={[...]}>{content}</RoleGate>
 */
export function RoleGate({
  roles,
  children,
  fallback = null,
}: {
  roles: RoleName[];
  children?: React.ReactNode;
  fallback?: React.ReactNode;
}) {
  const role = useAuthStore((s) => s.role);
  const allowed = role !== null && roles.includes(role);

  // Route-wrapper mode (no children) — redirect to /403 when disallowed.
  if (children === undefined) {
    return allowed ? <Outlet /> : <Navigate to="/403" replace />;
  }

  // Inline mode — render children only when allowed.
  return <>{allowed ? children : fallback}</>;
}

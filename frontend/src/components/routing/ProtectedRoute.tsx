import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';

/**
 * ProtectedRoute — requires authentication.
 * NOTE: UI gating is convenience, not security — the API enforces authorisation
 * server-side (NFR-04). Never treat a hidden route as a protected resource.
 */
export function ProtectedRoute() {
  const user = useAuthStore((s) => s.user);
  const location = useLocation();
  if (!user) {
    return <Navigate to="/signin" state={{ from: location.pathname }} replace />;
  }
  return <Outlet />;
}

import { Navigate, useNavigate } from 'react-router-dom';
import { AuthBackground } from '@/features/auth/AuthBackground';
import { SignInCard } from '@/features/auth/SignInCard';
import { useAuthStore } from '@/stores/authStore';
import { ORG_UNIT } from '@/lib/constants';

/**
 * Landing (§13.1) — exactly one viewport, no scrolling (D4). Wordmark lower-left,
 * sign-in card upper-right. No marketing, no navigation, no scroll cue.
 */
export function LandingPage() {
  const navigate = useNavigate();
  const isAuthenticated = useAuthStore((s) => Boolean(s.user));
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;
  return (
    <AuthBackground>
      <div className="mx-auto grid h-full w-full max-w-content grid-cols-1 items-center gap-8 px-8 lg:grid-cols-12">
        <div className="order-2 hidden lg:order-1 lg:col-span-6 lg:flex">
          <div className="flex flex-col text-primary-50">
            <h2 className="font-display text-display-lg leading-none text-primary-50">Trainer</h2>
            <h2 className="font-display text-display-lg leading-none text-primary-50">Prediction</h2>
            <h2 className="font-display text-display-lg leading-none text-primary-50">System</h2>
            <span className="mt-4 font-mono text-label uppercase text-primary-200">{ORG_UNIT}</span>
          </div>
        </div>
        <div className="order-1 flex justify-center lg:order-2 lg:col-span-6 lg:justify-end">
          <SignInCard onSuccess={() => navigate('/dashboard')} />
        </div>
      </div>
    </AuthBackground>
  );
}

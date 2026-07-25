import { Navigate, useNavigate } from 'react-router-dom';
import { AuthBackground } from '@/features/auth/AuthBackground';
import { AuthHero } from '@/features/auth/AuthHero';
import { SignInCard } from '@/features/auth/SignInCard';
import { useAuthStore } from '@/stores/authStore';

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
      <div className="mx-auto grid h-full w-full max-w-content grid-cols-1 items-center gap-8 px-8 md:grid-cols-12">
        <AuthHero />
        <div className="order-1 flex justify-center md:order-2 md:col-span-6 md:justify-end">
          <SignInCard onSuccess={() => navigate('/dashboard')} />
        </div>
      </div>
    </AuthBackground>
  );
}

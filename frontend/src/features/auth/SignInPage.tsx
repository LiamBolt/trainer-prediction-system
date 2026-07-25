import { useNavigate, useSearchParams } from 'react-router-dom';
import { AuthBackground } from './AuthBackground';
import { AuthHero } from './AuthHero';
import { SignInCard } from './SignInCard';

/**
 * Sign in (§13.2) — the same two-column layout as the landing (brand wordmark on the
 * left, card on the right), so signing out or a session-expiry redirect feels
 * continuous rather than like a different, stripped-down product.
 */
export function SignInPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const expired = params.get('expired') === '1';

  return (
    <AuthBackground>
      <div className="mx-auto grid h-full w-full max-w-content grid-cols-1 items-center gap-8 px-8 md:grid-cols-12">
        <AuthHero />
        <div className="order-1 flex justify-center md:order-2 md:col-span-6 md:justify-end">
          <SignInCard expired={expired} onSuccess={() => navigate('/dashboard')} />
        </div>
      </div>
    </AuthBackground>
  );
}

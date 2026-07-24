import { useNavigate, useSearchParams } from 'react-router-dom';
import { AuthBackground } from './AuthBackground';
import { SignInCard } from './SignInCard';

/**
 * Sign in (§13.2) — the same card over the same background as the landing, so a
 * session-expiry redirect feels continuous rather than like a different product.
 */
export function SignInPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const expired = params.get('expired') === '1';

  return (
    <AuthBackground>
      <div className="mx-auto flex h-full w-full max-w-content items-center justify-center px-8 lg:justify-end">
        <SignInCard expired={expired} onSuccess={() => navigate('/dashboard')} />
      </div>
    </AuthBackground>
  );
}

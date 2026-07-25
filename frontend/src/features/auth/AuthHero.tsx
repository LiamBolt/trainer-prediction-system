import { ORG_UNIT } from '@/lib/constants';

/**
 * The left-hand brand column shared by the landing and sign-in screens (§13.1). Kept
 * in one place so both routes stay identical — previously only the landing page had
 * it, so signing out (which lands on /signin) dropped the wordmark entirely. Shown
 * from `md` up; on a phone the single sign-in card stands alone.
 */
export function AuthHero() {
  return (
    <div className="order-2 hidden md:order-1 md:col-span-6 md:flex">
      <div className="flex flex-col text-primary-50">
        <h2 className="font-display text-display-lg leading-none text-primary-50">Trainer</h2>
        <h2 className="font-display text-display-lg leading-none text-primary-50">Prediction</h2>
        <h2 className="font-display text-display-lg leading-none text-primary-50">System</h2>
        <span className="mt-4 font-mono text-label uppercase text-primary-200">{ORG_UNIT}</span>
      </div>
    </div>
  );
}

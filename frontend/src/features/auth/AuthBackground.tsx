import { useEffect } from 'react';
import { Crest } from '@/components/brand/Crest';
import { CLASSIFICATION_LEFT, CLASSIFICATION_RIGHT, ORG_NAME } from '@/lib/constants';
import heroImage from '@/assets/hero.png';

/**
 * The shared landing / sign-in background (§13.1). One viewport, no scroll. A bundled
 * hero image layered over a navy brand gradient, beneath a mandatory two-layer scrim
 * that keeps text at AA contrast over the brightest pixels.
 *
 * The original design (§15) called for a hero *video* with a video → poster → gradient
 * fallback chain. No video clip ships with the application, and referencing
 * `/media/tps-hero.*` produced 404s on every load, so the still image + gradient — the
 * end of that fallback chain — is used directly. `hero.png` is imported (not a public
 * URL), so Vite fingerprints it into the bundle and it can never 404.
 */
export function AuthBackground({ children }: { children: React.ReactNode }) {
  // Lock body scroll for this route only (§13.1 / D4).
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  return (
    <div className="relative h-dvh w-full overflow-hidden">
      {/* Base gradient — the ultimate fallback; never a blank rectangle. */}
      <div
        className="absolute inset-0"
        style={{ background: 'linear-gradient(135deg, #19154e 0%, #0f0d2e 60%, #0b0922 100%)' }}
        aria-hidden="true"
      />

      {/* Bundled hero image (hashed asset, always present). */}
      <img
        src={heroImage}
        alt=""
        aria-hidden="true"
        className="absolute inset-0 h-full w-full object-cover"
        onError={(e) => {
          (e.currentTarget as HTMLImageElement).style.display = 'none';
        }}
      />

      {/* Scrim — linear wash + radial vignette (§13.1). */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'linear-gradient(90deg, rgba(15,13,46,0.92) 0%, rgba(15,13,46,0.72) 45%, rgba(15,13,46,0.55) 100%)',
        }}
        aria-hidden="true"
      />
      <div
        className="absolute inset-0"
        style={{ background: 'radial-gradient(120% 90% at 50% 40%, transparent 40%, rgba(5,4,18,0.55) 100%)' }}
        aria-hidden="true"
      />

      {/* Foreground */}
      <div className="relative flex h-full flex-col">
        <header className="flex items-center gap-3 p-8 text-primary-50">
          <Crest size={40} />
          <div className="flex flex-col leading-tight">
            <span className="font-display text-h3 text-primary-50">{ORG_NAME}</span>
            <span className="font-mono text-label uppercase text-primary-200">Protect and Serve</span>
          </div>
        </header>

        <div className="flex-1 overflow-hidden">{children}</div>

        <div className="flex h-classification shrink-0 items-center justify-between gap-4 border-t border-primary-50/15 px-4 md:px-8">
          <span className="truncate font-mono text-label uppercase text-primary-200">
            {CLASSIFICATION_LEFT}
          </span>
          <span className="hidden truncate font-mono text-label uppercase text-primary-200 sm:inline">
            {CLASSIFICATION_RIGHT}
          </span>
        </div>
      </div>
    </div>
  );
}

import { useEffect, useState } from 'react';
import { Crest } from '@/components/brand/Crest';
import { CLASSIFICATION_LEFT, CLASSIFICATION_RIGHT, ORG_NAME } from '@/lib/constants';

/**
 * The shared landing / sign-in background (§13.1). One viewport, no scroll. Video
 * with a strict fallback chain — video → poster → navy gradient — so the page is
 * never blank even though the client's clip is still pending (§15). A mandatory
 * two-layer scrim keeps text AA-contrast over the brightest frame; reduced-motion
 * skips autoplay entirely.
 */
const HERO_WEBM = '/media/tps-hero.webm';
const HERO_MP4 = '/media/tps-hero.mp4';
const HERO_POSTER = '/media/hero-poster.jpg';

export function AuthBackground({ children }: { children: React.ReactNode }) {
  const [videoFailed, setVideoFailed] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);

  // Lock body scroll for this route only (§13.1 / D4).
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    setReduceMotion(window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  const showVideo = !reduceMotion && !videoFailed;

  return (
    <div className="relative h-dvh w-full overflow-hidden">
      {/* Base gradient — the ultimate fallback; never a blank rectangle. */}
      <div
        className="absolute inset-0"
        style={{ background: 'linear-gradient(135deg, #19154e 0%, #0f0d2e 60%, #0b0922 100%)' }}
        aria-hidden="true"
      />

      {/* Poster (shown when reduced-motion or video fails). */}
      {(reduceMotion || videoFailed) && (
        <img
          src={HERO_POSTER}
          alt=""
          aria-hidden="true"
          className="absolute inset-0 h-full w-full object-cover"
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = 'none';
          }}
        />
      )}

      {/* Video */}
      {showVideo && (
        <video
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
          poster={HERO_POSTER}
          onError={() => setVideoFailed(true)}
          className="absolute inset-0 h-full w-full object-cover"
        >
          <source src={HERO_WEBM} type="video/webm" />
          <source src={HERO_MP4} type="video/mp4" />
        </video>
      )}

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

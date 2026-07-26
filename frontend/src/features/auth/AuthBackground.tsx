import { useEffect, useState } from 'react';
import { Crest } from '@/components/brand/Crest';
import { CLASSIFICATION_LEFT, CLASSIFICATION_RIGHT, ORG_NAME } from '@/lib/constants';
import heroImage from '@/assets/hero.jpg';

/**
 * The shared landing / sign-in background (§13.1). One viewport, no scroll. A bundled
 * hero image layered over a navy brand gradient, beneath a mandatory two-layer scrim
 * that keeps text at AA contrast over the brightest pixels.
 *
 * The image is animated like a **hoisted flag on a windy day**: an SVG turbulence +
 * displacement filter ripples the pixels (the field "breathes" and the amplitude
 * pulses via SMIL), and a soft light band sweeps across for a shimmer. Both are
 * disabled under `prefers-reduced-motion`, leaving the still image + gradient.
 */
export function AuthBackground({ children }: { children: React.ReactNode }) {
  const [reduceMotion, setReduceMotion] = useState(false);

  // Lock body scroll for this route only (§13.1 / D4); read the motion preference once.
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    setReduceMotion(window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  return (
    <div className="relative h-dvh w-full overflow-hidden">
      {/* Scoped animation for the shimmer sweep. */}
      <style>{`
        @keyframes tps-flag-shimmer {
          0%   { background-position: 160% 0; }
          100% { background-position: -60% 0; }
        }
        .tps-flag-shimmer {
          background: linear-gradient(105deg,
            transparent 38%,
            rgba(255,255,255,0.10) 46%,
            rgba(255,255,255,0.26) 50%,
            rgba(255,255,255,0.10) 54%,
            transparent 62%);
          background-size: 220% 100%;
          mix-blend-mode: soft-light;
          animation: tps-flag-shimmer 7.5s ease-in-out infinite;
        }
        @media (prefers-reduced-motion: reduce) {
          .tps-flag-shimmer { animation: none; opacity: 0; }
        }
      `}</style>

      {/* The waving-flag displacement filter (0×0, just a definition). */}
      {!reduceMotion && (
        <svg aria-hidden="true" width="0" height="0" className="absolute">
          <filter
            id="tps-flag"
            x="-8%"
            y="-8%"
            width="116%"
            height="116%"
            colorInterpolationFilters="sRGB"
          >
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.009 0.016"
              numOctaves={2}
              seed={8}
              result="noise"
            >
              <animate
                attributeName="baseFrequency"
                dur="16s"
                keyTimes="0;0.5;1"
                values="0.009 0.016; 0.013 0.020; 0.009 0.016"
                calcMode="spline"
                keySplines="0.45 0 0.55 1; 0.45 0 0.55 1"
                repeatCount="indefinite"
              />
            </feTurbulence>
            <feDisplacementMap
              in="SourceGraphic"
              in2="noise"
              scale="24"
              xChannelSelector="R"
              yChannelSelector="G"
            >
              <animate
                attributeName="scale"
                dur="8s"
                keyTimes="0;0.5;1"
                values="16; 30; 16"
                calcMode="spline"
                keySplines="0.45 0 0.55 1; 0.45 0 0.55 1"
                repeatCount="indefinite"
              />
            </feDisplacementMap>
          </filter>
        </svg>
      )}

      {/* Base gradient — the ultimate fallback; never a blank rectangle. */}
      <div
        className="absolute inset-0"
        style={{ background: 'linear-gradient(135deg, #19154e 0%, #0f0d2e 60%, #0b0922 100%)' }}
        aria-hidden="true"
      />

      {/* Bundled hero image (hashed asset). Rippled by the flag filter; scaled up a
          touch so the displacement never pulls a transparent edge into view. */}
      <img
        src={heroImage}
        alt=""
        aria-hidden="true"
        className="absolute inset-0 h-full w-full object-cover will-change-transform"
        style={
          reduceMotion
            ? undefined
            : { filter: 'url(#tps-flag)', transform: 'scale(1.06)' }
        }
        onError={(e) => {
          (e.currentTarget as HTMLImageElement).style.display = 'none';
        }}
      />

      {/* Shimmer of light sweeping across, like sun catching a flag. Above the image,
          below the scrim, so text contrast is preserved. */}
      {!reduceMotion && (
        <div className="tps-flag-shimmer pointer-events-none absolute inset-0" aria-hidden="true" />
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

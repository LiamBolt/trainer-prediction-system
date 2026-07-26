/**
 * Asset paths behind single constants (§15). The client's crest/banner artwork
 * is pending; until it arrives the app renders the inline <Crest/> and a live
 * text wordmark. Drop the real files in and flip these constants — one line each.
 */
// Point the in-app logo at the favicon so the tab icon and the crest match. Served
// from public/ at the site root. NOTE: this favicon has a white background, so the
// logo shows as a white tile — see the sign-in header caveat. Give it a transparent
// background (drop the full-bleed white <rect> in the SVG) if you want it to blend.
export const CREST_IMAGE_SRC: string | null = '/favicon.svg?v=3';
export const BANNER_LIGHT_SRC: string | null = null; // header_banner_logo.png (dark ink)
export const BANNER_KNOCKOUT_SRC: string | null = null; // white version for dark grounds

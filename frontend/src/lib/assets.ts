/**
 * Asset paths behind single constants (§15). The client's crest/banner artwork
 * is pending; until it arrives the app renders the inline <Crest/> and a live
 * text wordmark. Drop the real files in and flip these constants — one line each.
 */
export const CREST_IMAGE_SRC: string | null = null; // e.g. '/assets/upf-crest.png'
export const BANNER_LIGHT_SRC: string | null = null; // header_banner_logo.png (dark ink)
export const BANNER_KNOCKOUT_SRC: string | null = null; // white version for dark grounds

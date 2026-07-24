/**
 * Formatting helpers enforcing the numeral + date rules in §5.5.
 * Every numeric surface routes through here so the whole app stays consistent.
 */
import dayjs from 'dayjs';
import { RANK_FULL_NAMES } from './constants';
import type { PoliceRank } from '@/types/domain';

/** Date: "14 Aug 2026" (§5.5). */
export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return '—';
  const d = dayjs(value);
  return d.isValid() ? d.format('DD MMM YYYY') : '—';
}

/** Compact date range: "10–21 Aug 2026" or "28 Jul – 4 Aug 2026". */
export function formatDateRange(start: string, end: string): string {
  const a = dayjs(start);
  const b = dayjs(end);
  if (!a.isValid() || !b.isValid()) return '—';
  if (a.isSame(b, 'day')) return formatDate(start);
  const sameMonth = a.month() === b.month() && a.year() === b.year();
  const sameYear = a.year() === b.year();
  if (sameMonth) return `${a.format('DD')}–${b.format('DD MMM YYYY')}`;
  if (sameYear) return `${a.format('DD MMM')} – ${b.format('DD MMM YYYY')}`;
  return `${a.format('DD MMM YYYY')} – ${b.format('DD MMM YYYY')}`;
}

/** Time, 24-hour: "14:35" (§5.5). */
export function formatTime(value: string | Date): string {
  const d = dayjs(value);
  return d.isValid() ? d.format('HH:mm') : '—';
}

/** Audit timestamp: "14 Aug 2026 · 14:35:07" (§5.5). */
export function formatTimestamp(value: string | Date): string {
  const d = dayjs(value);
  return d.isValid() ? d.format('DD MMM YYYY · HH:mm:ss') : '—';
}

/** Relative time for feeds ("3 hours ago"). */
export function formatRelative(value: string | Date): string {
  const d = dayjs(value);
  if (!d.isValid()) return '—';
  const diffMs = Date.now() - d.valueOf();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? '' : 's'} ago`;
  return formatDate(value);
}

/** Suitability score — always one decimal: "87.0" (§5.5). */
export function formatScore(value: number): string {
  return value.toFixed(1);
}

/** Percentage — one decimal. */
export function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

/** Integer count with thousands separators: "1,204" (§5.5). */
export function formatCount(value: number): string {
  return Math.round(value).toLocaleString('en-GB');
}

/** Evaluation score out of 5, one decimal: "4.6". */
export function formatRating(value: number): string {
  return value.toFixed(1);
}

/** Force number in mono display form: "No. 41927" (§8.8). */
export function formatForceNumber(forceNumber: string): string {
  return `No. ${forceNumber}`;
}

/** Rank code + full name: "IP · Inspector of Police". */
export function rankFullName(rank: PoliceRank): string {
  return RANK_FULL_NAMES[rank];
}

/** Generated avatar initials from a full name (max two letters). */
export function initials(fullName: string): string {
  const parts = fullName
    .replace(/\b(PC|CPL|SGT|AIP|IP|ASP|SP|SSP|ACP)\b\.?/i, '')
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length === 0) return '—';
  if (parts.length === 1) return (parts[0] ?? '').slice(0, 2).toUpperCase();
  const first = parts[0] ?? '';
  const last = parts[parts.length - 1] ?? '';
  return `${first.charAt(0)}${last.charAt(0)}`.toUpperCase();
}

/** Surname (last token) for narrative templates. */
export function surname(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  return parts[parts.length - 1] ?? fullName;
}

/** "1st", "2nd", "3rd"… for rank positions. */
export function ordinal(n: number): string {
  const s = ['th', 'st', 'nd', 'rd'];
  const v = n % 100;
  return `${n}${s[(v - 20) % 10] ?? s[v] ?? s[0]}`;
}

/** Milliseconds -> "1.4s" for the prediction run-time readout (NFR-01). */
export function formatElapsed(ms: number): string {
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Programme request registry number, e.g. "TPS/REQ/2026/0132" (§8.8). */
export function programmeRegistry(programmeId: number): string {
  return `TPS/REQ/2026/${String(programmeId).padStart(4, '0')}`;
}

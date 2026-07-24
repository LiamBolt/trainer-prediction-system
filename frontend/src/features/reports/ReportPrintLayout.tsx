import { forwardRef } from 'react';
import { Crest } from '@/components/brand/Crest';
import { ORG_NAME, ORG_UNIT } from '@/lib/constants';
import { formatDate, formatTimestamp } from '@/lib/format';
import type { ReportFilters } from '@/types/api';

/**
 * The dedicated print layout captured for PDF export (§11.9). Always rendered in
 * light theme (the exporter strips `dark` from the clone) and carries the report
 * title, the filter parameters used, a generation timestamp, and the generating
 * officer — so an exported report is self-describing months later.
 */
export interface ReportPrintLayoutProps {
  title: string;
  filters: ReportFilters;
  generatedBy: string;
  columns: { key: string; header: string }[];
  rows: Record<string, string | number>[];
}

export const ReportPrintLayout = forwardRef<HTMLDivElement, ReportPrintLayoutProps>(
  function ReportPrintLayout({ title, filters, generatedBy, columns, rows }, ref) {
    const filterText = [
      filters.from ? `From ${formatDate(filters.from)}` : null,
      filters.to ? `To ${formatDate(filters.to)}` : null,
      filters.category ? `Category: ${filters.category}` : null,
    ]
      .filter(Boolean)
      .join(' · ');

    return (
      <div
        ref={ref}
        // Rendered off-screen; captured by html2canvas at A4 width.
        style={{
          position: 'fixed',
          left: -10000,
          top: 0,
          width: 794,
          background: '#ffffff',
          color: '#09004a',
          padding: 32,
          fontFamily: '"Open Sans", system-ui, sans-serif',
        }}
        aria-hidden="true"
      >
        {/* Banner header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, borderBottom: '2px solid #19154e', paddingBottom: 12 }}>
          {/* Print artefact is deliberately theme-independent — colour set inline. */}
          <span style={{ color: '#19154e', display: 'inline-flex' }}>
            <Crest size={44} />
          </span>
          <div>
            <div style={{ fontFamily: 'Roboto, sans-serif', fontWeight: 700, fontSize: 18, color: '#19154e' }}>
              {ORG_NAME}
            </div>
            <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#67648a' }}>
              {ORG_UNIT} · Trainer Prediction System
            </div>
          </div>
        </div>

        <h1 style={{ fontFamily: 'Roboto, sans-serif', fontSize: 22, fontWeight: 700, margin: '20px 0 4px' }}>
          {title}
        </h1>
        <div style={{ fontSize: 12, color: '#67648a', marginBottom: 4 }}>
          {filterText || 'All records (no filters applied)'}
        </div>
        <div style={{ fontSize: 12, color: '#67648a', marginBottom: 20 }}>
          Generated {formatTimestamp(new Date().toISOString())} by {generatedBy}
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr>
              {columns.map((c) => (
                <th
                  key={c.key}
                  style={{
                    textAlign: 'left',
                    borderBottom: '1px solid #c2c1d0',
                    padding: '8px 6px',
                    fontFamily: '"JetBrains Mono", monospace',
                    fontSize: 10,
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                    color: '#67648a',
                  }}
                >
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {columns.map((c) => (
                  <td key={c.key} style={{ borderBottom: '1px solid #ecebf0', padding: '8px 6px' }}>
                    {r[c.key] ?? ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>

        <div style={{ marginTop: 24, borderTop: '1px solid #c2c1d0', paddingTop: 10, fontFamily: '"JetBrains Mono", monospace', fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#67648a' }}>
          Restricted · Authorised personnel only
        </div>
      </div>
    );
  },
);

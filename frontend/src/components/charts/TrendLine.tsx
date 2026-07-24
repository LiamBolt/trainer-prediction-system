import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { TrendPoint } from '@/types/api';

/**
 * TrendLine — a monochromatic indigo trend chart (§4.1: no rainbow palettes).
 * Used for performance-by-quarter, run-time over time, and trainer score history.
 */
export function TrendLine({
  data,
  domain,
  height = 240,
  reference,
  valueSuffix = '',
}: {
  data: TrendPoint[];
  domain?: [number, number];
  height?: number;
  reference?: { value: number; label: string };
  valueSuffix?: string;
}) {
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="var(--border-hairline)" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: 'rgb(var(--text-muted))', fontFamily: 'JetBrains Mono' }}
            tickLine={false}
            axisLine={{ stroke: 'var(--border-hairline)' }}
          />
          <YAxis
            domain={domain ?? ['auto', 'auto']}
            tick={{ fontSize: 11, fill: 'rgb(var(--text-muted))', fontFamily: 'JetBrains Mono' }}
            tickLine={false}
            axisLine={false}
            width={44}
          />
          <Tooltip
            cursor={{ stroke: 'var(--border-strong)' }}
            contentStyle={{
              background: 'rgb(var(--surface))',
              border: '1px solid var(--border-hairline)',
              borderRadius: 10,
              fontSize: 13,
              color: 'rgb(var(--ink))',
            }}
            formatter={(v: number) => [`${v}${valueSuffix}`, '']}
          />
          {reference && (
            <ReferenceLine
              y={reference.value}
              stroke="var(--danger-fg)"
              strokeDasharray="4 4"
              label={{
                value: reference.label,
                position: 'insideTopRight',
                fill: 'var(--danger-fg)',
                fontSize: 11,
              }}
            />
          )}
          <Line
            type="monotone"
            dataKey="value"
            stroke="var(--viz-1)"
            strokeWidth={2}
            dot={{ r: 3, fill: 'var(--viz-1)', strokeWidth: 0 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

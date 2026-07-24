import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Bucket } from '@/types/api';

/**
 * DistributionBar — horizontal distribution (e.g. allocations per trainer, which
 * reveals over-reliance on familiar names: the SRS problem statement, visualised).
 */
export function DistributionBar({
  data,
  height = 280,
  layout = 'horizontal',
}: {
  data: Bucket[];
  height?: number;
  layout?: 'horizontal' | 'vertical';
}) {
  const vertical = layout === 'vertical';
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout={vertical ? 'vertical' : 'horizontal'}
          margin={{ top: 8, right: 16, bottom: 0, left: vertical ? 24 : -16 }}
        >
          <CartesianGrid stroke="var(--border-hairline)" vertical={vertical} horizontal={!vertical} />
          {vertical ? (
            <>
              <XAxis
                type="number"
                tick={{ fontSize: 11, fill: 'rgb(var(--text-muted))', fontFamily: 'JetBrains Mono' }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                type="category"
                dataKey="label"
                width={140}
                tick={{ fontSize: 12, fill: 'rgb(var(--text-secondary))' }}
                tickLine={false}
                axisLine={false}
              />
            </>
          ) : (
            <>
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: 'rgb(var(--text-muted))' }}
                tickLine={false}
                axisLine={{ stroke: 'var(--border-hairline)' }}
              />
              <YAxis
                tick={{ fontSize: 11, fill: 'rgb(var(--text-muted))', fontFamily: 'JetBrains Mono' }}
                tickLine={false}
                axisLine={false}
                width={44}
              />
            </>
          )}
          <Tooltip
            cursor={{ fill: 'rgb(var(--surface-sunken))' }}
            contentStyle={{
              background: 'rgb(var(--surface))',
              border: '1px solid var(--border-hairline)',
              borderRadius: 10,
              fontSize: 13,
              color: 'rgb(var(--ink))',
            }}
          />
          <Bar dataKey="value" fill="var(--viz-2)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

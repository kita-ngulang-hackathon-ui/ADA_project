"use client";

// Forecasted drop in high-risk share per segment, in percentage points.
// Single series, so one hue and no legend; every bar is direct-labeled.
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SegmentForecast } from "@/lib/forecast";
import { formatReductionPp } from "@/lib/forecast";

type Row = {
  label: string;
  reduction: number;
  current: number;
  forecast: number;
};

export default function SegmentImpactChart({
  segments,
  rowHeight = 34,
}: {
  segments: SegmentForecast[];
  rowHeight?: number;
}) {
  const data: Row[] = segments.map((item) => ({
    label: item.segment.name,
    reduction: item.reductionPp,
    current: item.currentHighPct,
    forecast: item.forecastHighPct,
  }));

  const max = Math.max(1, ...data.map((row) => row.reduction));

  return (
    <div style={{ height: data.length * rowHeight + 36 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 72, bottom: 0, left: 0 }}
          barCategoryGap="28%"
        >
          <CartesianGrid stroke="var(--chart-grid)" horizontal={false} />
          <XAxis
            type="number"
            domain={[0, Math.ceil(max)]}
            tickFormatter={(value: number) => `${value}pp`}
            tick={{ fill: "var(--chart-axis)", fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: "var(--chart-grid)" }}
            allowDecimals={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={130}
            tick={{ fill: "var(--text)", fontSize: 13, fontWeight: 700 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            cursor={{ fill: "var(--blue-light)" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const row = payload[0].payload as Row;
              return (
                <div className="chart-tooltip">
                  <div className="chart-tooltip-label">{row.label}</div>
                  <div>
                    High risk{" "}
                    <span className="chart-tooltip-value">{row.current.toFixed(1)}%</span>
                    {" → "}
                    <span className="chart-tooltip-value">{row.forecast.toFixed(1)}%</span>
                  </div>
                </div>
              );
            }}
          />
          <Bar
            dataKey="reduction"
            fill="var(--blue)"
            radius={[0, 4, 4, 0]}
            isAnimationActive={false}
          >
            <LabelList
              dataKey="reduction"
              position="right"
              fill="var(--text)"
              fontSize={12}
              fontWeight={700}
              formatter={(value: number) =>
                value > 0 ? formatReductionPp(value) : "No change"
              }
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

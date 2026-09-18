"use client";

import { formatNumber } from "@/lib/mock-data";

type TooltipRow = {
  label: string;
  value: number;
  color?: string;
  suffix?: string;
};

export function ChartTooltipCard({
  title,
  rows,
}: {
  title: string;
  rows: TooltipRow[];
}) {
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-label">{title}</div>
      {rows.map((row) => (
        <div key={row.label} className="flex items-center gap-2">
          {row.color && (
            <span
              className="chart-legend-swatch"
              style={{ background: row.color }}
            />
          )}
          <span className="text-muted">{row.label}</span>
          <span className="chart-tooltip-value">
            {formatNumber(row.value)}
            {row.suffix ?? ""}
          </span>
        </div>
      ))}
    </div>
  );
}

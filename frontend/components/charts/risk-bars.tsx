"use client";

// One horizontal 100% bar per row, split into Low / Medium / High churn risk.
// Rows are segments on the dashboard, or "Current" vs "Forecast" for an action.
import { useState } from "react";
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
import { ChartTooltipCard } from "@/components/charts/chart-tooltip";
import { RISK_BANDS, formatNumber, type RiskCounts } from "@/lib/mock-data";
import { sumRisk } from "@/lib/forecast";

export type RiskRow = {
  label: string;
  risk: RiskCounts;
};

type ChartRow = {
  label: string;
  risk: RiskCounts;
  low: number;
  medium: number;
  high: number;
};

const toPct = (value: number, total: number) => (value / total) * 100;

export default function RiskBars({
  rows,
  rowHeight = 36,
  labelWidth = 130,
  caption,
}: {
  rows: RiskRow[];
  rowHeight?: number;
  labelWidth?: number;
  caption: string;
}) {
  const [showTable, setShowTable] = useState(false);

  const data: ChartRow[] = rows.map((row) => {
    const total = sumRisk(row.risk);
    return {
      label: row.label,
      risk: row.risk,
      low: toPct(row.risk.low, total),
      medium: toPct(row.risk.medium, total),
      high: toPct(row.risk.high, total),
    };
  });

  return (
    <div>
      <div style={{ height: rows.length * rowHeight + 36 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
            barCategoryGap="22%"
          >
            <CartesianGrid stroke="var(--chart-grid)" horizontal={false} />
            <XAxis
              type="number"
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tickFormatter={(value: number) => `${value}%`}
              tick={{ fill: "var(--chart-axis)", fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "var(--chart-grid)" }}
            />
            <YAxis
              type="category"
              dataKey="label"
              width={labelWidth}
              tick={{ fill: "var(--text)", fontSize: 13, fontWeight: 700 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              cursor={{ fill: "var(--blue-light)" }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const row = payload[0].payload as ChartRow;
                const total = sumRisk(row.risk);
                return (
                  <ChartTooltipCard
                    title={`${row.label} · ${formatNumber(total)} customers`}
                    rows={RISK_BANDS.map((band) => ({
                      label: `${band.label} ${row[band.key].toFixed(1)}% ·`,
                      value: row.risk[band.key],
                      color: band.color,
                    }))}
                  />
                );
              }}
            />
            {RISK_BANDS.map((band, index) => (
              <Bar
                key={band.key}
                dataKey={band.key}
                name={band.label}
                stackId="risk"
                fill={band.color}
                stroke="var(--white)"
                strokeWidth={2}
                radius={
                  index === 0
                    ? [4, 0, 0, 4]
                    : index === RISK_BANDS.length - 1
                      ? [0, 4, 4, 0]
                      : 0
                }
                isAnimationActive={false}
              >
                {band.key === "high" && (
                  <LabelList
                    dataKey="high"
                    position="insideRight"
                    fill="var(--white)"
                    fontSize={12}
                    fontWeight={900}
                    formatter={(value: number) => (value >= 7 ? `${value.toFixed(1)}%` : "")}
                  />
                )}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      <ul className="chart-legend">
        {RISK_BANDS.map((band) => (
          <li key={band.key} className="chart-legend-item">
            <span className="chart-legend-swatch" style={{ background: band.color }} />
            <span>{band.label} risk</span>
          </li>
        ))}
      </ul>

      <button
        type="button"
        className="table-toggle"
        onClick={() => setShowTable((open) => !open)}
        aria-expanded={showTable}
      >
        {showTable ? "Hide table" : "View as table"}
      </button>

      {showTable && (
        <table className="data-table mt-2">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr>
              <th scope="col" />
              {RISK_BANDS.map((band) => (
                <th key={band.key} scope="col">
                  {band.label}
                </th>
              ))}
              <th scope="col">Total</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.label}>
                <th scope="row">{row.label}</th>
                {RISK_BANDS.map((band) => (
                  <td key={band.key}>
                    {formatNumber(row.risk[band.key])}{" "}
                    <span className="text-muted">({row[band.key].toFixed(1)}%)</span>
                  </td>
                ))}
                <td>{formatNumber(sumRisk(row.risk))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

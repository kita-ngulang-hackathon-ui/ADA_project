"use client";

// Donut for part-to-whole counts. Identity is carried by the legend and the
// direct value labels, never by color alone.
import { useState } from "react";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { ChartTooltipCard } from "@/components/charts/chart-tooltip";
import { formatNumber, formatPercent } from "@/lib/mock-data";

export type DonutSlice = {
  label: string;
  users: number;
  color: string;
};

export default function DonutChart({
  slices,
  centerLabel,
  height = 240,
}: {
  slices: DonutSlice[];
  centerLabel: string;
  height?: number;
}) {
  const [showTable, setShowTable] = useState(false);
  const total = slices.reduce((sum, slice) => sum + slice.users, 0);

  return (
    <div>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={slices}
              dataKey="users"
              nameKey="label"
              innerRadius="62%"
              outerRadius="92%"
              paddingAngle={2}
              stroke="var(--white)"
              strokeWidth={2}
              isAnimationActive={false}
            >
              {slices.map((slice) => (
                <Cell key={slice.label} fill={slice.color} />
              ))}
            </Pie>

            <text
              x="50%"
              y="47%"
              textAnchor="middle"
              className="donut-center-value"
            >
              {formatNumber(total)}
            </text>
            <text
              x="50%"
              y="58%"
              textAnchor="middle"
              className="donut-center-label"
            >
              {centerLabel}
            </text>

            <Tooltip
              cursor={false}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const slice = payload[0].payload as DonutSlice;
                return (
                  <ChartTooltipCard
                    title={slice.label}
                    rows={[
                      {
                        label: `${formatPercent(slice.users, total)} ·`,
                        value: slice.users,
                        color: slice.color,
                      },
                    ]}
                  />
                );
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <ul className="chart-legend">
        {slices.map((slice) => (
          <li key={slice.label} className="chart-legend-item">
            <span
              className="chart-legend-swatch"
              style={{ background: slice.color }}
            />
            <span>{slice.label}</span>
            <span className="chart-legend-value">
              {formatPercent(slice.users, total)}
            </span>
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
          <thead>
            <tr>
              <th scope="col">{centerLabel}</th>
              <th scope="col">Customers</th>
              <th scope="col">Share</th>
            </tr>
          </thead>
          <tbody>
            {slices.map((slice) => (
              <tr key={slice.label}>
                <th scope="row">{slice.label}</th>
                <td>{formatNumber(slice.users)}</td>
                <td>{formatPercent(slice.users, total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

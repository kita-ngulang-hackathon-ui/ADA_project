"use client";

// Dashboard: churn risk (main), segmentation by risk, top suggested actions.
import { useActions } from "@/components/actions-provider";
import DonutChart from "@/components/charts/donut-chart";
import RiskBars from "@/components/charts/risk-bars";
import SuggestedActionsPreview from "@/components/suggested-actions-preview";
import { formatNumber } from "@/lib/mock-data";

export default function DashboardPage() {
  const { loading, error, segments, churnRiskSlices, portfolioRisk } = useActions();

  if (loading) return <div className="empty-state">Loading live data from the console API…</div>;
  if (error) return <div className="empty-state">Couldn&apos;t reach the console API: {error}</div>;

  return (
    <>
      <section className="dashboard-grid">
        <div className="card dashboard-card-risk">
          <h2 className="card-title">Churn Risk</h2>
          <p className="card-subtitle">All customers by predicted risk band</p>
          <DonutChart slices={churnRiskSlices} centerLabel="Customers" />
        </div>

        <div className="card dashboard-card-segments">
          <h2 className="card-title">Customer Segmentation</h2>
          <p className="card-subtitle">
            RFM-FCA segments, split by churn risk ({formatNumber(portfolioRisk.high)} high risk
            overall)
          </p>
          <div className="mt-4">
            <RiskBars
              rows={segments.map((segment) => ({ label: segment.name, risk: segment.risk }))}
              caption="Customers in each segment by churn risk band"
            />
          </div>
        </div>
      </section>

      <SuggestedActionsPreview />
    </>
  );
}

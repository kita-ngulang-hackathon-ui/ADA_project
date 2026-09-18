// Dashboard: churn risk (main), segmentation by risk, top suggested actions.
import DonutChart from "@/components/charts/donut-chart";
import RiskBars from "@/components/charts/risk-bars";
import SuggestedActionsPreview from "@/components/suggested-actions-preview";
import SyntheticDataBanner from "@/components/synthetic-data-banner";
import { CHURN_RISK_SLICES, PORTFOLIO_RISK } from "@/lib/forecast";
import { SEGMENTS, formatNumber } from "@/lib/mock-data";

export default function DashboardPage() {
  return (
    <>
      <SyntheticDataBanner />

      <section className="dashboard-grid">
        <div className="card dashboard-card-risk">
          <h2 className="card-title">Churn Risk</h2>
          <p className="card-subtitle">All customers by predicted risk band</p>
          <DonutChart slices={CHURN_RISK_SLICES} centerLabel="Customers" />
        </div>

        <div className="card dashboard-card-segments">
          <h2 className="card-title">Customer Segmentation</h2>
          <p className="card-subtitle">
            RFM-FCA segments, split by churn risk ({formatNumber(PORTFOLIO_RISK.high)} high risk
            overall)
          </p>
          <div className="mt-4">
            <RiskBars
              rows={SEGMENTS.map((segment) => ({ label: segment.name, risk: segment.risk }))}
              caption="Customers in each segment by churn risk band"
            />
          </div>
        </div>
      </section>

      <SuggestedActionsPreview />
    </>
  );
}

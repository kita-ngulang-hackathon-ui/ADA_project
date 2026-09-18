"use client";

// Suggested Actions: ranked list, each row expands to its forecasted effect on
// churn risk and on each customer segment. Review accepts, Dismiss rejects.
import { useEffect, useState } from "react";
import Link from "next/link";
import { useActions, type RankedAction } from "@/components/actions-provider";
import { RankBadge } from "@/components/action-badges";
import RiskBars from "@/components/charts/risk-bars";
import SegmentImpactChart from "@/components/charts/segment-impact-chart";
import SyntheticDataBanner from "@/components/synthetic-data-banner";
import { formatReductionPp, getForecast } from "@/lib/forecast";
import { formatNumber } from "@/lib/mock-data";

type Notice = { kind: "accepted" | "dismissed"; title: string };

export default function SuggestedActionsPage() {
  const { suggested, accept, dismiss } = useActions();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [notice, setNotice] = useState<Notice | null>(null);

  // Open the row linked from the dashboard preview (#action-id).
  useEffect(() => {
    const id = window.location.hash.slice(1);
    if (!id) return;
    setExpanded(new Set([id]));
    document.getElementById(id)?.scrollIntoView({ block: "start" });
  }, []);

  function toggle(id: string) {
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function onReview(action: RankedAction) {
    accept(action.id);
    setNotice({ kind: "accepted", title: action.title });
  }

  function onDismiss(action: RankedAction) {
    dismiss(action.id);
    setNotice({ kind: "dismissed", title: action.title });
  }

  return (
    <>
      <header className="page-header">
        <h1 className="page-title">
          <strong>Suggested Actions</strong>
        </h1>
        <p className="page-subtitle">
          {suggested.length} pending, ranked by forecasted customers leaving high churn risk
        </p>
      </header>

      <SyntheticDataBanner />

      {notice && (
        <div className="notice" role="status">
          <span>
            {notice.kind === "accepted" ? "Moved to ongoing: " : "Dismissed: "}
            <strong>{notice.title}</strong>
          </span>
          <Link href="/actions" className="notice-link">
            Open Actions Overview →
          </Link>
        </div>
      )}

      {suggested.length === 0 ? (
        <div className="empty-state">
          All suggestions have been handled. See{" "}
          <Link href="/actions" className="text-blue font-bold">
            Actions Overview
          </Link>
          .
        </div>
      ) : (
        <ol className="action-list">
          {suggested.map((action) => {
            const open = expanded.has(action.id);
            const forecast = getForecast(action.id);
            const panelId = `${action.id}-panel`;

            return (
              <li key={action.id} id={action.id} className="action-row">
                <button
                  type="button"
                  className="action-row-header"
                  onClick={() => toggle(action.id)}
                  aria-expanded={open}
                  aria-controls={panelId}
                >
                  <RankBadge rank={action.rank} />
                  <span className="action-row-title">{action.title}</span>
                  <span className="forecast-chip">
                    {formatReductionPp(forecast.highRiskReductionPp)} high risk
                  </span>
                  <span className={`chevron ${open ? "chevron-open" : ""}`} aria-hidden="true" />
                </button>

                {open && (
                  <div id={panelId} className="action-row-panel">
                    <p className="action-row-summary">{action.summary}</p>

                    <div className="impact-grid">
                      <div>
                        <h3 className="impact-title">Impact on churn risk</h3>
                        <div className="impact-stats">
                          <div>
                            <div className="impact-stat-value">
                              {formatNumber(forecast.customersLeavingHighRisk)}
                            </div>
                            <div className="impact-stat-label">customers leave high risk</div>
                          </div>
                          <div>
                            <div className="impact-stat-value">
                              {formatNumber(forecast.current.high)} →{" "}
                              {formatNumber(forecast.forecast.high)}
                            </div>
                            <div className="impact-stat-label">high-risk customers</div>
                          </div>
                          <div>
                            <div className="impact-stat-value">
                              {formatReductionPp(forecast.highRiskReductionPp)}
                            </div>
                            <div className="impact-stat-label">high-risk share</div>
                          </div>
                        </div>
                        <RiskBars
                          rows={[
                            { label: "Current", risk: forecast.current },
                            { label: "Forecast", risk: forecast.forecast },
                          ]}
                          labelWidth={80}
                          caption="All customers by churn risk, current and forecast"
                        />
                      </div>

                      <div>
                        <h3 className="impact-title">Impact on each customer segment</h3>
                        <p className="impact-note">
                          Forecasted drop in each segment&apos;s high-risk share
                        </p>
                        <SegmentImpactChart segments={forecast.segments} />
                      </div>
                    </div>

                    <div className="action-row-footer">
                      <button
                        type="button"
                        className="action-button"
                        onClick={() => onReview(action)}
                      >
                        Accept & Move to Ongoing
                      </button>
                      <button
                        type="button"
                        className="button-secondary button-small"
                        onClick={() => onDismiss(action)}
                      >
                        Dismiss
                      </button>
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </>
  );
}

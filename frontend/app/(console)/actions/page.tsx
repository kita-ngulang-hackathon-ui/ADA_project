"use client";

// Actions Overview: ongoing actions with step-by-step instructions, and the
// history of completed and dismissed actions.
import Link from "next/link";
import { useActions } from "@/components/actions-provider";
import { StatusBadge } from "@/components/action-badges";
import SyntheticDataBanner from "@/components/synthetic-data-banner";
import { TOTAL_CUSTOMERS, formatReductionPp, getForecast } from "@/lib/forecast";
import { formatDate, formatNumber } from "@/lib/mock-data";

export default function ActionsOverviewPage() {
  const { ongoing, history, toggleStep, complete } = useActions();

  return (
    <>
      <header className="page-header">
        <h1 className="page-title">
          <strong>Actions Overview</strong>
        </h1>
        <p className="page-subtitle">Follow ongoing actions and look back on past decisions</p>
      </header>

      <SyntheticDataBanner />

      <section className="mb-8">
        <div className="section-header">
          <h2 className="section-title">Ongoing ({ongoing.length})</h2>
        </div>

        {ongoing.length === 0 ? (
          <div className="empty-state">
            No ongoing actions. Review one from{" "}
            <Link href="/suggested-actions" className="text-blue font-bold">
              Suggested Actions
            </Link>
            .
          </div>
        ) : (
          <div className="ongoing-grid">
            {ongoing.map((action) => {
              const forecast = getForecast(action.id);
              const done = action.completedSteps.length;
              const total = action.instructions.length;
              const allDone = done === total;

              return (
                <article key={action.id} className="card ongoing-card">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <StatusBadge status={action.status} />
                    {action.decidedAt && (
                      <span className="text-muted text-[13px]">
                        Accepted {formatDate(action.decidedAt)}
                      </span>
                    )}
                  </div>

                  <h3 className="ongoing-title">{action.title}</h3>
                  <p className="text-muted text-[13px] mb-0">
                    Forecast: {formatNumber(forecast.customersLeavingHighRisk)} customers leave
                    high risk ({formatReductionPp(forecast.highRiskReductionPp)})
                  </p>

                  <div className="progress" aria-hidden="true">
                    <div className="progress-fill" style={{ width: `${(done / total) * 100}%` }} />
                  </div>
                  <div className="text-[13px] font-bold">
                    {done} / {total} steps done
                  </div>

                  <ol className="checklist">
                    {action.instructions.map((step, index) => {
                      const checked = action.completedSteps.includes(index);
                      const inputId = `${action.id}-step-${index}`;
                      return (
                        <li key={index} className={`checklist-item ${checked ? "checklist-item-done" : ""}`}>
                          <input
                            id={inputId}
                            type="checkbox"
                            className="login-checkbox"
                            checked={checked}
                            onChange={() => toggleStep(action.id, index)}
                          />
                          <label htmlFor={inputId}>
                            <span className="checklist-number">{index + 1}.</span> {step}
                          </label>
                        </li>
                      );
                    })}
                  </ol>

                  <button
                    type="button"
                    className="button-primary button-small self-start"
                    disabled={!allDone}
                    onClick={() => complete(action.id)}
                    title={allDone ? undefined : "Finish every step first"}
                  >
                    Mark complete
                  </button>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section>
        <div className="section-header">
          <h2 className="section-title">History ({history.length})</h2>
        </div>

        {history.length === 0 ? (
          <div className="empty-state">No completed or dismissed actions yet.</div>
        ) : (
          <div className="card overflow-x-auto p-0">
            <table className="data-table history-table">
              <thead>
                <tr>
                  <th scope="col">Action</th>
                  <th scope="col">Status</th>
                  <th scope="col">Date</th>
                  <th scope="col">Forecast</th>
                  <th scope="col">Actual</th>
                </tr>
              </thead>
              <tbody>
                {history.map((action) => {
                  const forecast = getForecast(action.id);
                  const date = action.completedAt ?? action.decidedAt;
                  const actual = action.outcome?.actualHighToMedium;
                  const isCompleted = action.status === "completed";

                  return (
                    <tr key={action.id}>
                      <th scope="row" className="history-action">
                        {action.title}
                      </th>
                      <td>
                        <StatusBadge status={action.status} />
                      </td>
                      <td className="whitespace-nowrap">{date ? formatDate(date) : "—"}</td>
                      <td className="whitespace-nowrap">
                        {isCompleted
                          ? `${formatNumber(forecast.customersLeavingHighRisk)} customers`
                          : "—"}
                      </td>
                      <td className="whitespace-nowrap">
                        {isCompleted && actual !== undefined
                          ? `${formatNumber(actual)} customers (${formatReductionPp(
                              (actual / TOTAL_CUSTOMERS) * 100,
                            )})`
                          : isCompleted
                            ? "Measuring…"
                            : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}

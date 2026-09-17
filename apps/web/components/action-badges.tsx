// Small labels shared by the action pages.
import type { ActionStatus } from "@/lib/mock-data";

export function RankBadge({ rank }: { rank: number }) {
  return (
    <span className="rank-badge" aria-label={`Rank ${rank}`}>
      #{rank}
    </span>
  );
}

const STATUS: Record<Exclude<ActionStatus, "suggested">, { label: string; icon: string }> = {
  ongoing: { label: "Ongoing", icon: "◔" },
  completed: { label: "Completed", icon: "✓" },
  dismissed: { label: "Dismissed", icon: "✕" },
};

// Icon + text, so status is never carried by color alone.
export function StatusBadge({ status }: { status: ActionStatus }) {
  if (status === "suggested") return null;
  const { label, icon } = STATUS[status];
  return (
    <span className={`status-badge status-badge-${status}`}>
      <span aria-hidden="true">{icon}</span>
      {label}
    </span>
  );
}

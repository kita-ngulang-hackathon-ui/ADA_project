"use client";

// Dashboard preview: top pending actions, rank and title only.
import Link from "next/link";
import { useActions } from "@/components/actions-provider";
import { RankBadge } from "@/components/action-badges";

const PREVIEW_COUNT = 4;

export default function SuggestedActionsPreview() {
  const { suggested } = useActions();
  const top = suggested.slice(0, PREVIEW_COUNT);

  return (
    <section>
      <div className="section-header">
        <h2 className="section-title">Suggested Actions</h2>
        <Link href="/suggested-actions" className="see-more">
          See more <span aria-hidden="true">→</span>
        </Link>
      </div>

      {top.length === 0 ? (
        <div className="empty-state">
          No pending suggestions. Check progress in{" "}
          <Link href="/actions" className="text-blue font-bold">
            Actions Overview
          </Link>
          .
        </div>
      ) : (
        <ol className="action-preview-grid">
          {top.map((action) => (
            <li key={action.id}>
              <Link href={`/suggested-actions#${action.id}`} className="action-preview-card">
                <RankBadge rank={action.rank} />
                <span className="action-preview-title">{action.title}</span>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

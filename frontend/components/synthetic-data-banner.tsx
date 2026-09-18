// Honesty rule: every screen that shows performance numbers says the data is synthetic.
export default function SyntheticDataBanner() {
  return (
    <div className="synthetic-banner" role="note">
      <span aria-hidden="true">⚠</span>
      <span>Synthetic demo data — no real customer records are shown.</span>
    </div>
  );
}

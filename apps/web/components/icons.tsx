// Inline stroke icons for the sidebar. Kept local so the demo stays offline.
export type NavIconName = "home" | "sparkle" | "checklist" | "logout";

const PATHS: Record<NavIconName, React.ReactNode> = {
  home: (
    <>
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5.5 9.5V20h13V9.5" />
    </>
  ),
  sparkle: (
    <>
      <path d="M12 3.5 13.9 9l5.6 2-5.6 2-1.9 5.5L10.1 13 4.5 11l5.6-2z" />
    </>
  ),
  checklist: (
    <>
      <path d="m4 6.5 1.6 1.6L8.5 5" />
      <path d="m4 12.5 1.6 1.6 2.9-3.1" />
      <path d="M4.5 18.5h3" />
      <path d="M11.5 7h8.5" />
      <path d="M11.5 13h8.5" />
      <path d="M11.5 19h8.5" />
    </>
  ),
  logout: (
    <>
      <path d="M14 4.5h4a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2h-4" />
      <path d="M10 16.5 5.5 12 10 7.5" />
      <path d="M5.5 12H15" />
    </>
  ),
};

export function NavIcon({ name }: { name: NavIconName }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  );
}

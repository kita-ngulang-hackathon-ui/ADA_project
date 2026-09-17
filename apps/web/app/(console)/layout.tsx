// Console layout: every page under this group gets the top bar, sidebar and
// shared action state.
import { ActionsProvider } from "@/components/actions-provider";
import AppShell from "@/components/app-shell";

export default function ConsoleLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ActionsProvider>
      <AppShell>{children}</AppShell>
    </ActionsProvider>
  );
}

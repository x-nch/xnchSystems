import { Suspense } from "react";
import { WorkflowsView } from "@/components/workflows/workflows-view";

export default function WorkflowsPage() {
  return (
    <Suspense fallback={<div className="flex h-full items-center justify-center font-mono text-xs text-muted-foreground">Loading workflows…</div>}>
      <WorkflowsView />
    </Suspense>
  );
}

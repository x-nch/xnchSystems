import { Suspense } from "react";
import { ApprovalQueue } from "@/components/approvals/approval-queue";

export default function Home() {
  return (
    <Suspense fallback={<div className="flex h-full items-center justify-center font-mono text-xs text-muted-foreground">Loading approvals…</div>}>
      <ApprovalQueue />
    </Suspense>
  );
}

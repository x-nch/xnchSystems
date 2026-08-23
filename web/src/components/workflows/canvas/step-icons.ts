import {
  Database,
  FilePen,
  Mail,
  Shapes,
  Target,
  Terminal,
  type LucideIcon,
} from "lucide-react";
import type { HitlActionKind } from "@/lib/approvals/types";

export const KIND_ICONS: Record<HitlActionKind, LucideIcon> = {
  write_file: FilePen,
  exec_tool: Terminal,
  send_email: Mail,
  create_goal: Target,
  update_memory: Database,
  other: Shapes,
};

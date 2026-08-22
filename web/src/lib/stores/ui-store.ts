import { create } from "zustand";

export type SubsystemId =
  | "memory"
  | "tools"
  | "policy"
  | "voice"
  | "capabilities"
  | "system"
  | "chat";

type UiState = {
  activeSubsystems: Set<SubsystemId>;
  presenceTransitioning: boolean;
  setSubsystemActive: (id: SubsystemId, active: boolean) => void;
  setPresenceTransitioning: (v: boolean) => void;
};

export const useUiStore = create<UiState>((set) => ({
  activeSubsystems: new Set(),
  presenceTransitioning: false,
  setSubsystemActive: (id, active) =>
    set((s) => {
      const next = new Set(s.activeSubsystems);
      if (active) next.add(id);
      else next.delete(id);
      return { activeSubsystems: next };
    }),
  setPresenceTransitioning: (presenceTransitioning) => ({ presenceTransitioning }),
}));

"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AuthMode } from "@/lib/auth/auth";

export interface SettingsState {
  /** Actor identity shown in the UI and used as `actor:<id>` / JWT sub. */
  actorId: string;
  /** Actor role sent in chat bodies and the `X-Actor-Role` header. */
  actorRole: string;
  authMode: AuthMode;
  authSecret: string;
  pastedToken: string;
  /** Sidebar collapsed state. */
  sidebarCollapsed: boolean;

  setActorId: (id: string) => void;
  setActorRole: (role: string) => void;
  setAuthMode: (mode: AuthMode) => void;
  setAuthSecret: (secret: string) => void;
  setPastedToken: (token: string) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      actorId: "operator",
      actorRole: "operator",
      authMode: "actor",
      authSecret: "",
      pastedToken: "",
      sidebarCollapsed: false,

      setActorId: (actorId) => set({ actorId }),
      setActorRole: (actorRole) => set({ actorRole }),
      setAuthMode: (authMode) => set({ authMode }),
      setAuthSecret: (authSecret) => set({ authSecret }),
      setPastedToken: (pastedToken) => set({ pastedToken }),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
    }),
    { name: "xnch-ui-settings" }
  )
);

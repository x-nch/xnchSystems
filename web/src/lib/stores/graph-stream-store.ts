"use client";

import { create } from "zustand";
import type { GraphEntity, GraphRelation, GraphStats } from "@/lib/api/types";

type GraphStreamState = {
  connected: boolean;
  stats: GraphStats | null;
  liveEntities: Record<string, GraphEntity>;
  liveRelations: Record<string, GraphRelation>;
  lastEventAt: number | null;
  setConnected: (v: boolean) => void;
  setStats: (stats: GraphStats) => void;
  upsertEntity: (entity: GraphEntity) => void;
  upsertRelation: (relation: GraphRelation) => void;
  clearLive: () => void;
  touch: () => void;
};

function relationKey(r: GraphRelation): string {
  return `${r.from_id}|${r.to_id}|${r.rel_type}`;
}

export const useGraphStreamStore = create<GraphStreamState>((set) => ({
  connected: false,
  stats: null,
  liveEntities: {},
  liveRelations: {},
  lastEventAt: null,
  setConnected: (connected) => set({ connected }),
  setStats: (stats) => set({ stats, lastEventAt: Date.now() }),
  upsertEntity: (entity) =>
    set((s) => ({
      liveEntities: { ...s.liveEntities, [entity.entity_id]: entity },
      lastEventAt: Date.now(),
    })),
  upsertRelation: (relation) =>
    set((s) => ({
      liveRelations: {
        ...s.liveRelations,
        [relationKey(relation)]: relation,
      },
      lastEventAt: Date.now(),
    })),
  clearLive: () => set({ liveEntities: {}, liveRelations: {} }),
  touch: () => set({ lastEventAt: Date.now() }),
}));

export function mergeGraphData(
  baseEntities: GraphEntity[],
  baseRelations: GraphRelation[],
  liveEntities: Record<string, GraphEntity>,
  liveRelations: Record<string, GraphRelation>
): { entities: GraphEntity[]; relations: GraphRelation[] } {
  const entityMap = new Map(baseEntities.map((e) => [e.entity_id, e]));
  for (const e of Object.values(liveEntities)) {
    entityMap.set(e.entity_id, e);
  }

  const relMap = new Map(
    baseRelations.map((r) => [`${r.from_id}|${r.to_id}|${r.rel_type}`, r])
  );
  for (const r of Object.values(liveRelations)) {
    relMap.set(relationKey(r), r);
  }

  return {
    entities: Array.from(entityMap.values()),
    relations: Array.from(relMap.values()),
  };
}

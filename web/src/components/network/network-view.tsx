"use client";

import { useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  type Edge,
  type EdgeTypes,
  type Node,
  type NodeTypes,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Activity,
  Cpu,
  Database,
  MessageSquare,
  Mic,
  Shield,
  Wrench,
} from "lucide-react";
import { CoreNode } from "./core-node";
import { AgentNode, type AgentNodeData } from "./agent-node";
import { GlowEdge } from "./glow-edge";
import { NetworkHud } from "./network-hud";
import { useHealth } from "@/lib/api/hooks";
import { useSubsystemStatuses } from "@/lib/hooks/use-subsystem-status";
import type { SubsystemId } from "@/lib/stores/ui-store";

const nodeTypes: NodeTypes = {
  core: CoreNode,
  agent: AgentNode,
};

const edgeTypes: EdgeTypes = {
  glow: GlowEdge,
};

type Satellite = {
  id: SubsystemId;
  label: string;
  desc: string;
  href: string;
  icon: typeof Database;
  index: number;
};

const SATELLITES: Satellite[] = [
  {
    id: "memory",
    label: "Memory",
    desc: "Recall · Surface",
    href: "/memory",
    icon: Database,
    index: 0,
  },
  {
    id: "tools",
    label: "Tools",
    desc: "MCP inventory",
    href: "/tools",
    icon: Wrench,
    index: 1,
  },
  {
    id: "policy",
    label: "Policy",
    desc: "Governance",
    href: "/system",
    icon: Shield,
    index: 2,
  },
  {
    id: "voice",
    label: "Voice",
    desc: "Speech I/O",
    href: "/system",
    icon: Mic,
    index: 3,
  },
  {
    id: "capabilities",
    label: "Capabilities",
    desc: "Nexi profile",
    href: "/system",
    icon: Cpu,
    index: 4,
  },
  {
    id: "system",
    label: "System",
    desc: "Health · State",
    href: "/system",
    icon: Activity,
    index: 5,
  },
  {
    id: "chat",
    label: "Chat",
    desc: "Agent sessions",
    href: "/chat",
    icon: MessageSquare,
    index: 6,
  },
];

const RADIUS = 268;

const HREF_BY_ID = Object.fromEntries(
  SATELLITES.map((s) => [s.id, s.href])
) as Record<SubsystemId, string>;

export function NetworkView() {
  const router = useRouter();
  const health = useHealth();
  const statuses = useSubsystemStatuses();

  const onNodeClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      const href = HREF_BY_ID[node.id as SubsystemId];
      if (href) router.push(href);
    },
    [router]
  );

  const activeCount = SATELLITES.filter(
    (s) => statuses[s.id].active || statuses[s.id].online
  ).length;

  const { nodes, edges } = useMemo(() => {
    const coreStatus =
      health.isError || !health.data
        ? "offline"
        : health.data.status === "ok"
          ? "ok"
          : "degraded";

    const satellites: Node[] = SATELLITES.map((s) => {
      const angle = -Math.PI / 2 + (s.index * 2 * Math.PI) / SATELLITES.length;
      const status = statuses[s.id];
      return {
        id: s.id,
        type: "agent",
        position: {
          x: RADIUS * Math.cos(angle),
          y: RADIUS * Math.sin(angle),
        },
        data: {
          label: s.label,
          desc: s.desc,
          href: s.href,
          icon: s.icon,
          online: status.online,
          active: status.active,
          meta: status.meta,
          alert: status.alert,
        } satisfies AgentNodeData,
      };
    });

    const coreNode: Node = {
      id: "core",
      type: "core",
      position: { x: -75, y: -75 },
      data: { status: coreStatus },
    };

    const edgeList: Edge[] = SATELLITES.map((s) => {
      const status = statuses[s.id];
      return {
        id: `e-core-${s.id}`,
        source: "core",
        target: s.id,
        type: "glow",
        data: { active: status.active, online: status.online },
      };
    });

    return { nodes: [coreNode, ...satellites], edges: edgeList };
  }, [health.isError, health.data, statuses]);

  const isOnline = !health.isError && health.data?.status === "ok";
  return (
    <div className="relative h-full w-full overflow-hidden bg-background">
      {isOnline && (
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background: "radial-gradient(520px 420px at 50% 46%, rgba(200,255,0,0.05), transparent 70%)",
          }}
          aria-hidden
        />
      )}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodeClick={onNodeClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.35}
        maxZoom={1.8}
        proOptions={{ hideAttribution: true }}
        nodesConnectable={false}
        nodesDraggable={false}
        elementsSelectable={false}
        nodesFocusable={false}
        panOnScroll
        className="bg-transparent"
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={28}
          size={1}
          color="rgba(242, 244, 247, 0.06)"
        />
        <Controls showInteractive={false} position="top-right" />
      </ReactFlow>

      <NetworkHud
        health={health.data}
        memoryCount={statuses.memoryCount}
        toolCount={statuses.toolCount}
        activeCount={activeCount}
        gatewayOk={statuses.gatewayOk}
      />
    </div>
  );
}

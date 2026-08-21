// Hand-written types mirroring the xnch gateway FastAPI schemas.

// ---- Health / system ----

export interface HealthResponse {
  status: "ok" | "degraded" | string;
  redis: "ok" | "unavailable" | string;
  state_version: string;
  version: string;
}

export interface SystemStateResponse {
  system_state_version: string;
  policy_version: string;
}

// ---- Chat ----

export interface ChatRequest {
  session_id: string;
  message: string;
  actor_role?: string;
}

export interface ChatResponse {
  response: string;
  model_used: string;
  session_id: string;
}

/** Parsed SSE event from POST /nexi/chat/stream. */
export type StreamEvent =
  | { type: "content"; content: string }
  | { type: "delta"; delta: string }
  | { type: "tool_call"; tool: string; arguments: unknown }
  | { type: "tool_result"; tool: string; result: unknown }
  | { type: "meta"; [key: string]: unknown }
  | { type: "error"; message: string }
  | { type: "done" };

// ---- Capabilities ----

export interface CapabilitiesResponse {
  summary?: string;
  hosts?: Record<string, string>;
  filesystem?: Record<string, unknown>;
  tools?: Record<string, string[]>;
  tool_routing?: string;
  voice?: Record<string, unknown>;
  [key: string]: unknown;
}

// ---- Memory ----

export interface MemoryRecallRequest {
  query: string;
  top_k?: number;
}

export interface Relationship {
  entity_a: string;
  entity_b: string;
  type: string;
  strength: number;
}

export interface MemoryRecallResult {
  id: string | null;
  type: string;
  timestamp: string | null;
  content: string;
  similarity: number;
  importance: number;
  relationships?: Relationship[];
}

export interface SurfaceEvent {
  trigger: string;
  message: string;
  priority: number;
  expires_at: string;
}

// ---- Kuzu L3 graph ----

export interface GraphEntity {
  entity_id: string;
  name: string;
  type: string;
  created_at?: string | null;
}

export interface GraphRelation {
  from_id: string;
  from_name?: string | null;
  to_id: string;
  to_name?: string | null;
  rel_type: string;
  confidence: number;
  created_at?: string | null;
}

export interface GraphEntitiesPage {
  entities: GraphEntity[];
  total: number;
  limit: number;
  offset: number;
}

export interface GraphRelationsPage {
  relations: GraphRelation[];
  total: number;
  limit: number;
  offset: number;
}

export interface GraphSubgraph {
  center_id: string;
  depth: number;
  entities: GraphEntity[];
  relations: GraphRelation[];
}

export interface GraphStats {
  entity_count: number;
  relation_count: number;
  types: Record<string, number>;
}

/** Parsed SSE event from GET /memory/graph/stream. */
export type GraphStreamEvent =
  | ({ type: "stats" } & GraphStats)
  | { type: "entity"; entity: GraphEntity }
  | { type: "relation"; relation: GraphRelation }
  | { type: "ready" }
  | { type: "sync" }
  | { type: "heartbeat" }
  | { type: "error"; message: string }
  | { type: "done" };

// ---- MCP tools ----

export interface McpTool {
  name: string;
  description: string;
  tier: string;
}

export interface McpToolsResponse {
  actor: string;
  tools: McpTool[];
}

export interface McpServersResponse {
  enabled: boolean;
  servers: Array<{
    name?: string;
    status?: string;
    tools?: number;
    [key: string]: unknown;
  }>;
}

export interface McpCallRequest {
  name: string;
  arguments: Record<string, unknown>;
}

export interface McpCallResponse {
  name: string;
  result: unknown;
}

// ---- Governance ----

export interface WeightConfigResponse {
  version: string;
  intent_class: string;
  weights: Record<string, number>;
}

export interface PolicyCandidate {
  [key: string]: unknown;
}

// ---- Session ----

export interface SessionInitRequest {
  auth_token: string;
  raw_input: string;
  input_type?: string;
  priority?: string;
  source_system?: string;
  trace_id?: string;
  idempotency_key?: string;
}

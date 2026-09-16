// Wire-contract tests for every endpoint touched in Phase 2 (T5–T8).
// Captures the exact URL / query / method / body each frontend API module
// issues, so a drift from the backend contract fails the build instead of
// silently 404ing or returning empty lists.
import { describe, expect, it, vi, beforeAll, afterAll, beforeEach } from "vitest";
import { workflowEndpoints } from "@/lib/api/workflows";
import { agentsApi } from "@/lib/api/agents";

const map = new Map<string, string>();
const localStorageShim: Storage = {
  getItem: (k) => map.get(k) ?? null,
  setItem: (k, v) => void map.set(k, v),
  removeItem: (k) => void map.delete(k),
  clear: () => map.clear(),
  key: () => null,
  get length() {
    return map.size;
  },
};

type Captured = { url: string; method: string; headers: Headers; body?: string };
let captured: Captured[] = [];

function makeResponse(body: string, status = 200): Response {
  return new Response(body, { status, headers: { "Content-Type": "application/json" } });
}

describe("workflow endpoints wire contract (approved + decide)", () => {
  beforeAll(() => {
    vi.stubGlobal("localStorage", localStorageShim);
    vi.stubGlobal("window", { location: { origin: "http://localhost:3000" } });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        captured.push({
          url: String(_input),
          method: init?.method ?? "GET",
          headers: new Headers(init?.headers),
          body: init?.body as string | undefined,
        });
        return makeResponse("[]");
      })
    );
  });

  afterAll(() => {
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    captured = [];
  });

  it("lists approvals with the AWAITING_APPROVAL default (T7 status contract)", async () => {
    await workflowEndpoints.listApprovals();
    expect(captured[0].url).toBe(
      "http://localhost:3000/api/gateway/approvals?status=AWAITING_APPROVAL"
    );
    expect(captured[0].method).toBe("GET");
  });

  it("maps explicit expiry-status filters onto the query string", async () => {
    await workflowEndpoints.listApprovals({ status: "APPROVED" });
    expect(captured[0].url).toBe(
      "http://localhost:3000/api/gateway/approvals?status=APPROVED"
    );
  });

  it("accepts the producer_type filter alongside status", async () => {
    await workflowEndpoints.listApprovals({
      status: "AWAITING_APPROVAL",
      producer_type: "workstream_spawn",
    });
    expect(captured[0].url).toBe(
      "http://localhost:3000/api/gateway/approvals?status=AWAITING_APPROVAL&producer_type=workstream_spawn"
    );
  });

  it("decides an approval via POST to /approvals/{id}/decide with the decision body", async () => {
    await workflowEndpoints.decideApproval("apr_1", { decision: "approve", note: "looks good" });
    expect(captured[0].url).toBe(
      "http://localhost:3000/api/gateway/approvals/apr_1/decide"
    );
    expect(captured[0].method).toBe("POST");
    expect(JSON.parse(captured[0].body ?? "{}")).toEqual({
      decision: "approve",
      note: "looks good",
    });
  });

  it("sends approved/rejected decisions as the Literal contract", async () => {
    await workflowEndpoints.decideApproval("apr_2", { decision: "reject" });
    expect(JSON.parse(captured[0].body ?? "{}")).toEqual({ decision: "reject" });
  });

  it("attaches X-Actor-Role: operator on reads and the admin role on decides (audit P1)", async () => {
    await workflowEndpoints.listApprovals();
    expect(captured[0].headers.get("X-Actor-Role")).toBe("operator");
    await workflowEndpoints.decideApproval("apr_3", { decision: "approve" });
    expect(captured[1].headers.get("X-Actor-Role")).toBe("admin");
  });
});

describe("agents endpoints wire contract (listRuns + dispatch)", () => {
  beforeAll(() => {
    vi.stubGlobal("localStorage", localStorageShim);
    vi.stubGlobal("window", { location: { origin: "http://localhost:3000" } });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        captured.push({
          url: String(_input),
          method: init?.method ?? "GET",
          headers: new Headers(init?.headers),
          body: init?.body as string | undefined,
        });
        return makeResponse("[]");
      })
    );
  });

  afterAll(() => {
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    captured = [];
  });

  it("lists runs via GET /agents/runs with no filter by default", async () => {
    await agentsApi.listRuns();
    expect(captured[0].url).toBe("http://localhost:3000/api/gateway/agents/runs");
    expect(captured[0].method).toBe("GET");
  });

  it("appends status as a query param when given", async () => {
    await agentsApi.listRuns("RUNNING");
    expect(captured[0].url).toBe(
      "http://localhost:3000/api/gateway/agents/runs?status=RUNNING"
    );
  });

  it("dispatches via POST /agents/dispatch with just the prompt", async () => {
    await agentsApi.dispatch("Create hello.txt containing hi");
    expect(captured[0].url).toBe("http://localhost:3000/api/gateway/agents/dispatch");
    expect(captured[0].method).toBe("POST");
    expect(JSON.parse(captured[0].body ?? "{}")).toEqual({
      prompt: "Create hello.txt containing hi",
    });
  });

  it("includes a non-empty trimmed workspace in the dispatch body", async () => {
    await agentsApi.dispatch("do a thing", "  ~/xnch-agents/custom  ");
    expect(JSON.parse(captured[0].body ?? "{}")).toEqual({
      prompt: "do a thing",
      workspace: "~/xnch-agents/custom",
    });
  });

  it("omits a blank/whitespace-only workspace", async () => {
    await agentsApi.dispatch("do a thing", "   ");
    expect(JSON.parse(captured[0].body ?? "{}")).toEqual({ prompt: "do a thing" });
  });
});
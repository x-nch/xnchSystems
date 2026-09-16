import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import { useSettingsStore } from "@/lib/stores/settings-store";

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

describe("buildHeaders X-MCP-Token plumbing", () => {
  let buildHeaders: (typeof import("./client"))["buildHeaders"];

  beforeAll(async () => {
    vi.stubGlobal("localStorage", localStorageShim);
    const client = await import("./client");
    buildHeaders = client.buildHeaders;
  });

  afterAll(() => {
    vi.unstubAllGlobals();
  });

  it("omits X-MCP-Token when none is configured", async () => {
    useSettingsStore.setState({ mcpToken: "" });
    const headers = await buildHeaders();
    expect(headers["X-MCP-Token"]).toBeUndefined();
  });

  it("sends X-MCP-Token when configured", async () => {
    useSettingsStore.setState({ mcpToken: "s3cret" });
    const headers = await buildHeaders();
    expect(headers["X-MCP-Token"]).toBe("s3cret");
  });

  it("keeps Content-Type, X-Actor-Role and Authorization in the same call", async () => {
    useSettingsStore.setState({
      mcpToken: "s3cret",
      authMode: "actor",
      actorId: "operator",
      actorRole: "operator",
    });
    const headers = await buildHeaders();
    expect(headers["Content-Type"]).toBe("application/json");
    expect(headers["X-Actor-Role"]).toBe("operator");
    expect(headers["Authorization"]).toBe("actor:operator");
    expect(headers["X-MCP-Token"]).toBe("s3cret");
  });
});
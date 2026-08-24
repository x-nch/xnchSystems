import { describe, expect, it } from "vitest";
import { isGatedGatewayPath } from "./route";

describe("isGatedGatewayPath", () => {
  it("gates writes to protected prefixes", () => {
    expect(isGatedGatewayPath(["agents", "runs"], "POST")).toBe(true);
    expect(isGatedGatewayPath(["approvals", "x", "decide"], "POST")).toBe(true);
    expect(isGatedGatewayPath(["workflows"], "DELETE")).toBe(true);
  });

  it("gates reads to protected prefixes too (2026-08-24 audit P0)", () => {
    expect(isGatedGatewayPath(["agents", "runs"], "GET")).toBe(true);
    expect(isGatedGatewayPath(["approvals"], "GET")).toBe(true);
    expect(isGatedGatewayPath(["workflows", "runs"], "GET")).toBe(true);
  });

  it("never gates chat, observability, or system traffic", () => {
    for (const method of ["GET", "POST", "HEAD", "OPTIONS"]) {
      expect(isGatedGatewayPath(["chat"], method)).toBe(false);
      expect(isGatedGatewayPath(["nexi", "chat"], method)).toBe(false);
      expect(isGatedGatewayPath(["observability"], method)).toBe(false);
      expect(isGatedGatewayPath(["system"], method)).toBe(false);
    }
  });

  it("treats an empty path as ungated", () => {
    expect(isGatedGatewayPath([], "GET")).toBe(false);
  });
});

import { describe, expect, it } from "vitest";
import { linePath, toPoints } from "@/components/observability/charts";

describe("observability chart helpers", () => {
  it("linePath emits an SVG path string", () => {
    const pts = [
      { x: 0, y: 10 },
      { x: 5.25, y: 2 },
    ];
    expect(linePath(pts)).toBe("M0.00,10.00 L5.25,2.00");
  });

  it("toPoints spans the padded viewbox on x", () => {
    const pts = toPoints(
      [
        [0, 5],
        [1, 5],
      ],
      100,
      50,
      4
    );
    expect(pts).toHaveLength(2);
    expect(pts[1].x).toBeCloseTo(96, 5);
  });

  it("toPoints keeps constant series flat instead of dividing by zero", () => {
    const pts = toPoints(
      [
        [0, 5],
        [1, 5],
      ],
      100,
      50,
      4
    );
    expect(pts[0].y).toBe(pts[1].y);
  });
});

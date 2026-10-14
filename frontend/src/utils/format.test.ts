import { describe, expect, it } from "vitest";
import { formatDuration, formatTimestamp } from "./format";

describe("format helpers", () => {
  it("formats timestamps without losing hour boundaries", () => {
    expect(formatTimestamp(3661.9)).toBe("01:01:01");
    expect(formatTimestamp(-1)).toBe("00:00:00");
  });

  it("formats persisted processing duration", () => {
    expect(formatDuration("2026-01-01T00:00:00Z", "2026-01-01T00:02:04Z")).toBe("2m 4s");
    expect(formatDuration(null, null)).toBe("—");
  });
});

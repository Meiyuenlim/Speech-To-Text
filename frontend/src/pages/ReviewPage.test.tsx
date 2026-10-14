import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api/client";
import type { Meeting } from "../types";
import { ReviewPage } from "./ReviewPage";

vi.mock("../api/client", () => ({
  api: { getMeeting: vi.fn(), regenerateMinutes: vi.fn() },
  exportUrl: () => "#",
  fileUrl: (path: string | null) => path,
}));

afterEach(() => vi.clearAllMocks());

it("shows the saved transcript and allows minutes regeneration when minutes are absent", async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.mocked(api.getMeeting).mockResolvedValue({
    id: "meeting-1", title: "Failed summary", meeting_date: null,
    original_filename: "meeting.wav", device: "cpu", warnings: [], minutes: null,
    transcript: [{ id: "segment-1", sequence: 0, start_time: 0, end_time: 2,
      text: "The new deadline is Friday.", confidence: 0.9, needs_review: false }],
  } as unknown as Meeting);
  vi.mocked(api.regenerateMinutes).mockResolvedValue({} as Awaited<ReturnType<typeof api.regenerateMinutes>>);
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  try {
    await act(async () => {
      root.render(<MemoryRouter initialEntries={["/meetings/meeting-1/review"]}>
        <Routes><Route path="/meetings/:id/review" element={<ReviewPage />} /></Routes>
      </MemoryRouter>);
    });
    expect(container.querySelector("textarea")?.value).toBe("The new deadline is Friday.");
    expect(container.textContent).not.toContain("Loading review workspace");
    const minutesTab = Array.from(container.querySelectorAll("button")).find(button => button.textContent === "Meeting minutes")!;
    await act(async () => minutesTab.click());
    expect(container.textContent).toContain("Minutes have not been generated yet");
    const regenerate = Array.from(container.querySelectorAll("button")).find(button => button.textContent === "Regenerate minutes")!;
    await act(async () => regenerate.click());
    expect(api.regenerateMinutes).toHaveBeenCalledWith("meeting-1");
  } finally {
    await act(async () => root.unmount());
    container.remove();
    vi.unstubAllGlobals();
  }
});

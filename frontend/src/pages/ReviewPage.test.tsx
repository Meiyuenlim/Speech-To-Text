import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { api } from "../api/client";
import type { Meeting } from "../types";
import { ReviewPage } from "./ReviewPage";

vi.mock("../api/client", () => ({
  api: { getMeeting: vi.fn(), regenerateMinutes: vi.fn(), updateTranscript: vi.fn() },
  exportUrl: () => "#",
  fileUrl: (path: string | null) => path,
}));

const meeting = {
  id: "meeting-1", title: "Failed summary", meeting_date: null, status: "failed",
  original_filename: "meeting.wav", device: "cpu", warnings: [], minutes: null,
  transcript: [
    { id: "segment-1", sequence: 0, start_time: 0, end_time: 2, text: "The new deadline is Friday.", confidence: 0.9, needs_review: false },
    { id: "segment-2", sequence: 1, start_time: 2, end_time: 4, text: "Please confirm by Friday.", confidence: 0.8, needs_review: true },
  ],
} as unknown as Meeting;

let container: HTMLDivElement;
let root: Root;

beforeEach(async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.mocked(api.getMeeting).mockResolvedValue(meeting);
  vi.mocked(api.regenerateMinutes).mockResolvedValue({} as Awaited<ReturnType<typeof api.regenerateMinutes>>);
  vi.mocked(api.updateTranscript).mockImplementation(async (_id, segments) => segments.map((segment, index) => ({ ...segment, id: "saved-" + index })));
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () => {
    root.render(<MemoryRouter initialEntries={["/meetings/meeting-1/review"]}>
      <Routes><Route path="/meetings/:id/review" element={<ReviewPage />} /></Routes>
    </MemoryRouter>);
  });
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.resetAllMocks();
  vi.unstubAllGlobals();
});

function button(text: string) {
  return Array.from(container.querySelectorAll("button")).find(item => item.textContent === text && !item.closest("[hidden]"))!;
}

async function change(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const prototype = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(prototype, "value")!.set!.call(element, value);
    element.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

it("shows one readable document, including when minutes are absent", async () => {
  expect(container.querySelector('[role="region"][aria-label="Full transcript"]')?.textContent).toBe("The new deadline is Friday. Please confirm by Friday.");
  expect(container.querySelectorAll("textarea")).toHaveLength(0);
  await act(async () => button("Meeting minutes").click());
  expect(container.textContent).toContain("Minutes have not been generated yet");
  const regenerate = button("Regenerate minutes");
  await act(async () => { regenerate.click(); regenerate.click(); });
  expect(api.regenerateMinutes).toHaveBeenCalledTimes(1);
  expect(api.regenerateMinutes).toHaveBeenCalledWith("meeting-1");
  expect(container.querySelector('a[href="/meetings/meeting-1/process"]')).not.toBeNull();
});

it("searches within the full document without hiding other transcript text", async () => {
  const search = container.querySelector('input[aria-label="Search transcript"]') as HTMLInputElement;
  await change(search, "friday");
  expect(container.querySelectorAll("mark")).toHaveLength(2);
  expect(container.textContent).toContain("1 of 2 matches");
  await act(async () => button("Next match").click());
  expect(container.textContent).toContain("2 of 2 matches");
  await change(search, "Friday. Please");
  expect(container.querySelector("mark")?.textContent).toBe("Friday. Please");
  await change(search, "[missing]");
  expect(container.textContent).toContain("No matches");
  expect(container.querySelector('[aria-label="Full transcript"]')?.textContent).toContain("Please confirm by Friday.");
});

it("edits in one box, keeps drafts across tabs, and saves with the original timing", async () => {
  await act(async () => button("Edit transcript").click());
  expect(container.querySelectorAll("textarea")).toHaveLength(1);
  const textarea = container.querySelector("textarea")!;
  const corrected = textarea.value.replace("new deadline", "agreed deadline");
  await change(textarea, corrected);
  expect(button("Regenerate minutes").disabled).toBe(true);
  await act(async () => button("Meeting minutes").click());
  expect(button("Regenerate minutes").disabled).toBe(true);
  await act(async () => button("Transcript").click());
  expect(container.querySelector("textarea")?.value).toBe(corrected);
  await act(async () => button("Save corrections").click());
  expect(api.updateTranscript).toHaveBeenCalledWith("meeting-1", [
    { ...meeting.transcript[0], text: "The agreed deadline is Friday." },
    { ...meeting.transcript[1], text: " Please confirm by Friday." },
  ]);
  expect(button("Save corrections").disabled).toBe(true);
  expect(button("Regenerate minutes").disabled).toBe(false);
  await act(async () => button("Reading view").click());
  expect(container.querySelector('[aria-label="Full transcript"]')?.textContent).toBe(corrected);
});

it("keeps corrections available if saving fails and prevents saving an empty transcript", async () => {
  vi.mocked(api.updateTranscript).mockRejectedValue(new Error("Could not save. Try again."));
  await act(async () => button("Edit transcript").click());
  const textarea = container.querySelector("textarea")!;
  const corrected = textarea.value.replace("Friday", "Monday");
  await change(textarea, corrected);
  await act(async () => button("Save corrections").click());
  expect(container.querySelector('[role="alert"]')?.textContent).toContain("Could not save");
  expect(textarea.value).toBe(corrected);
  expect(button("Save corrections").disabled).toBe(false);
  await change(textarea, "");
  expect(button("Save corrections").disabled).toBe(true);
  expect(button("Regenerate minutes").disabled).toBe(true);
});

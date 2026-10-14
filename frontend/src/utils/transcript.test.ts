import { describe, expect, it } from "vitest";
import type { TranscriptSegment } from "../types";
import { createTranscriptDocument, editTranscriptDocument, transcriptSegmentsForSave } from "./transcript";

const segments: TranscriptSegment[] = [
  { id: "first", sequence: 0, start_time: 0, end_time: 4, text: "We will meet Monday.", confidence: 0.9, needs_review: false },
  { id: "second", sequence: 1, start_time: 5, end_time: 9, text: "Please bring the report.", confidence: 0.7, needs_review: true },
  { id: "third", sequence: 2, start_time: 10, end_time: 12, text: "谢谢大家。", confidence: 0.9, needs_review: false },
];

describe("continuous transcript corrections", () => {
  it("joins the full transcript without changing the source data", () => {
    const document = createTranscriptDocument(segments);
    expect(document.text).toBe("We will meet Monday. Please bring the report. 谢谢大家。");
    expect(segments[1].text).toBe("Please bring the report.");
    expect(createTranscriptDocument(transcriptSegmentsForSave(document)).text).toBe(document.text);
  });

  it("keeps paragraph breaks through saving and reloading", () => {
    const document = createTranscriptDocument([segments[0], { ...segments[1], start_time: 8 }]);
    expect(document.text).toBe("We will meet Monday.\n\nPlease bring the report.");
    const edited = editTranscriptDocument(document, document.text.replace("Monday", "Friday"));
    expect(createTranscriptDocument(transcriptSegmentsForSave(edited)).text).toBe(edited.text);
  });

  it("preserves timestamps and review metadata when correcting a word", () => {
    const document = createTranscriptDocument(segments);
    const edited = editTranscriptDocument(document, document.text.replace("Monday", "Friday"));
    const saved = transcriptSegmentsForSave(edited);
    expect(saved[0]).toEqual({ ...segments[0], text: "We will meet Friday." });
    expect(saved.slice(1)).toEqual(document.segments.slice(1));
  });

  it("uses the affected audio range for edits across original boundaries", () => {
    const document = createTranscriptDocument(segments);
    const edited = editTranscriptDocument(document, document.text.replace("Monday. Please bring", "Tuesday; review"));
    const saved = transcriptSegmentsForSave(edited);
    expect(saved).toHaveLength(2);
    expect(saved[0]).toMatchObject({ start_time: 0, end_time: 9, text: "We will meet Tuesday; review the report.", needs_review: true });
    expect(saved[1]).toMatchObject({ start_time: 10, end_time: 12, text: " 谢谢大家。", sequence: 1 });
    expect(createTranscriptDocument(saved).text).toBe(edited.text);
  });

  it("preserves insertions, deletions and replacements at every boundary through a save/reload", () => {
    const document = createTranscriptDocument(segments.slice(0, 2).map((segment, index) => ({ ...segment, text: ["abc", "def"][index] })));
    for (let start = 0; start <= document.text.length; start++) {
      for (let end = start; end <= document.text.length; end++) {
        for (const replacement of ["", "新 text", "\n\n"]) {
          const text = document.text.slice(0, start) + replacement + document.text.slice(end);
          const edited = editTranscriptDocument(document, text);
          expect(edited.segments.map(segment => segment.text).join("")).toBe(text);
          expect(createTranscriptDocument(transcriptSegmentsForSave(edited)).text).toBe(text);
        }
      }
    }
  });

  it("allows replacing cleared text without losing the original audio range", () => {
    const cleared = editTranscriptDocument(createTranscriptDocument(segments), "");
    const edited = editTranscriptDocument(cleared, "A corrected transcript.");
    expect(transcriptSegmentsForSave(edited)).toEqual([
      expect.objectContaining({ start_time: 0, end_time: 12, text: "A corrected transcript." }),
    ]);
  });

  it("saves a large paste within API limits without losing Unicode or text on reload", () => {
    const text = "a".repeat(9999) + "😀" + "你好".repeat(6000);
    const edited = editTranscriptDocument(createTranscriptDocument(segments), text);
    const saved = transcriptSegmentsForSave(edited);
    expect(saved.length).toBeGreaterThan(1);
    expect(saved.every(segment => segment.text.length <= 10000 && segment.start_time === 0 && segment.end_time === 12)).toBe(true);
    expect(saved.map(segment => segment.text).join("")).toBe(text);
    expect(createTranscriptDocument(saved).text).toBe(text);
    expect(saved[0].text.endsWith("\ud83d")).toBe(false);
  });
});

import type { TranscriptSegment } from "../types";

export type TranscriptDocument = {
  text: string;
  segments: TranscriptSegment[];
};

// Keep separators in the segment text so paragraph breaks survive save/reload.
export function createTranscriptDocument(segments: TranscriptSegment[]): TranscriptDocument {
  let paragraphLength = 0;
  const parts = segments.map((segment, index) => {
    const previous = segments[index - 1];
    let separator = "";
    const sameRange = previous?.start_time === segment.start_time && previous?.end_time === segment.end_time;
    if (previous && !sameRange && !/\s$/.test(previous.text) && !/^\s/.test(segment.text)) {
      const paragraphBreak = segment.start_time - previous.end_time >= 3
        || (paragraphLength >= 400 && /[.!?。！？]["'”’）)]*$/.test(previous.text));
      separator = paragraphBreak ? "\n\n" : " ";
    }
    const text = separator + segment.text;
    paragraphLength = text.includes("\n\n")
      ? text.slice(text.lastIndexOf("\n\n") + 2).length
      : paragraphLength + text.length;
    return { ...segment, text };
  });
  return { text: parts.map(segment => segment.text).join(""), segments: parts };
}

// Map a contiguous document edit back to its affected audio range. Unchanged
// segments keep their timestamps; edits across boundaries use the combined range.
export function editTranscriptDocument(document: TranscriptDocument, text: string): TranscriptDocument {
  if (text === document.text || document.segments.length === 0) return document;
  const previous = document.text;
  let start = 0;
  while (start < previous.length && start < text.length && previous[start] === text[start]) start++;
  let end = previous.length;
  let nextEnd = text.length;
  while (end > start && nextEnd > start && previous[end - 1] === text[nextEnd - 1]) {
    end--;
    nextEnd--;
  }

  let offset = 0;
  const ranges = document.segments.map(segment => {
    const range = { start: offset, end: offset + segment.text.length };
    offset = range.end;
    return range;
  });
  const firstMatch = ranges.findIndex(range => range.end > start);
  const first = firstMatch === -1 ? ranges.length - 1 : firstMatch;
  const last = end === start ? first : ranges.findIndex((range, index) => index >= first && range.end >= end);
  const affected = document.segments.slice(first, last + 1);
  const merged: TranscriptSegment = {
    ...affected[0],
    start_time: Math.min(...affected.map(segment => segment.start_time)),
    end_time: Math.max(...affected.map(segment => segment.end_time)),
    text: affected[0].text.slice(0, start - ranges[first].start)
      + text.slice(start, nextEnd)
      + affected[affected.length - 1].text.slice(end - ranges[last].start),
    confidence: affected.length === 1 ? affected[0].confidence : null,
    needs_review: affected.some(segment => segment.needs_review),
  };
  const segments = [
    ...document.segments.slice(0, first), merged, ...document.segments.slice(last + 1),
  ];
  return { text, segments };
}

export function transcriptSegmentsForSave(document: TranscriptDocument): TranscriptSegment[] {
  const joined: TranscriptSegment[] = [];
  for (const segment of document.segments.filter(segment => segment.text.length > 0)) {
    const previous = joined[joined.length - 1];
    if (previous && !/\s$/.test(previous.text) && !/^\s/.test(segment.text)) {
      // Preserve an intentional removal of the space between two original parts.
      joined[joined.length - 1] = {
        ...previous, text: previous.text + segment.text,
        start_time: Math.min(previous.start_time, segment.start_time),
        end_time: Math.max(previous.end_time, segment.end_time),
        confidence: null, needs_review: previous.needs_review || segment.needs_review,
      };
    } else joined.push(segment);
  }
  const segments: TranscriptSegment[] = [];
  for (const segment of joined) {
    // Large pastes keep the affected range rather than inventing finer timings.
    for (let offset = 0; offset < segment.text.length;) {
      let end = Math.min(offset + 10000, segment.text.length);
      if (end < segment.text.length && /[\uD800-\uDBFF]/.test(segment.text[end - 1])) end--;
      segments.push({ ...segment, text: segment.text.slice(offset, end), sequence: segments.length });
      offset = end;
    }
  }
  return segments;
}

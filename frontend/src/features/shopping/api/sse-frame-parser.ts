/**
 * Transport-level SSE frame parsing for the agent chat stream (D7 wire format:
 * `event: <type>\ndata: <one-line JSON>\n\n`, per
 * specs/001-backend-agent-scaffold/contracts/http-api.md).
 *
 * Pure string machinery — no fetch, no React, no schema validation. The
 * extractor reassembles raw network chunks into complete frames; `parseSseData`
 * is the only place a frame's data line is decoded to JSON.
 */

export interface SseFrame {
  event: string;
  data: string;
}

/** Error thrown when a frame's data line is not valid JSON. */
export class SseDataError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "SseDataError";
  }
}

/**
 * Parses one frame's raw text (an "event: X" line plus a "data: Y" line).
 * Tolerates CRLF endings, comment lines (":" prefix) and stray blank lines;
 * tolerates extra whitespace around the values. Returns null when the event or
 * data line is missing — never throws. The data payload is returned verbatim;
 * JSON decoding is `parseSseData`'s job.
 */
export function parseSseFrame(raw: string): SseFrame | null {
  let event: string | null = null;
  let data: string | null = null;

  for (const line of raw.split(/\r?\n/)) {
    if (line === "" || line.startsWith(":")) {
      continue;
    }
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      data = line.slice("data:".length).trim();
    }
  }

  if (!event || !data) {
    return null;
  }
  return { event, data };
}

/** Decodes a frame's data line as JSON; throws {@link SseDataError} on garbage. */
export function parseSseData<T = unknown>(frame: SseFrame): T {
  try {
    return JSON.parse(frame.data) as T;
  } catch (cause) {
    throw new SseDataError(`SSE data for event "${frame.event}" is not valid JSON.`, {
      cause,
    });
  }
}

/** True for the two frames that may end a turn: `turn_end` and `error`. */
export function isTerminalFrame(frame: SseFrame): boolean {
  return frame.event === "turn_end" || frame.event === "error";
}

type SseStreamExtractor = {
  push: (chunk: string) => SseFrame[];
  flush: () => SseFrame[];
};

/**
 * Blank-line frame terminators: `\n\n` plus every CRLF mix the network can
 * produce (`\r\n\r\n`, `\r\n\n`, `\n\r\n`). Longest alternative first so
 * `\r\n\r\n` is consumed as a single boundary.
 */
const FRAME_TERMINATOR = /\r\n\r\n|\r\n\n|\n\r\n|\n\n/;

/**
 * Stateful incremental frame extractor. Feed raw network chunks to `push`;
 * every COMPLETE frame (terminated by a blank line) is returned, in order,
 * while the partial tail stays buffered — however the chunk boundaries fall
 * (mid-line, mid-JSON, mid-terminator). `flush()` ends the stream: it emits a
 * trailing buffered frame even without its terminating blank line (connection
 * cut mid-stream); heartbeats and comment-only frames emit nothing.
 */
export function createSseStreamExtractor(): SseStreamExtractor {
  let buffer = "";

  return {
    push(chunk: string): SseFrame[] {
      buffer += chunk;
      const frames: SseFrame[] = [];

      let terminator = FRAME_TERMINATOR.exec(buffer);
      while (terminator) {
        const rawFrame = buffer.slice(0, terminator.index);
        buffer = buffer.slice(terminator.index + terminator[0].length);
        const frame = parseSseFrame(rawFrame);
        if (frame) {
          frames.push(frame);
        }
        terminator = FRAME_TERMINATOR.exec(buffer);
      }

      return frames;
    },
    flush(): SseFrame[] {
      if (buffer === "") {
        return [];
      }
      const rawFrame = buffer;
      buffer = "";
      const frame = parseSseFrame(rawFrame);
      return frame ? [frame] : [];
    },
  };
}

import { describe, expect, it } from "vitest";
import {
  createSseStreamExtractor,
  isTerminalFrame,
  parseSseData,
  parseSseFrame,
  SseDataError,
  type SseFrame,
} from "./sse-frame-parser";

/** Renders one wire frame exactly as the backend does (compact one-line JSON). */
function frame(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

/** Feeds chunks through one extractor and appends the flush result. */
function extractAll(chunks: string[]): SseFrame[] {
  const extractor = createSseStreamExtractor();
  const frames = chunks.flatMap((chunk) => extractor.push(chunk));
  return [...frames, ...extractor.flush()];
}

const UI_PLAN = {
  planVersion: "1",
  sessionId: "demo-12345",
  turnId: 3,
  root: {
    type: "product_grid",
    props: {
      title: "Best matches for long flights",
      productIds: ["aurora-hush-pro", "cloudline-air"],
      ranked: true,
    },
    actions: [
      { type: "compare", label: "Compare", payload: {} },
      {
        type: "add_to_cart",
        label: "Add to cart",
        payload: { productId: "aurora-hush-pro" },
      },
    ],
  },
};

/** A realistic turn: six statuses, two deltas, one plan, one terminator. */
const REALISTIC_STREAM = [
  frame("status", { stage: "intent_parsed" }),
  frame("status", { stage: "searching" }),
  frame("status", { stage: "found_n", count: 14 }),
  frame("status", { stage: "researching" }),
  frame("status", { stage: "ranking" }),
  frame("status", { stage: "building_ui" }),
  frame("message_delta", { text: "Based on your priorities, here are my top picks." }),
  frame("message_delta", { text: "Aurora Hush Pro ($179): adaptive ANC rated 4.9/5." }),
  frame("ui_update", UI_PLAN),
  frame("turn_end", {}),
].join("");

const REALISTIC_FRAMES: SseFrame[] = [
  { event: "status", data: '{"stage":"intent_parsed"}' },
  { event: "status", data: '{"stage":"searching"}' },
  { event: "status", data: '{"stage":"found_n","count":14}' },
  { event: "status", data: '{"stage":"researching"}' },
  { event: "status", data: '{"stage":"ranking"}' },
  { event: "status", data: '{"stage":"building_ui"}' },
  {
    event: "message_delta",
    data: '{"text":"Based on your priorities, here are my top picks."}',
  },
  {
    event: "message_delta",
    data: '{"text":"Aurora Hush Pro ($179): adaptive ANC rated 4.9/5."}',
  },
  { event: "ui_update", data: JSON.stringify(UI_PLAN) },
  { event: "turn_end", data: "{}" },
];

describe("parseSseFrame", () => {
  it("parses one well-formed frame", () => {
    expect(parseSseFrame('event: status\ndata: {"stage":"intent_parsed"}\n\n')).toEqual({
      event: "status",
      data: '{"stage":"intent_parsed"}',
    });
  });

  it("keeps the data payload verbatim, including a count field", () => {
    const parsed = parseSseFrame('event: status\ndata: {"stage":"found_n","count":14}\n\n');
    expect(parsed).toEqual({ event: "status", data: '{"stage":"found_n","count":14}' });
  });

  it("ignores comment lines around the frame", () => {
    const parsed = parseSseFrame(": heartbeat\nevent: turn_end\ndata: {}\n: trailing\n");
    expect(parsed).toEqual({ event: "turn_end", data: "{}" });
  });

  it("returns null when the event line is missing", () => {
    expect(parseSseFrame('data: {"text":"hi"}\n\n')).toBeNull();
  });

  it("returns null when the data line is missing", () => {
    expect(parseSseFrame("event: status\n\n")).toBeNull();
  });

  it("tolerates extra spaces around the values", () => {
    expect(parseSseFrame('event:  status  \ndata:   {"ok":true}  ')).toEqual({
      event: "status",
      data: '{"ok":true}',
    });
  });

  it("tolerates surrounding blank lines", () => {
    expect(parseSseFrame("\n\nevent: turn_end\ndata: {}\n\n\n")).toEqual({
      event: "turn_end",
      data: "{}",
    });
  });

  it("parses CRLF line endings inside the frame", () => {
    expect(parseSseFrame("event: turn_end\r\ndata: {}\r\n\r\n")).toEqual({
      event: "turn_end",
      data: "{}",
    });
  });

  it("returns null for empty or blank-only input", () => {
    expect(parseSseFrame("")).toBeNull();
    expect(parseSseFrame("\n\n")).toBeNull();
    expect(parseSseFrame("\r\n\r\n")).toBeNull();
  });
});

describe("parseSseData", () => {
  it("round-trips a JSON payload", () => {
    const frame = { event: "status", data: JSON.stringify({ stage: "found_n", count: 14 }) };
    expect(parseSseData(frame)).toEqual({ stage: "found_n", count: 14 });
  });

  it("returns typed payloads when given a type parameter", () => {
    const frame: SseFrame = { event: "message_delta", data: '{"text":"hello"}' };
    const payload = parseSseData<{ text: string }>(frame);
    expect(payload.text).toBe("hello");
  });

  it("throws a SseDataError naming the event on malformed JSON", () => {
    const frame: SseFrame = { event: "ui_update", data: "{not-json" };
    try {
      parseSseData(frame);
      expect.fail("expected parseSseData to throw");
    } catch (error) {
      expect(error).toBeInstanceOf(SseDataError);
      expect((error as SseDataError).name).toBe("SseDataError");
      expect((error as SseDataError).message).toContain("ui_update");
    }
  });
});

describe("isTerminalFrame", () => {
  it("returns true for turn_end and error frames", () => {
    expect(isTerminalFrame({ event: "turn_end", data: "{}" })).toBe(true);
    expect(isTerminalFrame({ event: "error", data: '{"message":"boom"}' })).toBe(true);
  });

  it("returns false for mid-turn frames", () => {
    expect(isTerminalFrame({ event: "status", data: '{"stage":"ranking"}' })).toBe(false);
    expect(isTerminalFrame({ event: "message_delta", data: '{"text":"hi"}' })).toBe(false);
    expect(isTerminalFrame({ event: "ui_update", data: '{"planVersion":"1"}' })).toBe(false);
  });
});

describe("createSseStreamExtractor", () => {
  it("parses a full stream pushed as one chunk", () => {
    expect(extractAll([REALISTIC_STREAM])).toEqual(REALISTIC_FRAMES);
  });

  it("yields identical frames when the stream is split at every possible offset", () => {
    for (let offset = 0; offset <= REALISTIC_STREAM.length; offset += 1) {
      const head = REALISTIC_STREAM.slice(0, offset);
      const tail = REALISTIC_STREAM.slice(offset);
      expect(extractAll([head, tail]), `split at offset ${offset}`).toEqual(REALISTIC_FRAMES);
    }
  });

  it("reassembles frames pushed one character at a time", () => {
    expect(extractAll([...REALISTIC_STREAM])).toEqual(REALISTIC_FRAMES);
  });

  it("emits only complete frames and retains the partial tail", () => {
    const twoFrames =
      frame("status", { stage: "intent_parsed" }) + frame("status", { stage: "searching" });
    const cut = twoFrames.length + 5;

    const extractor = createSseStreamExtractor();
    expect(extractor.push(REALISTIC_STREAM.slice(0, cut))).toEqual(REALISTIC_FRAMES.slice(0, 2));
    expect(extractor.push(REALISTIC_STREAM.slice(cut))).toEqual(REALISTIC_FRAMES.slice(2));
  });

  it("separates consecutive frames pushed back to back", () => {
    expect(extractAll([REALISTIC_STREAM, REALISTIC_STREAM])).toEqual([
      ...REALISTIC_FRAMES,
      ...REALISTIC_FRAMES,
    ]);
  });

  it("parses a CRLF-framed stream", () => {
    const stream = [
      'event: status\r\ndata: {"stage":"ranking"}\r\n\r\n',
      "event: turn_end\r\ndata: {}\r\n\r\n",
    ].join("");
    expect(extractAll([stream])).toEqual([
      { event: "status", data: '{"stage":"ranking"}' },
      { event: "turn_end", data: "{}" },
    ]);
  });

  it("treats mixed CRLF/LF blank-line terminators as frame boundaries", () => {
    const stream = [
      'event: status\r\ndata: {"stage":"ranking"}\r\n\n',
      'event: message_delta\ndata: {"text":"hi"}\n\r\n',
      "event: turn_end\ndata: {}\n\n",
    ].join("");
    expect(extractAll([stream])).toEqual([
      { event: "status", data: '{"stage":"ranking"}' },
      { event: "message_delta", data: '{"text":"hi"}' },
      { event: "turn_end", data: "{}" },
    ]);
  });

  it("recognizes a CRLF terminator split across two pushes", () => {
    const extractor = createSseStreamExtractor();
    expect(extractor.push("event: turn_end\ndata: {}\r\n")).toEqual([]);
    expect(extractor.push("\r\n")).toEqual([{ event: "turn_end", data: "{}" }]);
  });

  it("emits nothing for a blank heartbeat chunk and keeps parsing afterwards", () => {
    const extractor = createSseStreamExtractor();
    expect(extractor.push("\n\n")).toEqual([]);
    expect(extractor.flush()).toEqual([]);
    expect(extractor.push("event: turn_end\ndata: {}\n\n")).toEqual([
      { event: "turn_end", data: "{}" },
    ]);
  });

  it("emits nothing for comment-only frames", () => {
    expect(extractAll([": keep-alive\n\n", ":retry in 30\n\n"])).toEqual([]);
  });

  it("flush() emits a trailing frame that lacks its terminator", () => {
    const extractor = createSseStreamExtractor();
    expect(extractor.push('event: status\ndata: {"stage":"ranking"}\n')).toEqual([]);
    expect(extractor.flush()).toEqual([{ event: "status", data: '{"stage":"ranking"}' }]);
    expect(extractor.flush()).toEqual([]);
  });

  it("flush() drops a trailing frame missing its data line", () => {
    const extractor = createSseStreamExtractor();
    extractor.push("event: status\n");
    expect(extractor.flush()).toEqual([]);
  });

  it("flush() with an empty buffer returns an empty array", () => {
    expect(createSseStreamExtractor().flush()).toEqual([]);
  });

  it("flush() after a fully terminated stream returns an empty array", () => {
    const extractor = createSseStreamExtractor();
    extractor.push(REALISTIC_STREAM);
    expect(extractor.flush()).toEqual([]);
  });

  it("keeps a data line containing escaped \\n\\n as a single frame", () => {
    const data = JSON.stringify({ text: "first paragraph\n\nsecond paragraph" });
    expect(data).toContain("\\n\\n");

    const frames = extractAll([`event: message_delta\ndata: ${data}\n\n`]);
    expect(frames).toEqual([{ event: "message_delta", data }]);
    expect(parseSseData<{ text: string }>(frames[0]).text).toBe(
      "first paragraph\n\nsecond paragraph"
    );
  });
});

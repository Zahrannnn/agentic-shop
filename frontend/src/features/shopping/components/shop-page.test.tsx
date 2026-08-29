import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

// jsdom does not implement scrollIntoView; the auto-scroll effect needs it.
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

import { SESSION_STORAGE_KEY, type Turn } from "../store";
import { ShopPage } from "./shop-page";

/**
 * The hook module is mocked outright: the shell's contract is what
 * `useAgentTurn` exposes ({ turns, phase, isBusy, sessionId, send,
 * startFresh }), so tests drive the store shape directly and assert how the
 * shell renders it and what it passes back into `send`.
 */

type SendOutcomeLike = { kind: string; status?: number; detail?: unknown };

type HookValue = {
  turns: Turn[];
  phase: "idle" | "streaming";
  isBusy: boolean;
  sessionId: string;
  send: (input: unknown) => Promise<SendOutcomeLike>;
  startFresh: () => void;
};

const SESSION_ID = "b7e6a1c2-3f4d-4a5b-8c9d-0e1f2a3b4c5d";

const hook = vi.hoisted(() => {
  return {
    current: {
      turns: [],
      phase: "idle" as "idle" | "streaming",
      isBusy: false,
      sessionId: "b7e6a1c2-3f4d-4a5b-8c9d-0e1f2a3b4c5d",
      send: vi.fn(async () => ({ kind: "started" })),
      startFresh: vi.fn(),
    } as {
      turns: Turn[];
      phase: "idle" | "streaming";
      isBusy: boolean;
      sessionId: string;
      send: (input: unknown) => Promise<{
        kind: string;
        status?: number;
        detail?: unknown;
      }>;
      startFresh: () => void;
    },
  };
});

vi.mock("../hooks/use-agent-turn", () => ({
  useAgentTurn: () => hook.current,
}));

function baseHook(): HookValue {
  return {
    turns: [],
    phase: "idle",
    isBusy: false,
    sessionId: SESSION_ID,
    send: vi.fn(
      async (): Promise<SendOutcomeLike> => ({ kind: "started" }),
    ),
    startFresh: vi.fn(),
  };
}

function setHook(overrides: Partial<HookValue> = {}): void {
  hook.current = { ...baseHook(), ...overrides };
}

function makeTurn(overrides: Partial<Turn>): Turn {
  return {
    id: 1,
    userText: null,
    sentAction: null,
    stages: [],
    deltas: "",
    plan: null,
    planState: "none",
    terminal: null,
    ...overrides,
  };
}

const TEXT_BLOCK_PLAN = {
  planVersion: "1",
  sessionId: SESSION_ID,
  turnId: 2,
  root: {
    type: "text_block",
    props: { body: "Assumption: over-ear, travel-first, under $200." },
    actions: [],
  },
};

const PREFERENCE_PLAN_ACTIONS = [
  {
    type: "select_preference",
    label: "Headphones",
    payload: { value: "headphones" },
  },
  {
    type: "select_preference",
    label: "Something else",
    payload: { value: "other" },
  },
];

const PREFERENCE_PLAN = {
  planVersion: "1",
  sessionId: SESSION_ID,
  turnId: 3,
  root: {
    type: "preference_picker",
    props: {
      question: "Which category are you shopping for?",
      options: ["Headphones", "Something else"],
    },
    actions: PREFERENCE_PLAN_ACTIONS,
  },
};

/** The composer textarea, addressed by its accessible label. */
function composerBox(): HTMLTextAreaElement {
  return screen.getByRole(
    "textbox",
    { name: "Message the shopping agent" },
  ) as HTMLTextAreaElement;
}

function sendMessage(text: string): void {
  fireEvent.change(composerBox(), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
}

describe("ShopPage transcript", () => {
  it("renders turns oldest to newest: user bubble, action line, prose, rendered plan", () => {
    setHook({
      turns: [
        makeTurn({ id: 1, userText: "Quiet headphones for long flights" }),
        makeTurn({
          id: 2,
          sentAction: {
            type: "select_preference",
            label: "Headphones",
            payload: { value: "headphones" },
          },
          stages: [
            "intent_parsed",
            "searching",
            "found_n",
            "researching",
            "ranking",
            "building_ui",
          ],
          deltas: "Based on your needs, here is my pick.",
          planState: "rendered",
          plan: TEXT_BLOCK_PLAN,
          terminal: { kind: "turn_end" },
        }),
      ],
    });
    render(<ShopPage />);

    expect(
      screen.getByText("Quiet headphones for long flights"),
    ).toBeInTheDocument();
    expect(screen.getByText("▸ Headphones")).toBeInTheDocument();
    expect(
      screen.getByText("Based on your needs, here is my pick."),
    ).toBeInTheDocument();
    expect(screen.getByTestId("plan-text_block")).toBeInTheDocument();
    expect(
      screen.getByText("Assumption: over-ear, travel-first, under $200."),
    ).toBeInTheDocument();

    // DOM order: user text → action line → prose → plan.
    const user = screen.getByText("Quiet headphones for long flights");
    const action = screen.getByText("▸ Headphones");
    const prose = screen.getByText("Based on your needs, here is my pick.");
    const plan = screen.getByTestId("plan-text_block");
    const follows = (first: Element, second: Element): boolean =>
      Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING);
    expect(follows(user, action)).toBe(true);
    expect(follows(action, prose)).toBe(true);
    expect(follows(prose, plan)).toBe(true);
  });

  it("shows a live region only on the last agent turn's prose", () => {
    setHook({
      turns: [
        makeTurn({ id: 1, deltas: "Earlier answer.", terminal: { kind: "turn_end" } }),
        makeTurn({ id: 2, deltas: "Latest answer.", terminal: { kind: "turn_end" } }),
      ],
    });
    render(<ShopPage />);

    const log = screen.getByRole("log", { name: "Conversation transcript" });
    expect(log).toBeInTheDocument();
    expect(screen.getByText("Earlier answer.")).not.toHaveAttribute("aria-live");
    expect(screen.getByText("Latest answer.")).toHaveAttribute(
      "aria-live",
      "polite",
    );
  });

  it("marks the error terminal as an inline Pencil-tone notice", () => {
    setHook({
      turns: [
        makeTurn({
          id: 1,
          userText: "surprise me",
          planState: "invalid",
          terminal: {
            kind: "error",
            message: "Invalid plan: unknown component type.",
            code: "structured_output",
          },
        }),
      ],
    });
    render(<ShopPage />);

    const notice = screen.getByTestId("turn-error");
    expect(notice).toHaveTextContent(
      "Invalid plan: unknown component type.",
    );
    expect(notice).toHaveClass("bg-secondary", "text-muted-foreground");
    expect(screen.queryByTestId("plan-text_block")).not.toBeInTheDocument();
  });
});

describe("ShopPage thinking states", () => {
  it("offers suggestion chips in the empty state and sends the prompt on click", () => {
    const send = vi.fn(
      async (): Promise<SendOutcomeLike> => ({ kind: "started" }),
    );
    setHook({ send });
    render(<ShopPage />);

    const chips = screen.getAllByTestId("suggestion-chip");
    expect(chips).toHaveLength(3);

    fireEvent.click(chips[0]);
    expect(send).toHaveBeenCalledWith({
      message:
        "Help me find the best headphones for long flights under $200. Noise cancellation and comfort matter most.",
      resume: false,
    });
  });

  it("scrolls the newest turn into view as turns arrive", () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    setHook({
      turns: [makeTurn({ id: 1, userText: "hello", deltas: "Hi." })],
    });
    render(<ShopPage />);
    expect(scrollIntoView).toHaveBeenCalled();
  });

  it("shows the thinking skeleton while streaming with no prose yet", () => {
    setHook({
      phase: "streaming",
      isBusy: true,
      turns: [makeTurn({ id: 1, userText: "recommend headphones" })],
    });
    render(<ShopPage />);

    const thinking = screen.getByTestId("turn-thinking");
    expect(thinking).toHaveAttribute("role", "status");
    expect(thinking).toHaveTextContent("Thinking…");
    expect(thinking.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
    expect(screen.queryByTestId("plan-skeleton")).not.toBeInTheDocument();
  });

  it("shows a plan skeleton once prose started and the plan has not landed", () => {
    setHook({
      phase: "streaming",
      isBusy: true,
      turns: [
        makeTurn({ id: 1, userText: "recommend headphones", deltas: "Here is my pick…" }),
      ],
    });
    render(<ShopPage />);

    expect(screen.getByTestId("plan-skeleton")).toBeInTheDocument();
    expect(screen.queryByTestId("turn-thinking")).not.toBeInTheDocument();
  });

  it("renders neither skeleton once the plan is rendered", () => {
    setHook({
      turns: [
        makeTurn({
          id: 1,
          userText: "recommend headphones",
          deltas: "Here is my pick.",
          planState: "rendered",
          plan: TEXT_BLOCK_PLAN,
          terminal: { kind: "turn_end" },
        }),
      ],
    });
    render(<ShopPage />);

    expect(screen.queryByTestId("turn-thinking")).not.toBeInTheDocument();
    expect(screen.queryByTestId("plan-skeleton")).not.toBeInTheDocument();
    expect(screen.getByTestId("plan-text_block")).toBeInTheDocument();
  });
});

describe("ShopPage composer", () => {
  it("locks the input while streaming and shows Working…", () => {
    setHook({
      phase: "streaming",
      isBusy: true,
      turns: [
        makeTurn({ id: 1, userText: "hello", terminal: { kind: "turn_end" } }),
      ],
    });
    render(<ShopPage />);

    const working = screen.getByRole("button", { name: "Working…" });
    expect(working).toBeDisabled();
    expect(composerBox()).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Send" })).not.toBeInTheDocument();
  });

  it("sends the trimmed message without resume in a fresh session", () => {
    const send = vi.fn(
      async (): Promise<SendOutcomeLike> => ({ kind: "started" }),
    );
    setHook({ send });
    render(<ShopPage />);

    sendMessage("  quiet over-ear headphones  ");

    expect(send).toHaveBeenCalledTimes(1);
    expect(send).toHaveBeenCalledWith({
      message: "quiet over-ear headphones",
      resume: false,
    });
    expect(composerBox()).toHaveValue("");
  });

  it("sends the first message of a rehydrated session with resume: true", () => {
    window.sessionStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({ sessionId: "rehydrated-session-id", live: true }),
    );
    const send = vi.fn(
      async (): Promise<SendOutcomeLike> => ({ kind: "started" }),
    );
    setHook({ send });
    render(<ShopPage />);

    sendMessage("still there?");

    expect(send).toHaveBeenCalledWith({
      message: "still there?",
      resume: true,
    });
    window.sessionStorage.clear();
  });

  it("sends a tapped plan action verbatim and never with resume", () => {
    const send = vi.fn(
      async (): Promise<SendOutcomeLike> => ({ kind: "started" }),
    );
    setHook({
      send,
      turns: [
        makeTurn({
          id: 1,
          deltas: "One question first.",
          planState: "rendered",
          plan: PREFERENCE_PLAN,
          terminal: { kind: "turn_end" },
        }),
      ],
    });
    render(<ShopPage />);

    fireEvent.click(screen.getByRole("button", { name: "Headphones" }));

    expect(send).toHaveBeenCalledWith({
      uiAction: PREFERENCE_PLAN_ACTIONS[0],
      resume: false,
    });
  });
});

describe("ShopPage 404 flow", () => {
  it("renders the one-time expiry notice above the composer", async () => {
    const send = vi.fn(
      async (): Promise<SendOutcomeLike> => ({
        kind: "http_error",
        status: 404,
        detail: { detail: "unknown_session" },
      }),
    );
    setHook({ send });
    render(<ShopPage />);

    sendMessage("still there?");

    const notice = await screen.findByTestId("session-expired-notice");
    expect(notice).toHaveTextContent(
      "Session expired — starting a fresh conversation.",
    );
    expect(send).toHaveBeenCalledWith({
      message: "still there?",
      resume: false,
    });
  });

  it("offers New conversation inline after the notice and starts fresh on click", async () => {
    const send = vi.fn(
      async (): Promise<SendOutcomeLike> => ({
        kind: "http_error",
        status: 404,
        detail: null,
      }),
    );
    const startFresh = vi.fn();
    setHook({ send, startFresh });
    render(<ShopPage />);

    sendMessage("still there?");
    const notice = await screen.findByTestId("session-expired-notice");

    // The notice carries its own New conversation affordance.
    const inlineNewConversation = within(notice).getByRole("button", {
      name: "New conversation",
    });
    fireEvent.click(inlineNewConversation);
    expect(startFresh).toHaveBeenCalledTimes(1);
  });

  it("clears the notice once a later send succeeds", async () => {
    let calls = 0;
    const send = vi.fn(async (): Promise<SendOutcomeLike> => {
      calls += 1;
      return calls === 1
        ? { kind: "http_error", status: 404, detail: null }
        : { kind: "started" };
    });
    setHook({ send });
    render(<ShopPage />);

    sendMessage("still there?");
    await screen.findByTestId("session-expired-notice");

    // The next successful send takes the notice down again.
    sendMessage("fresh question");
    await waitFor(() => {
      expect(screen.queryByTestId("session-expired-notice")).not.toBeInTheDocument();
    });
  });
});

describe("ShopPage session line", () => {
  it("shows the short session id and calls startFresh on New conversation", () => {
    setHook({});
    render(<ShopPage />);

    expect(screen.getByText(`Session ${SESSION_ID.slice(0, 8)}`)).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "New conversation" }),
    );
    expect(hook.current.startFresh).toHaveBeenCalledTimes(1);
  });
});

describe("ShopPage health badge", () => {
  const fetchMock = vi.fn<(...args: unknown[]) => Promise<Response>>();

  beforeEach(() => {
    fetchMock.mockReset();
    // Default: a never-resolving health check — non-badge tests are unaffected.
    fetchMock.mockImplementation(
      () => new Promise<Response>(() => undefined),
    );
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the backend mode reported by GET /health", async () => {
    fetchMock.mockImplementationOnce(
      async () =>
        new Response(JSON.stringify({ status: "ok", mode: "mock" }), {
          status: 200,
        }),
    );
    render(<ShopPage />);

    // The badge re-queries inside waitFor: loading renders a Skeleton div and
    // the resolved mode swaps it for a span (different element type).
    await waitFor(() => {
      expect(screen.getByTestId("health-badge")).toHaveTextContent("MOCK");
    });
    expect(
      screen.getByTestId("health-badge").querySelector(".animate-pulse"),
    ).toBeNull();
    expect(screen.getByTestId("health-badge")).toHaveAttribute(
      "data-mode",
      "mock",
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/health",
      { cache: "no-store" },
    );
  });

  it("shows a skeleton while the health check resolves, then the mode", async () => {
    fetchMock.mockImplementationOnce(
      () => new Promise<Response>(() => undefined),
    );
    render(<ShopPage />);
    expect(screen.getByTestId("health-badge").className).toContain(
      "animate-pulse",
    );
  });

  it("falls back to OFFLINE when the health check fails", async () => {
    fetchMock.mockImplementationOnce(() =>
      Promise.reject(new TypeError("Failed to fetch")),
    );
    render(<ShopPage />);

    await waitFor(() => {
      expect(screen.getByTestId("health-badge")).toHaveTextContent("OFFLINE");
    });
    expect(screen.getByTestId("health-badge")).toHaveAttribute(
      "data-mode",
      "offline",
    );
  });
});

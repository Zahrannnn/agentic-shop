"use client";

import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { Button } from "@/components/ui/button";

/**
 * The message input (Curator's Desk): a Desk-filled textarea that grows from
 * one row to four, Enter sends and Shift+Enter breaks the line, and a single
 * Teal Ink primary action. While a turn is in flight both the input and the
 * send control lock and the button honestly says "Working…" — calm progress,
 * never a spinner (PRODUCT.md principle 4).
 */

export type TurnComposerProps = {
  onSend: (message: string) => void;
  isBusy: boolean;
};

/** Four rows at text-[15px]/leading-6 (24px) plus vertical padding. */
const MAX_HEIGHT_PX = 4 * 24 + 16;

export function TurnComposer({ onSend, isBusy }: TurnComposerProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const trimmed = value.trim();
  const canSend = !isBusy && trimmed.length > 0;

  // Auto-shrink/grow between one and four rows.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) {
      return;
    }
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`;
  }, [value]);

  const submit = () => {
    if (!canSend) {
      return;
    }
    onSend(trimmed);
    setValue("");
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submit();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-end gap-3">
      <textarea
        ref={textareaRef}
        rows={1}
        name="message"
        aria-label="Message the shopping agent"
        placeholder="What are you looking for?"
        value={value}
        disabled={isBusy}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        className="max-h-28 min-h-10 w-full flex-1 resize-none overflow-y-auto rounded-md border bg-secondary px-3 py-2 text-[15px] leading-6 text-foreground transition-colors placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      />
      <Button type="submit" disabled={!canSend} className="shrink-0">
        {isBusy ? "Working…" : "Send"}
      </Button>
    </form>
  );
}

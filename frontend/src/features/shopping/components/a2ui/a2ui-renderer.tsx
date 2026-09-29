"use client";

import { useEffect, useMemo } from "react";
import {
  A2uiSurface,
  basicCatalog,
  type ReactComponentImplementation,
} from "@a2ui/react/v0_9";
import { Catalog, MessageProcessor, peekValue, type DataModel } from "@a2ui/web_core/v0_9";

import {
  PLAN_ACTION_TYPES,
  type PlanAction,
} from "../../validations/plan-schema";
import {
  SHOPPING_CATALOG_ID,
  blueprintSurfaceId,
  type A2uiMessage,
} from "../../validations/a2ui-schema";

/**
 * Renders one turn's plan through the REAL A2UI stack (D10 side-by-side demo):
 * a fresh `MessageProcessor` (official `@a2ui/react` + `@a2ui/web_core`,
 * v0.9) processes the validated message stream, and `A2uiSurface` renders the
 * resolved component tree with the basic catalog's React implementations.
 *
 * The backend pins a shopping catalog id in every `createSurface`, so the
 * basic catalog's components are re-registered under OUR id — the surface
 * machinery refuses unknown catalogs.
 *
 * Action fidelity: the transpiler encodes each plan action as a Button event
 * (`name = action.type`, `context = {**payload, "label"}`), so the listener
 * reconstructs the verbatim `PlanAction` and hands it to the SAME `onAction`
 * path the native renderer uses — both renderers send identical wire traffic.
 * The ONE exception is the multi-picker's `select_preferences` template (D11
 * stamping, the `withProduct` precedent): its CheckBoxes two-way-bind into
 * the surface data model, so an unstamped tap reads `/selections` and fills
 * `values` with the checked options — mirroring the native renderer's local
 * checkbox state.
 *
 * The processor is rebuilt only when the messages or handler change and is
 * disposed on cleanup; a processing failure (gate drift, not expected for
 * validated blueprints) renders a notice instead of crashing the transcript.
 */

export type A2uiRendererProps = {
  messages: A2uiMessage[];
  onAction: (action: PlanAction) => void;
};

/** The checked option names from the surface's `/selections` map (D11). */
function checkedSelections(dataModel: DataModel): string[] {
  const selections: unknown = peekValue(dataModel.getSignal("/selections"));
  if (typeof selections !== "object" || selections === null) {
    return [];
  }
  return Object.entries(selections as Record<string, unknown>)
    .filter(([, checked]) => checked === true)
    .map(([option]) => option);
}

export function A2uiRenderer({ messages, onAction }: A2uiRendererProps) {
  const { processor, surfaceId, error } = useMemo(() => {
    // Re-register the basic catalog's React implementations under OUR id —
    // the surface machinery refuses unknown catalog ids. The explicit generic
    // keeps the React `render` implementations visible to the type system.
    const shoppingCatalog = new Catalog<ReactComponentImplementation>(
      SHOPPING_CATALOG_ID,
      basicCatalog.protocolVersion,
      [...basicCatalog.components.values()],
      [...basicCatalog.functions.values()],
    );
    // Surfaces do not exist until the messages are processed, but the action
    // handler is constructed first — the closure reads through this holder.
    let activeDataModel: DataModel | null = null;
    const instance = new MessageProcessor<ReactComponentImplementation>(
      [shoppingCatalog],
      (action) => {
        const context = (action.context ?? {}) as Record<string, unknown>;
        const { label, ...payload } = context;
        // Fidelity guard: only the contracted action kinds ride the wire; an
        // unknown event name is dropped rather than smuggled through.
        if (!(PLAN_ACTION_TYPES as readonly string[]).includes(action.name)) {
          return;
        }
        let finalPayload = payload;
        if (
          action.name === "select_preferences" &&
          activeDataModel !== null &&
          (!Array.isArray(payload.values) || payload.values.length === 0)
        ) {
          // D11 stamping exception: the checkboxes wrote the user's picks
          // into the data model; stamp them before the action goes out.
          finalPayload = { ...payload, values: checkedSelections(activeDataModel) };
        }
        onAction({
          type: action.name as PlanAction["type"],
          label: typeof label === "string" ? label : action.name,
          payload: finalPayload,
        });
      },
    );
    try {
      instance.processMessages(messages);
    } catch (processingError) {
      instance.dispose();
      return { processor: null, surfaceId: null, error: processingError };
    }
    const created = blueprintSurfaceId({ messages });
    if (created !== null) {
      activeDataModel = instance.model.getSurface(created)?.dataModel ?? null;
    }
    return {
      processor: instance,
      surfaceId: created,
      error: null,
    };
  }, [messages, onAction]);

  useEffect(() => {
    return () => {
      processor?.dispose();
    };
  }, [processor]);

  if (error !== null || processor === null || surfaceId === null) {
    return (
      <p
        role="status"
        data-testid="a2ui-render-error"
        className="max-w-prose rounded-lg border bg-secondary p-4 text-sm text-muted-foreground"
      >
        This result couldn&apos;t be rendered through A2UI.
      </p>
    );
  }

  const surface = processor.model.getSurface(surfaceId);
  if (!surface) {
    return (
      <p
        role="status"
        data-testid="a2ui-render-error"
        className="max-w-prose rounded-lg border bg-secondary p-4 text-sm text-muted-foreground"
      >
        This result couldn&apos;t be rendered through A2UI.
      </p>
    );
  }

  return (
    <div
      data-testid="a2ui-surface"
      className="max-w-3xl rounded-lg border bg-card p-4"
    >
      <A2uiSurface surface={surface} />
    </div>
  );
}

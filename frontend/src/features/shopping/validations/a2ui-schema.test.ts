import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  A2UI_WIRE_VERSION,
  SHOPPING_CATALOG_ID,
  a2uiBlueprintSchema,
  blueprintSurfaceId,
  parseA2uiBlueprint,
} from "./a2ui-schema";

/**
 * Contract tests for the optional `a2ui_update` payload (D10): the golden
 * fixtures produced by the backend transpiler (`backend/fixtures/a2ui/`,
 * generated from `backend/fixtures/ui-plans/`) are the single source of
 * truth — every one must validate; known-bad mutations must be rejected.
 * (Same fs-read pattern as `plan-schema.test.ts`: node:path + import.meta,
 * never the jsdom-swapped global URL.)
 */

const GOLDENS_DIR = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../../..",
  "backend/fixtures/a2ui",
);
const GOLDEN_NAMES = [
  "cart-one-item.json",
  "comparison-two.json",
  "multi-picker-priorities.json",
  "preference-picker-category.json",
  "product-details.json",
  "product-grid-flights.json",
];

function loadGolden(name: string): unknown {
  return JSON.parse(readFileSync(resolve(GOLDENS_DIR, name), "utf-8"));
}

describe("a2ui blueprint schema — golden acceptance", () => {
  it.each(GOLDEN_NAMES)("accepts %s", (name) => {
    // The golden files hold the bare message list; the wire wraps it in
    // {"messages": [...]} (routes adds the envelope).
    const result = parseA2uiBlueprint({ messages: loadGolden(name) });
    expect(result.ok).toBe(true);
  });

  it("exposes the createSurface surface id", () => {
    const result = parseA2uiBlueprint({
      messages: loadGolden("product-grid-flights.json"),
    });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(blueprintSurfaceId(result.blueprint)).toBe("spec-fixture-1");
    }
  });

  it("carries a deleteSurface first for the amended cart stream", () => {
    const messages = [
      { version: A2UI_WIRE_VERSION, deleteSurface: { surfaceId: "s-1-1" } },
      {
        version: A2UI_WIRE_VERSION,
        createSurface: { surfaceId: "s-1-3", catalogId: SHOPPING_CATALOG_ID },
      },
    ];
    const result = parseA2uiBlueprint({ messages });
    expect(result.ok).toBe(true);
    expect(
      result.ok && result.blueprint.messages.some((m) => "deleteSurface" in m),
    ).toBe(true);
  });
});

describe("a2ui blueprint schema — rejection matrix", () => {
  it("rejects a wrong wire version", () => {
    const result = parseA2uiBlueprint({
      messages: [
        {
          version: "v1.0",
          createSurface: { surfaceId: "s", catalogId: SHOPPING_CATALOG_ID },
        },
      ],
    });
    expect(result.ok).toBe(false);
  });

  it("rejects a foreign catalog id", () => {
    const result = parseA2uiBlueprint({
      messages: [
        {
          version: A2UI_WIRE_VERSION,
          createSurface: { surfaceId: "s", catalogId: "https://evil.test/x" },
        },
      ],
    });
    expect(result.ok).toBe(false);
  });

  it("rejects an empty message list and a wrong envelope", () => {
    expect(parseA2uiBlueprint({ messages: [] }).ok).toBe(false);
    expect(parseA2uiBlueprint({ blueprint: [] }).ok).toBe(false);
    expect(parseA2uiBlueprint(null).ok).toBe(false);
  });

  it("rejects an unknown message kind", () => {
    const result = parseA2uiBlueprint({
      messages: [{ version: A2UI_WIRE_VERSION, repaintEverything: {} }],
    });
    expect(result.ok).toBe(false);
  });

  it("schema rejects non-object components entries", () => {
    const result = a2uiBlueprintSchema.safeParse({
      messages: [
        {
          version: A2UI_WIRE_VERSION,
          updateComponents: { surfaceId: "s", components: ["nope"] },
        },
      ],
    });
    expect(result.success).toBe(false);
  });
});

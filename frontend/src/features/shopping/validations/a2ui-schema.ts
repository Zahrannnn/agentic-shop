import { z } from "zod";

/**
 * Zod mirror of the OPTIONAL `a2ui_update` payload (DECISIONS.md D10,
 * FRONTEND_GUIDE.md §4 row 3a): `{"messages": [...]}` carrying an A2UI v0.9
 * message stream for the turn's surface.
 *
 * Deliberately a SIBLING of `plan-schema.ts` — the frozen native plan
 * contract is untouched. This gate checks only what the renderer depends on
 * (wire version, our shopping catalog id, the four message kinds, a resolvable
 * surface id); the official `MessageProcessor` performs the deep component
 * validation when it processes the stream. An invalid blueprint is ignored —
 * it must NEVER fail a turn whose native plan is fine.
 */

/** Wire protocol version the backend transpiler pins (app/a2ui/transpile.py). */
export const A2UI_WIRE_VERSION = "v0.9";

/** Catalog identifier the backend emits in every `createSurface`. */
export const SHOPPING_CATALOG_ID =
  "https://agentic-shop.local/a2ui/catalogs/shopping/v1.json";

const createSurfaceSchema = z.object({
  surfaceId: z.string().min(1),
  catalogId: z.literal(SHOPPING_CATALOG_ID),
});

const updateComponentsSchema = z.object({
  surfaceId: z.string().min(1),
  components: z.array(z.record(z.string(), z.unknown())),
});

const updateDataModelSchema = z.object({
  surfaceId: z.string().min(1),
  path: z.string().optional(),
  value: z.unknown().optional(),
});

const deleteSurfaceSchema = z.object({
  surfaceId: z.string().min(1),
});

const messageSchema = z.union([
  z
    .object({
      version: z.literal(A2UI_WIRE_VERSION),
      createSurface: createSurfaceSchema,
    })
    .strict(),
  z
    .object({
      version: z.literal(A2UI_WIRE_VERSION),
      updateComponents: updateComponentsSchema,
    })
    .strict(),
  z
    .object({
      version: z.literal(A2UI_WIRE_VERSION),
      updateDataModel: updateDataModelSchema,
    })
    .strict(),
  z
    .object({
      version: z.literal(A2UI_WIRE_VERSION),
      deleteSurface: deleteSurfaceSchema,
    })
    .strict(),
]);

export const a2uiBlueprintSchema = z
  .object({
    messages: z.array(messageSchema).min(1),
  })
  .strict();

export type A2uiMessage = z.infer<typeof messageSchema>;
export type A2uiBlueprint = z.infer<typeof a2uiBlueprintSchema>;

export type ParseA2uiBlueprintResult =
  | { ok: true; blueprint: A2uiBlueprint }
  | { ok: false; errors: string[] };

/**
 * Validate one raw `a2ui_update` payload. Failure is a *skip*, never a turn
 * error: the caller drops the blueprint and the native plan still renders.
 */
export function parseA2uiBlueprint(raw: unknown): ParseA2uiBlueprintResult {
  const result = a2uiBlueprintSchema.safeParse(raw);
  if (result.success) {
    return { ok: true, blueprint: result.data };
  }
  return { ok: false, errors: result.error.issues.map((issue) => issue.message) };
}

/** The surface id of the first `createSurface` (the turn's surface), if any. */
export function blueprintSurfaceId(blueprint: A2uiBlueprint): string | null {
  const created = blueprint.messages.find(
    (message) => "createSurface" in message,
  ) as { createSurface: { surfaceId: string } } | undefined;
  return created?.createSurface.surfaceId ?? null;
}

import { z } from "zod";

import { KNOWN_ATTRIBUTES } from "../utils/catalog-refs";

/**
 * Zod mirror of the UI plan wire contract
 * (`specs/001-backend-agent-scaffold/contracts/ui-dsl.md`).
 *
 * Field names are the camelCase wire names verbatim — the backend emits
 * camelCase and there is no rename layer. The five fixtures in
 * `backend/fixtures/ui-plans/` are the source of truth: every fixture must
 * parse, every known-bad mutation must be rejected (plan-schema.test.ts).
 */

/** The fixed component registry; the renderer has no fallback entry. */
export const PLAN_COMPONENT_TYPES = [
  "product_grid",
  "preference_picker",
  "comparison_table",
  "product_details",
  "cart_view",
  "text_block",
  "multi_picker",
] as const;

export type PlanComponentType = (typeof PLAN_COMPONENT_TYPES)[number];

/** Full action vocabulary of the contract (D11 additions at the end). */
export const PLAN_ACTION_TYPES = [
  "compare",
  "details",
  "select_preference",
  "add_to_cart",
  "remove_from_cart",
  "choose",
  "refine",
  "set_quantity",
  "select_preferences",
] as const;

/** Non-empty display label plus an open payload object, defaulting to `{}`. */
export const planActionSchema = z.object({
  type: z.enum(PLAN_ACTION_TYPES),
  label: z.string().min(1),
  payload: z.record(z.string(), z.unknown()).default({}),
});

export type PlanAction = z.infer<typeof planActionSchema>;

/** Wire-protocol alias: the SSE/chat layer sends this object verbatim. */
export type UIAction = PlanAction;

/** Per-component allowed action sets (contract validation rule 4). */
const ALLOWED_ACTIONS_BY_TYPE: Readonly<
  Record<PlanComponentType, readonly PlanAction["type"][]>
> = {
  product_grid: ["compare", "details", "add_to_cart", "refine"],
  preference_picker: ["select_preference"],
  comparison_table: ["choose"],
  product_details: [],
  cart_view: ["remove_from_cart", "set_quantity"],
  text_block: [],
  multi_picker: ["select_preferences"],
};

const gridProductSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  priceUsd: z.number(),
  ancType: z.string().min(1),
});

/** Refinement-bar vocabulary (D11). */
export const REFINEMENT_SORTS = [
  "relevance",
  "price_asc",
  "price_desc",
  "rating",
] as const;
export type RefinementSort = (typeof REFINEMENT_SORTS)[number];

export const refinementFiltersSchema = z
  .object({
    ancOnly: z.boolean().nullish(),
    minBatteryHours: z.number().positive().nullish(),
    maxPriceUsd: z.number().positive().nullish(),
  })
  .default({});

export const refinementStateSchema = z.object({
  sort: z.enum(REFINEMENT_SORTS).default("relevance"),
  filters: refinementFiltersSchema,
});

export type RefinementFilters = z.infer<typeof refinementFiltersSchema>;
export type RefinementState = z.infer<typeof refinementStateSchema>;

const productGridComponentSchema = z.object({
  type: z.literal("product_grid"),
  props: z.object({
    title: z.string().min(1),
    productIds: z.array(z.string()).min(1).max(6),
    ranked: z.boolean(),
    products: z.array(gridProductSchema).optional(),
    /** Refinement-bar state (D11) — present exactly when refine chips ride the actions. */
    refinement: refinementStateSchema.optional(),
  }),
  actions: z.array(planActionSchema),
});

const preferencePickerComponentSchema = z.object({
  type: z.literal("preference_picker"),
  props: z.object({
    question: z.string().min(1),
    options: z.array(z.string().min(1)).min(2).max(4),
  }),
  actions: z.array(planActionSchema),
});

const comparisonTableCellValueSchema = z.union([
  z.string(),
  z.number(),
  z.boolean(),
  z.null(),
]);

const comparisonTableComponentSchema = z.object({
  type: z.literal("comparison_table"),
  props: z.object({
    productIds: z.array(z.string()).min(2).max(3),
    attributes: z.array(z.string().min(1)).min(1),
    /** Render aid from the backend: {productId: {attribute: value}}. */
    values: z.record(z.string(), z.record(z.string(), comparisonTableCellValueSchema)).optional(),
  }),
  actions: z.array(planActionSchema),
});

const reviewScoresSchema = z.object({
  comfort: z.number(),
  anc: z.number(),
  sound: z.number(),
  battery: z.number(),
  value: z.number(),
});

const productDetailsComponentSchema = z.object({
  type: z.literal("product_details"),
  props: z.object({
    productId: z.string().min(1),
    showQuotes: z.boolean(),
    /** Catalog snapshot fields (additive): present on current plans. */
    productName: z.string().min(1).optional(),
    brand: z.string().min(1).optional(),
    priceUsd: z.number().optional(),
    batteryHours: z.number().optional(),
    weightG: z.number().optional(),
    ancType: z.string().min(1).optional(),
    driverMm: z.number().optional(),
    codecs: z.array(z.string()).optional(),
    multipoint: z.boolean().optional(),
    folding: z.boolean().optional(),
    reviewScores: reviewScoresSchema.partial().optional(),
    quotes: z.array(z.string()).optional(),
  }),
  actions: z.array(planActionSchema),
});

const cartLineSchema = z.object({
  productId: z.string().min(1),
  quantity: z.number().int().min(1).max(10),
  /** Catalog unit price (D12) — the client recompute's optimistic totals. */
  unitPriceUsd: z.number().nonnegative(),
});

const cartViewComponentSchema = z.object({
  type: z.literal("cart_view"),
  props: z.object({
    items: z.array(cartLineSchema),
    totalUsd: z.number().nonnegative(),
  }),
  actions: z.array(planActionSchema),
});

const textBlockComponentSchema = z.object({
  type: z.literal("text_block"),
  props: z.object({
    heading: z.string().optional(),
    body: z.string().min(1),
  }),
  actions: z.array(planActionSchema),
});

const multiPickerComponentSchema = z.object({
  type: z.literal("multi_picker"),
  props: z.object({
    question: z.string().min(1),
    options: z.array(z.string().min(1)).min(2).max(6),
    maxSelect: z.number().int().min(1).max(3).default(2),
  }),
  actions: z.array(planActionSchema),
});

const REFINEMENT_FILTER_KEYS: ReadonlySet<string> = new Set([
  "ancOnly",
  "minBatteryHours",
  "maxPriceUsd",
]);

export const planComponentSchema = z
  .discriminatedUnion("type", [
    productGridComponentSchema,
    preferencePickerComponentSchema,
    comparisonTableComponentSchema,
    productDetailsComponentSchema,
    cartViewComponentSchema,
    textBlockComponentSchema,
    multiPickerComponentSchema,
  ])
  .superRefine((component, ctx) => {
    const allowed = ALLOWED_ACTIONS_BY_TYPE[component.type];
    component.actions.forEach((action, index) => {
      if (!allowed.includes(action.type)) {
        ctx.addIssue({
          code: "custom",
          path: ["actions", index, "type"],
          message: `action "${action.type}" is not allowed on "${component.type}" components`,
        });
        return;
      }
      // Payload shape rules (D11) — the structural mirror of the backend's
      // action-payload checks in app/dsl/validate.py.
      if (action.type === "set_quantity") {
        const quantity = action.payload.quantity;
        if (
          typeof quantity !== "number" ||
          !Number.isInteger(quantity) ||
          quantity < 1 ||
          quantity > 10
        ) {
          ctx.addIssue({
            code: "custom",
            path: ["actions", index, "payload", "quantity"],
            message: "set_quantity requires an integer payload.quantity in [1, 10]",
          });
        }
      }
      if (action.type === "refine") {
        // Flat payload (D11): sort + filter scalars at the top level, so the
        // object rides an A2UI event context unchanged.
        const unknownKeys = Object.keys(action.payload).filter(
          (key) => key !== "label" && key !== "sort" && !REFINEMENT_FILTER_KEYS.has(key),
        );
        for (const key of unknownKeys) {
          ctx.addIssue({
            code: "custom",
            path: ["actions", index, "payload", key],
            message: `unknown refine payload key "${key}"`,
          });
        }
        const { sort } = action.payload as { sort?: unknown };
        if (
          sort !== undefined &&
          !REFINEMENT_SORTS.includes(sort as RefinementSort)
        ) {
          ctx.addIssue({
            code: "custom",
            path: ["actions", index, "payload", "sort"],
            message: `refine payload.sort "${String(sort)}" is outside the refinement vocabulary`,
          });
        }
        for (const key of ["minBatteryHours", "maxPriceUsd"] as const) {
          const value = action.payload[key];
          if (
            value !== undefined &&
            value !== null &&
            (typeof value !== "number" || value <= 0)
          ) {
            ctx.addIssue({
              code: "custom",
              path: ["actions", index, "payload", key],
              message: `refine "${key}" must be a positive number`,
            });
          }
        }
        const ancOnly = action.payload.ancOnly;
        if (ancOnly !== undefined && ancOnly !== null && typeof ancOnly !== "boolean") {
          ctx.addIssue({
            code: "custom",
            path: ["actions", index, "payload", "ancOnly"],
            message: "refine \"ancOnly\" must be a boolean",
          });
        }
      }
      if (action.type === "select_preferences") {
        const values = action.payload.values;
        if (
          values !== undefined &&
          (typeof values !== "object" ||
            !Array.isArray(values) ||
            values.some((item) => typeof item !== "string"))
        ) {
          ctx.addIssue({
            code: "custom",
            path: ["actions", index, "payload", "values"],
            message: "select_preferences payload.values must be a list of option names",
          });
        }
      }
    });
    // Refinement coupling (D11): a grid carries a refinement state exactly
    // when it offers refine chips.
    if (component.type === "product_grid") {
      const refineCount = component.actions.filter(
        (action) => action.type === "refine",
      ).length;
      if (refineCount > 8) {
        ctx.addIssue({
          code: "custom",
          path: ["actions"],
          message: `product_grid carries ${refineCount} refine actions (max 8)`,
        });
      }
      if (refineCount > 0 && component.props.refinement === undefined) {
        ctx.addIssue({
          code: "custom",
          path: ["props", "refinement"],
          message: "product_grid with refine actions must carry a refinement state",
        });
      }
      if (refineCount === 0 && component.props.refinement !== undefined) {
        ctx.addIssue({
          code: "custom",
          path: ["props", "refinement"],
          message: "product_grid with a refinement state must carry refine actions",
        });
      }
    }
  });

export type PlanComponent = z.infer<typeof planComponentSchema>;

type ComponentOf<T extends PlanComponentType> = Extract<PlanComponent, { type: T }>;

export type ProductGridProps = ComponentOf<"product_grid">["props"];
export type PreferencePickerProps = ComponentOf<"preference_picker">["props"];
export type ComparisonTableProps = ComponentOf<"comparison_table">["props"];
export type ProductDetailsProps = ComponentOf<"product_details">["props"];
export type CartViewProps = ComponentOf<"cart_view">["props"];
export type TextBlockProps = ComponentOf<"text_block">["props"];
export type MultiPickerProps = ComponentOf<"multi_picker">["props"];
export type CartLine = z.infer<typeof cartLineSchema>;

/** Plan envelope (contract validation rule 1). */
export const uiPlanSchema = z.object({
  planVersion: z.literal("1"),
  sessionId: z.string().min(1),
  turnId: z.number().int().min(1),
  /**
   * Bounded amendment (D2 amendment): a `cart_view` plan may point at the
   * earlier cart plan turn it supersedes — the client replaces THAT turn's
   * plan region in place instead of appending a duplicate cart section.
   * Absent on every strictly full-replace plan (the fixtures).
   */
  amendsTurnId: z.number().int().min(1).optional(),
  root: planComponentSchema,
});

export type UiPlan = z.infer<typeof uiPlanSchema>;

const KNOWN_ATTRIBUTE_SET: ReadonlySet<string> = new Set(KNOWN_ATTRIBUTES);

/** Action types whose `payload.productId` must reference the catalog. */
const ACTION_TYPES_CARRYING_PRODUCT_ID: ReadonlySet<PlanAction["type"]> = new Set([
  "compare",
  "details",
  "add_to_cart",
  "choose",
  "remove_from_cart",
  "set_quantity",
]);

/**
 * Catalog-level rules enforced outside Zod (the schema stays decoupled from
 * the catalog data): every referenced `productId` must exist in the catalog,
 * every picker option needs a matching `select_preference` action, a
 * comparison table carries at most one `choose` action, and comparison
 * attributes stay within the known whitelist. Returns human-readable
 * violation messages; empty array means the plan is clean.
 */
export function validateProductRefs(
  plan: UiPlan,
  validIds: ReadonlySet<string>,
): string[] {
  const violations: string[] = [];

  const checkId = (id: unknown, where: string): void => {
    if (typeof id === "string" && !validIds.has(id)) {
      violations.push(`unknown catalog id "${id}" at ${where}`);
    }
  };

  const { root } = plan;

  switch (root.type) {
    case "product_grid":
      root.props.productIds.forEach((id, index) =>
        checkId(id, `root.props.productIds[${index}]`),
      );
      break;
    case "preference_picker":
      root.props.options.forEach((option) => {
        const matched = root.actions.some(
          (action) =>
            action.type === "select_preference" && action.label === option,
        );
        if (!matched) {
          violations.push(
            `option "${option}" has no matching select_preference action`,
          );
        }
      });
      break;
    case "multi_picker": {
      // D11 stamping exception: the renderer fills `values` from its local
      // checkbox state, so a FILLED values list must stay within the
      // options and the maxSelect bound. An empty/absent list is the
      // unstamped wire template.
      const action = root.actions.find(
        (candidate) => candidate.type === "select_preferences",
      );
      if (!action) {
        violations.push("multi_picker has no select_preferences action");
        break;
      }
      const values = action.payload.values;
      if (Array.isArray(values) && values.length > 0) {
        values.forEach((value, index) => {
          if (!root.props.options.includes(value as string)) {
            violations.push(
              `select_preferences values[${index}] "${String(value)}" is not an option`,
            );
          }
        });
        if (values.length > root.props.maxSelect) {
          violations.push(
            `select_preferences carries ${values.length} values (maxSelect ${root.props.maxSelect})`,
          );
        }
      }
      break;
    }
    case "comparison_table": {
      root.props.productIds.forEach((id, index) =>
        checkId(id, `root.props.productIds[${index}]`),
      );
      const chooseCount = root.actions.filter(
        (action) => action.type === "choose",
      ).length;
      if (chooseCount > 1) {
        violations.push(
          `comparison_table carries ${chooseCount} choose actions (max 1)`,
        );
      }
      root.props.attributes.forEach((attribute, index) => {
        if (!KNOWN_ATTRIBUTE_SET.has(attribute)) {
          violations.push(
            `unknown comparison attribute "${attribute}" at root.props.attributes[${index}]`,
          );
        }
      });
      break;
    }
    case "product_details":
      checkId(root.props.productId, "root.props.productId");
      break;
    case "cart_view":
      root.props.items.forEach((item, index) =>
        checkId(item.productId, `root.props.items[${index}].productId`),
      );
      break;
    case "text_block":
      break;
  }

  root.actions.forEach((action, index) => {
    if (!ACTION_TYPES_CARRYING_PRODUCT_ID.has(action.type)) {
      return;
    }
    checkId(action.payload.productId, `root.actions[${index}].payload.productId`);
  });

  return violations;
}

export type ParseUiPlanResult =
  | { ok: true; plan: UiPlan }
  | { ok: false; errors: string[] };

type FlatIssue = { path: PropertyKey[]; message: string };

const formatIssue = (issue: FlatIssue): string => {
  const path = issue.path.map(String).join(".");
  return path ? `${path}: ${issue.message}` : issue.message;
};

/**
 * One-call boundary gate: Zod safeParse, then the optional catalog-level
 * ref validation. Never throws — invalid plans come back as `{ ok: false }`
 * with human-readable error strings.
 */
export function parseUiPlan(
  raw: unknown,
  validIds?: ReadonlySet<string>,
): ParseUiPlanResult {
  const parsed = uiPlanSchema.safeParse(raw);
  if (!parsed.success) {
    return { ok: false, errors: parsed.error.issues.map(formatIssue) };
  }
  if (validIds) {
    const violations = validateProductRefs(parsed.data, validIds);
    if (violations.length > 0) {
      return { ok: false, errors: violations };
    }
  }
  return { ok: true, plan: parsed.data };
}

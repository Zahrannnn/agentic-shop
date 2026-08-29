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
] as const;

export type PlanComponentType = (typeof PLAN_COMPONENT_TYPES)[number];

/** Full action vocabulary of the contract. */
const PLAN_ACTION_TYPES = [
  "compare",
  "details",
  "select_preference",
  "add_to_cart",
  "remove_from_cart",
  "choose",
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
  product_grid: ["compare", "details", "add_to_cart"],
  preference_picker: ["select_preference"],
  comparison_table: ["choose"],
  product_details: [],
  cart_view: ["remove_from_cart"],
  text_block: [],
};

const productGridComponentSchema = z.object({
  type: z.literal("product_grid"),
  props: z.object({
    title: z.string().min(1),
    productIds: z.array(z.string()).min(1).max(6),
    ranked: z.boolean(),
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

const productDetailsComponentSchema = z.object({
  type: z.literal("product_details"),
  props: z.object({
    productId: z.string().min(1),
    showQuotes: z.boolean(),
  }),
  actions: z.array(planActionSchema),
});

const cartLineSchema = z.object({
  productId: z.string().min(1),
  quantity: z.number().int().min(1).max(10),
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

export const planComponentSchema = z
  .discriminatedUnion("type", [
    productGridComponentSchema,
    preferencePickerComponentSchema,
    comparisonTableComponentSchema,
    productDetailsComponentSchema,
    cartViewComponentSchema,
    textBlockComponentSchema,
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
      }
    });
  });

export type PlanComponent = z.infer<typeof planComponentSchema>;

type ComponentOf<T extends PlanComponentType> = Extract<PlanComponent, { type: T }>;

export type ProductGridProps = ComponentOf<"product_grid">["props"];
export type PreferencePickerProps = ComponentOf<"preference_picker">["props"];
export type ComparisonTableProps = ComponentOf<"comparison_table">["props"];
export type ProductDetailsProps = ComponentOf<"product_details">["props"];
export type CartViewProps = ComponentOf<"cart_view">["props"];
export type TextBlockProps = ComponentOf<"text_block">["props"];
export type CartLine = z.infer<typeof cartLineSchema>;

/** Plan envelope (contract validation rule 1). */
export const uiPlanSchema = z.object({
  planVersion: z.literal("1"),
  sessionId: z.string().min(1),
  turnId: z.number().int().min(1),
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

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { CATALOG_IDS } from "../utils/catalog-refs";
import {
  parseUiPlan,
  validateProductRefs,
  type ParseUiPlanResult,
  type PlanComponentType,
  type UiPlan,
} from "./plan-schema";

// Fixture resolution assumes the monorepo root: `frontend/` and `backend/` are
// siblings in one checkout (data-model.md "Fixture loader", research.md R5).
// From `src/features/shopping/validations/` it is exactly five levels up.
// Paths go through node:path (not the global URL): vitest's jsdom environment
// swaps in jsdom's URL constructor, which resolves against http://localhost.
const VALIDATIONS_DIR = dirname(fileURLToPath(import.meta.url));
const FIXTURES_DIR = resolve(VALIDATIONS_DIR, "../../../../..", "backend/fixtures/ui-plans");

const FIXTURE_NAMES = [
  "product-grid-flights",
  "preference-picker-category",
  "comparison-two",
  "product-details",
  "cart-one-item",
] as const;

type FixtureName = (typeof FIXTURE_NAMES)[number];

const loadFixture = (name: FixtureName): unknown =>
  JSON.parse(readFileSync(resolve(FIXTURES_DIR, `${name}.json`), "utf8"));

// Fixtures are plain JSON, so a JSON round-trip is an exact deep copy and
// lets rejection tests mutate without touching the loader cache.
const loadFixtureCopy = (name: FixtureName): Record<string, unknown> =>
  JSON.parse(JSON.stringify(loadFixture(name))) as Record<string, unknown>;

function expectOk(result: ParseUiPlanResult): Extract<ParseUiPlanResult, { ok: true }> {
  if (!result.ok) {
    throw new Error(`expected ok, got errors: ${result.errors.join("; ")}`);
  }
  return result;
}

function expectRejected(result: ParseUiPlanResult): string[] {
  expect(result.ok).toBe(false);
  if (result.ok) {
    throw new Error("expected rejection");
  }
  expect(result.errors.length).toBeGreaterThan(0);
  return result.errors;
}

function expectRoot<T extends PlanComponentType>(
  plan: UiPlan,
  type: T,
): Extract<UiPlan["root"], { type: T }> {
  if (plan.root.type !== type) {
    throw new Error(`expected root type "${type}", got "${plan.root.type}"`);
  }
  return plan.root as Extract<UiPlan["root"], { type: T }>;
}

describe("fixture acceptance (backend fixtures parse through the gate)", () => {
  it.each(FIXTURE_NAMES)("%s.json parses with the catalog mirror", (name) => {
    const result = parseUiPlan(loadFixture(name), CATALOG_IDS);
    expect(result.ok).toBe(true);
  });

  it("round-trips the product grid fixture", () => {
    const { plan } = expectOk(parseUiPlan(loadFixture("product-grid-flights"), CATALOG_IDS));
    const root = expectRoot(plan, "product_grid");
    expect(root.props.title).toBe("Best matches for long flights");
    expect(root.props.productIds).toEqual([
      "aurora-hush-pro",
      "cloudline-air",
      "maple-ridge-comfort-150",
    ]);
    expect(root.props.ranked).toBe(true);
    expect(root.actions.map((action) => action.type)).toEqual([
      "compare",
      "details",
      "add_to_cart",
    ]);
    expect(root.actions.map((action) => action.label)).toEqual([
      "Compare",
      "Details",
      "Add to cart",
    ]);
    expect(plan.planVersion).toBe("1");
    expect(plan.sessionId).toBe("spec-fixture");
    expect(plan.turnId).toBe(1);
  });

  it("round-trips the preference picker fixture", () => {
    const { plan } = expectOk(
      parseUiPlan(loadFixture("preference-picker-category"), CATALOG_IDS),
    );
    const root = expectRoot(plan, "preference_picker");
    expect(root.props.question).toBe("Which category are you shopping for?");
    expect(root.props.options).toEqual(["Headphones", "Something else"]);
    expect(root.actions.map((action) => action.type)).toEqual([
      "select_preference",
      "select_preference",
    ]);
    expect(root.actions[0]?.label).toBe("Headphones");
    expect(root.actions[0]?.payload).toEqual({ value: "headphones" });
    expect(root.actions[1]?.label).toBe("Something else");
    expect(root.actions[1]?.payload).toEqual({ value: "other" });
  });

  it("round-trips the comparison table fixture", () => {
    const { plan } = expectOk(parseUiPlan(loadFixture("comparison-two"), CATALOG_IDS));
    const root = expectRoot(plan, "comparison_table");
    expect(root.props.productIds).toEqual(["aurora-hush-pro", "cloudline-air"]);
    expect(root.props.attributes).toEqual([
      "price_usd",
      "battery_hours",
      "weight_g",
      "anc_type",
      "comfort",
    ]);
    expect(root.actions).toHaveLength(1);
    expect(root.actions[0]?.type).toBe("choose");
    expect(root.actions[0]?.payload).toEqual({ productId: "aurora-hush-pro" });
  });

  it("round-trips the product details fixture", () => {
    const { plan } = expectOk(parseUiPlan(loadFixture("product-details"), CATALOG_IDS));
    const root = expectRoot(plan, "product_details");
    expect(root.props.productId).toBe("aurora-hush-pro");
    expect(root.props.showQuotes).toBe(true);
    expect(root.actions).toEqual([]);
  });

  it("round-trips the cart view fixture", () => {
    const { plan } = expectOk(parseUiPlan(loadFixture("cart-one-item"), CATALOG_IDS));
    const root = expectRoot(plan, "cart_view");
    expect(root.props.items).toEqual([{ productId: "aurora-hush-pro", quantity: 1 }]);
    expect(root.props.totalUsd).toBe(179);
    expect(root.actions[0]?.type).toBe("remove_from_cart");
    expect(root.actions[0]?.payload).toEqual({ productId: "aurora-hush-pro" });
  });

  it("defaults a missing action payload to an empty object", () => {
    const raw = {
      planVersion: "1",
      sessionId: "session-1",
      turnId: 1,
      root: {
        type: "product_grid",
        props: {
          title: "Fresh picks",
          productIds: ["aurora-hush-pro"],
          ranked: false,
        },
        actions: [{ type: "compare", label: "Compare" }],
      },
    };
    const { plan } = expectOk(parseUiPlan(raw, CATALOG_IDS));
    const root = expectRoot(plan, "product_grid");
    expect(root.actions[0]?.payload).toEqual({});
  });
});

describe("rejection matrix (known-bad mutations fail with an error string)", () => {
  it("rejects an unknown root type", () => {
    const raw = loadFixtureCopy("product-grid-flights");
    (raw.root as Record<string, unknown>).type = "video_player";
    const errors = expectRejected(parseUiPlan(raw, CATALOG_IDS));
    expect(errors.join("\n")).toContain("Invalid discriminator value");
  });

  it("rejects a foreign productId", () => {
    const raw = loadFixtureCopy("product-grid-flights");
    (raw.root as Record<string, unknown>).props = {
      title: "Best matches for long flights",
      productIds: ["aurora-hush-pro", "off-catalog-thing"],
      ranked: true,
    };
    const errors = expectRejected(parseUiPlan(raw, CATALOG_IDS));
    expect(errors.join("\n")).toContain("off-catalog-thing");
  });

  it("rejects a grid with 7 productIds", () => {
    const raw = loadFixtureCopy("product-grid-flights");
    (raw.root as Record<string, unknown>).props = {
      title: "Too many",
      productIds: [
        "aurora-hush-pro",
        "cloudline-air",
        "skyline-hush",
        "volt-enduro-70",
        "pinegrove-bass-40",
        "pinegrove-day-50",
        "harbor-lite-anc",
      ],
      ranked: true,
    };
    expectRejected(parseUiPlan(raw, CATALOG_IDS));
  });

  it("rejects a disallowed action on a text_block", () => {
    const raw = {
      planVersion: "1",
      sessionId: "session-1",
      turnId: 1,
      root: {
        type: "text_block",
        props: { body: "Assumption: you want over-ear headphones." },
        actions: [{ type: "compare", label: "Compare" }],
      },
    };
    const errors = expectRejected(parseUiPlan(raw, CATALOG_IDS));
    expect(errors.join("\n")).toContain("compare");
  });

  it("rejects a picker option without a matching select_preference action", () => {
    const raw = loadFixtureCopy("preference-picker-category");
    (raw.root as Record<string, unknown>).actions = [
      { type: "select_preference", label: "Headphones", payload: { value: "headphones" } },
    ];
    const errors = expectRejected(parseUiPlan(raw, CATALOG_IDS));
    expect(errors.join("\n")).toContain("Something else");
  });

  it("rejects planVersion \"2\"", () => {
    const raw = loadFixtureCopy("product-grid-flights");
    raw.planVersion = "2";
    const errors = expectRejected(parseUiPlan(raw, CATALOG_IDS));
    expect(errors.join("\n")).toContain("planVersion");
  });

  it("rejects two choose actions on a comparison table", () => {
    const raw = loadFixtureCopy("comparison-two");
    (raw.root as Record<string, unknown>).actions = [
      { type: "choose", label: "Choose Aurora Hush Pro", payload: { productId: "aurora-hush-pro" } },
      { type: "choose", label: "Choose Cloudline Air", payload: { productId: "cloudline-air" } },
    ];
    const errors = expectRejected(parseUiPlan(raw, CATALOG_IDS));
    expect(errors.join("\n")).toContain("choose");
  });

  it("rejects a comparison attribute outside the whitelist", () => {
    const raw = loadFixtureCopy("comparison-two");
    (raw.root as Record<string, unknown>).props = {
      productIds: ["aurora-hush-pro", "cloudline-air"],
      attributes: ["price_usd", "wifi_7"],
    };
    const errors = expectRejected(parseUiPlan(raw, CATALOG_IDS));
    expect(errors.join("\n")).toContain("wifi_7");
  });
});

describe("validateProductRefs", () => {
  it("returns no violations for a clean fixture plan", () => {
    const result = expectOk(parseUiPlan(loadFixture("cart-one-item")));
    expect(validateProductRefs(result.plan, CATALOG_IDS)).toEqual([]);
  });

  it("flags a foreign payload productId on an add_to_cart action", () => {
    const raw = loadFixtureCopy("product-grid-flights");
    const root = raw.root as Record<string, unknown>;
    root.actions = [
      { type: "add_to_cart", label: "Add to cart", payload: { productId: "off-catalog-thing" } },
    ];
    const { plan } = expectOk(parseUiPlan(raw));
    const violations = validateProductRefs(plan, CATALOG_IDS);
    expect(violations.length).toBeGreaterThan(0);
    expect(violations.join("\n")).toContain("off-catalog-thing");
  });

  it("flags a foreign choose payload and a foreign details productId", () => {
    const comparison = loadFixtureCopy("comparison-two");
    (comparison.root as Record<string, unknown>).actions = [
      { type: "choose", label: "Choose it", payload: { productId: "not-a-product" } },
    ];
    const { plan: comparisonPlan } = expectOk(parseUiPlan(comparison));
    expect(validateProductRefs(comparisonPlan, CATALOG_IDS).join("\n")).toContain(
      "not-a-product",
    );

    const details = loadFixtureCopy("product-details");
    (details.root as Record<string, unknown>).props = {
      productId: "not-a-product",
      showQuotes: false,
    };
    const { plan: detailsPlan } = expectOk(parseUiPlan(details));
    expect(validateProductRefs(detailsPlan, CATALOG_IDS).join("\n")).toContain(
      "not-a-product",
    );
  });

  it("flags a foreign remove_from_cart payload and more than one choose action", () => {
    const cart = loadFixtureCopy("cart-one-item");
    (cart.root as Record<string, unknown>).actions = [
      { type: "remove_from_cart", label: "Remove", payload: { productId: "not-a-product" } },
    ];
    const { plan: cartPlan } = expectOk(parseUiPlan(cart));
    expect(validateProductRefs(cartPlan, CATALOG_IDS).join("\n")).toContain(
      "not-a-product",
    );

    const comparison = loadFixtureCopy("comparison-two");
    (comparison.root as Record<string, unknown>).actions = [
      { type: "choose", label: "Choose A", payload: { productId: "aurora-hush-pro" } },
      { type: "choose", label: "Choose B", payload: { productId: "cloudline-air" } },
    ];
    const { plan: comparisonPlan } = expectOk(parseUiPlan(comparison));
    const violations = validateProductRefs(comparisonPlan, CATALOG_IDS);
    expect(violations.join("\n")).toContain("2 choose actions");
  });

  it("flags every picker option that lacks a matching action", () => {
    const picker = loadFixtureCopy("preference-picker-category");
    (picker.root as Record<string, unknown>).actions = [];
    const { plan } = expectOk(parseUiPlan(picker));
    const violations = validateProductRefs(plan, CATALOG_IDS);
    expect(violations).toHaveLength(2);
    expect(violations.join("\n")).toContain("Headphones");
    expect(violations.join("\n")).toContain("Something else");
  });
});

describe("catalog mirror", () => {
  it("holds exactly 28 ids", () => {
    expect(CATALOG_IDS.size).toBe(28);
  });

  it("contains the four canonical ids", () => {
    for (const id of ["aurora-hush-pro", "cloudline-air", "skyline-hush", "volt-enduro-70"]) {
      expect(CATALOG_IDS.has(id)).toBe(true);
    }
  });
});

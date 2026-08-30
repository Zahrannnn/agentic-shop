import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CatalogError, fetchCatalog } from "../api/catalog-client";
import { CatalogSheet } from "./catalog-sheet";

/**
 * The wire shape pinned by the backend contract (branch 002): camelCase, no
 * quotes field, `count === products.length`, price-ascending. Tests mock
 * `fetch` with 3 samples and assert the sheet renders exactly what the wire
 * ordered — the sheet never re-sorts.
 */

const BASE_URL = "http://127.0.0.1:8000";

function makeProduct(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: "aurora-hush-pro",
    name: "Aurora Hush Pro",
    brand: "Aurora",
    category: "headphones",
    priceUsd: 179.0,
    batteryHours: 45.0,
    weightG: 250.0,
    ancType: "adaptive",
    reviewScores: { comfort: 4.7, anc: 4.9, sound: 4.4, battery: 4.6, value: 4.2 },
    multipoint: true,
    folding: false,
    codecs: ["aptx"],
    ...overrides,
  };
}

const PRODUCTS = [
  makeProduct(),
  makeProduct({
    id: "pebble-air-lite",
    name: "Pebble Air Lite",
    brand: "Pebble",
    category: "earbuds",
    priceUsd: 89.99,
    batteryHours: 8,
    weightG: 48,
    ancType: "none",
    multipoint: false,
    codecs: ["aac", "sbc"],
  }),
  makeProduct({
    id: "nimbus-studio-90",
    name: "Nimbus Studio 90",
    brand: "Nimbus",
    category: "headphones",
    priceUsd: 249.5,
    batteryHours: 60,
    weightG: 320,
    ancType: "adaptive",
    folding: true,
    codecs: ["ldac", "aptx"],
  }),
];

const fetchMock = vi.fn<(...args: unknown[]) => Promise<Response>>();

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderSheet(
  props: Partial<Parameters<typeof CatalogSheet>[0]> = {},
): ReturnType<typeof render> {
  return render(
    <CatalogSheet
      open
      onOpenChange={vi.fn()}
      baseUrl={BASE_URL}
      {...props}
    />,
  );
}

describe("CatalogSheet rendering states", () => {
  it("shows six skeleton rows while the fetch is in flight", () => {
    fetchMock.mockReturnValueOnce(new Promise<Response>(() => undefined));
    renderSheet();

    const loading = screen.getByTestId("catalog-loading");
    expect(loading.querySelectorAll(".animate-pulse")).toHaveLength(6);
    expect(screen.queryByTestId("catalog-list")).not.toBeInTheDocument();
    expect(screen.queryByTestId("catalog-count")).not.toBeInTheDocument();
  });

  it("fetches on open and renders the count, rows in wire order, and tabular prices", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ count: 3, products: PRODUCTS }));
    renderSheet();

    expect(await screen.findByTestId("catalog-count")).toHaveTextContent(
      "3 products",
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE_URL}/api/catalog`);
    expect(init).toMatchObject({ cache: "no-store" });
    expect((init as RequestInit).signal).toBeInstanceOf(AbortSignal);

    const rows = screen.getAllByTestId("catalog-row");
    expect(rows).toHaveLength(3);
    expect(rows.map((row) => row.getAttribute("data-product-id"))).toEqual([
      "aurora-hush-pro",
      "pebble-air-lite",
      "nimbus-studio-90",
    ]);

    const first = within(rows[0]);
    expect(first.getByText("Aurora Hush Pro")).toBeInTheDocument();
    expect(first.getByText("Aurora · headphones")).toBeInTheDocument();
    const price = first.getByTestId("catalog-price");
    expect(price).toHaveTextContent("$179.00");
    expect(price).toHaveClass("font-mono", "tabular-nums");
    expect(within(rows[1]).getByTestId("catalog-price")).toHaveTextContent(
      "$89.99",
    );
    expect(within(rows[2]).getByTestId("catalog-price")).toHaveTextContent(
      "$249.50",
    );
  });

  it("renders the compact ANC badge only when ancType is not none", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ count: 3, products: PRODUCTS }));
    renderSheet();

    const rows = await screen.findAllByTestId("catalog-row");
    expect(within(rows[0]).getByTestId("anc-badge")).toHaveTextContent("ANC");
    expect(within(rows[1]).queryByTestId("anc-badge")).not.toBeInTheDocument();
    expect(within(rows[2]).getByTestId("anc-badge")).toHaveTextContent("ANC");
  });

  it("renders a quiet empty line for a count of 0", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ count: 0, products: [] }));
    renderSheet();

    expect(await screen.findByTestId("catalog-empty")).toHaveTextContent(
      "The catalog is empty.",
    );
    expect(screen.queryByTestId("catalog-list")).not.toBeInTheDocument();
    expect(screen.getByTestId("catalog-count")).toHaveTextContent("0 products");
  });

  it("shows a Pencil-tone notice with Retry on failure and refetches on Retry", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "boom" }, 500));
    renderSheet();

    const notice = await screen.findByTestId("catalog-error");
    expect(notice).toHaveTextContent("Catalog request failed (HTTP 500).");
    expect(notice).toHaveClass("bg-secondary", "text-muted-foreground");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fetchMock.mockResolvedValueOnce(
      jsonResponse({ count: 1, products: [PRODUCTS[0]] }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByTestId("catalog-count")).toHaveTextContent(
      "1 product",
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("surfaces a contract-violating payload as the error notice", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ count: 3, products: [makeProduct({ priceUsd: "179" })] }),
    );
    renderSheet();

    const notice = await screen.findByTestId("catalog-error");
    expect(notice).toHaveTextContent(
      "Catalog response did not match the contract",
    );
    expect(notice).toHaveTextContent("priceUsd");
    expect(screen.queryByTestId("catalog-list")).not.toBeInTheDocument();
  });
});

describe("CatalogSheet interaction", () => {
  it("Ask about this hands the product to onAskAbout and closes the sheet", async () => {
    const onAskAbout = vi.fn();
    const onOpenChange = vi.fn();
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ count: 3, products: PRODUCTS }),
    );
    renderSheet({ onAskAbout, onOpenChange });

    const rows = await screen.findAllByTestId("catalog-row");
    fireEvent.click(
      within(rows[0]).getByRole("button", {
        name: "Ask about Aurora Hush Pro",
      }),
    );

    expect(onAskAbout).toHaveBeenCalledTimes(1);
    expect(onAskAbout).toHaveBeenCalledWith(PRODUCTS[0]);
    expect(onOpenChange).toHaveBeenCalledTimes(1);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("is props-driven: closed renders nothing and never fetches, opening fetches", async () => {
    const onOpenChange = vi.fn();
    fetchMock.mockResolvedValue(jsonResponse({ count: 3, products: PRODUCTS }));

    const view = renderSheet({ open: false, onOpenChange });
    expect(screen.queryByTestId("catalog-sheet")).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();

    view.rerender(
      <CatalogSheet
        open
        onOpenChange={onOpenChange}
        baseUrl={BASE_URL}
      />,
    );
    expect(await screen.findByTestId("catalog-count")).toHaveTextContent(
      "3 products",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);

    view.rerender(
      <CatalogSheet
        open={false}
        onOpenChange={onOpenChange}
        baseUrl={BASE_URL}
      />,
    );
    await waitFor(() => {
      expect(screen.queryByTestId("catalog-sheet")).not.toBeInTheDocument();
    });
  });
});

describe("fetchCatalog", () => {
  it("accepts the pinned wire shape", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ count: 1, products: [makeProduct()] }),
    );

    const data = await fetchCatalog(BASE_URL);

    expect(data.count).toBe(1);
    expect(data.products[0].id).toBe("aurora-hush-pro");
    expect(data.products[0].priceUsd).toBe(179.0);
    expect(data.products[0].reviewScores.anc).toBe(4.9);
    expect(data.products[0].codecs).toEqual(["aptx"]);
    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/api/catalog`,
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("throws CatalogError with the status on a non-ok response", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "not found" }, 404),
    );

    const error = await fetchCatalog(BASE_URL).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(CatalogError);
    expect((error as CatalogError).message).toBe(
      "Catalog request failed (HTTP 404).",
    );
    expect((error as CatalogError).status).toBe(404);
  });

  it("throws CatalogError when the body is not valid JSON", async () => {
    fetchMock.mockResolvedValueOnce(new Response("<html>boom</html>"));

    const error = await fetchCatalog(BASE_URL).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(CatalogError);
    expect((error as CatalogError).message).toBe(
      "Catalog response was not valid JSON.",
    );
  });

  it("throws CatalogError when the payload violates the contract", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ count: 3.5, products: [] }),
    );

    const error = await fetchCatalog(BASE_URL).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(CatalogError);
    expect((error as CatalogError).message).toContain("count");
  });

  it("wraps a transport failure into CatalogError", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const error = await fetchCatalog(BASE_URL).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(CatalogError);
    expect((error as CatalogError).message).toBe(
      "Couldn't reach the catalog.",
    );
  });

  it("rethrows a caller-requested abort instead of wrapping it", async () => {
    const controller = new AbortController();
    controller.abort();
    fetchMock.mockRejectedValueOnce(
      new DOMException("The operation was aborted.", "AbortError"),
    );

    await expect(
      fetchCatalog(BASE_URL, controller.signal),
    ).rejects.toMatchObject({ name: "AbortError" });
  });
});

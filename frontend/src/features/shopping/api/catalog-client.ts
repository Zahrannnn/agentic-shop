import { z } from "zod";

/**
 * Transport + boundary validation for `GET /api/catalog` (wire contract
 * pinned on branch 002): `{ count, products[] }`, sorted by price ascending,
 * camelCase, no quotes field. React-free and store-free — the sheet composes
 * this with its own open/abort lifecycle.
 *
 * Every failure mode (transport, HTTP status, unparsable JSON, contract
 * violation) surfaces as one typed error, {@link CatalogError}, so the UI has
 * a single branch. Caller-requested aborts keep their AbortError identity so
 * an aborted request can be told apart from a real failure.
 */

export const catalogProductSchema = z.object({
  id: z.string().min(1),
  name: z.string(),
  brand: z.string(),
  category: z.string(),
  priceUsd: z.number(),
  batteryHours: z.number(),
  weightG: z.number(),
  ancType: z.string(),
  reviewScores: z.object({
    comfort: z.number(),
    anc: z.number(),
    sound: z.number(),
    battery: z.number(),
    value: z.number(),
  }),
  multipoint: z.boolean(),
  folding: z.boolean(),
  codecs: z.array(z.string()),
});

export const catalogResponseSchema = z.object({
  /** Total catalog size; the contract pins `count === products.length`. */
  count: z.number().int(),
  products: z.array(catalogProductSchema),
});

export type CatalogProduct = z.infer<typeof catalogProductSchema>;
export type CatalogResponse = z.infer<typeof catalogResponseSchema>;

/** Single failure type for the catalog endpoint (transport/HTTP/contract). */
export class CatalogError extends Error {
  /** HTTP status when the failure was a non-ok response; undefined otherwise. */
  readonly status?: number;

  constructor(message: string, options?: { status?: number }) {
    super(message);
    this.name = "CatalogError";
    this.status = options?.status;
  }
}

function describeSchemaError(error: z.ZodError): string {
  const issue = error.issues.at(0);
  if (!issue) {
    return "unknown mismatch";
  }
  const path = issue.path.join(".");
  return `${path.length > 0 ? path : "payload"}: ${issue.message}`;
}

/**
 * Fetches and validates the full catalog. Resolves with the parsed
 * {@link CatalogResponse}; rejects with {@link CatalogError} on any failure
 * except a caller-requested abort, which rethrows the original AbortError.
 */
export async function fetchCatalog(
  baseUrl: string,
  signal?: AbortSignal,
): Promise<CatalogResponse> {
  let response: Response;
  try {
    response = await fetch(`${baseUrl}/api/catalog`, {
      cache: "no-store",
      signal,
    });
  } catch (error) {
    if (signal?.aborted) {
      throw error;
    }
    throw new CatalogError("Couldn't reach the catalog.");
  }

  if (!response.ok) {
    throw new CatalogError(`Catalog request failed (HTTP ${response.status}).`, {
      status: response.status,
    });
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch (error) {
    if (signal?.aborted) {
      throw error;
    }
    throw new CatalogError("Catalog response was not valid JSON.");
  }

  const parsed = catalogResponseSchema.safeParse(payload);
  if (!parsed.success) {
    throw new CatalogError(
      `Catalog response did not match the contract (${describeSchemaError(parsed.error)}).`,
    );
  }

  return parsed.data;
}

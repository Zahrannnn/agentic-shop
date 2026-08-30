import { z } from "zod";

const publicEnvSchema = z.object({
  NEXT_PUBLIC_APP_NAME: z.string().default("agentic-shop"),
  NEXT_PUBLIC_APP_URL: z.string().url().default("http://localhost:3000"),
  NEXT_PUBLIC_SHOW_HEALTH_URLS: z
    .enum(["true", "false"])
    .default("false")
    .transform((value) => value === "true"),
  NEXT_PUBLIC_CORE_API_BASE_URL: z.string().url().optional().or(z.literal("")),
  NEXT_PUBLIC_BILLING_API_BASE_URL: z.string().url().optional().or(z.literal("")),
  NEXT_PUBLIC_REPORTING_API_BASE_URL: z.string().url().optional().or(z.literal("")),
  NEXT_PUBLIC_AGENT_API_BASE_URL: z.string().url().optional().or(z.literal("")),
});

type PublicEnvInput = {
  NEXT_PUBLIC_APP_NAME?: string;
  NEXT_PUBLIC_APP_URL?: string;
  NEXT_PUBLIC_SHOW_HEALTH_URLS?: string;
  NEXT_PUBLIC_CORE_API_BASE_URL?: string;
  NEXT_PUBLIC_BILLING_API_BASE_URL?: string;
  NEXT_PUBLIC_REPORTING_API_BASE_URL?: string;
  NEXT_PUBLIC_AGENT_API_BASE_URL?: string;
};

declare global {
  interface Window {
    __RUNTIME_CONFIG__?: PublicEnvInput;
  }
}

function readPublicEnv(): PublicEnvInput {
  const processEnv: PublicEnvInput = {
    NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME,
    NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
    NEXT_PUBLIC_SHOW_HEALTH_URLS: process.env.NEXT_PUBLIC_SHOW_HEALTH_URLS,
    NEXT_PUBLIC_CORE_API_BASE_URL: process.env.NEXT_PUBLIC_CORE_API_BASE_URL,
    NEXT_PUBLIC_BILLING_API_BASE_URL: process.env.NEXT_PUBLIC_BILLING_API_BASE_URL,
    NEXT_PUBLIC_REPORTING_API_BASE_URL: process.env.NEXT_PUBLIC_REPORTING_API_BASE_URL,
    NEXT_PUBLIC_AGENT_API_BASE_URL: process.env.NEXT_PUBLIC_AGENT_API_BASE_URL,
  };

  if (typeof window !== "undefined" && window.__RUNTIME_CONFIG__) {
    return { ...processEnv, ...window.__RUNTIME_CONFIG__ };
  }

  return processEnv;
}

const parsed = publicEnvSchema.safeParse(readPublicEnv());

if (!parsed.success) {
  console.error("[env] Invalid public env, falling back to defaults:", parsed.error.issues);
}

export const env = parsed.success ? parsed.data : publicEnvSchema.parse({});

export const backendServices = [
  {
    key: "core",
    label: "Core API",
    baseUrl: env.NEXT_PUBLIC_CORE_API_BASE_URL,
  },
  {
    key: "billing",
    label: "Billing API",
    baseUrl: env.NEXT_PUBLIC_BILLING_API_BASE_URL,
  },
  {
    key: "reporting",
    label: "Reporting API",
    baseUrl: env.NEXT_PUBLIC_REPORTING_API_BASE_URL,
  },
] as const;

const AGENT_API_DEFAULT_BASE_URL = "http://127.0.0.1:8000";

/** Agent backend base URL; unset or empty resolves to the local dev backend. */
export const agentApiBaseUrl: string =
  env.NEXT_PUBLIC_AGENT_API_BASE_URL &&
  env.NEXT_PUBLIC_AGENT_API_BASE_URL.length > 0
    ? env.NEXT_PUBLIC_AGENT_API_BASE_URL
    : AGENT_API_DEFAULT_BASE_URL;

import axios, { AxiosError, type AxiosInstance } from "axios";

export type ApiServiceKey = "core" | "billing" | "reporting";

export type ApiError = {
  message: string;
  status?: number;
  code?: string;
};

const clients = new Map<ApiServiceKey, AxiosInstance>();

export function createHttpClient(baseURL?: string) {
  const client = axios.create({
    baseURL,
    timeout: 8000,
    headers: {
      Accept: "application/json",
    },
  });

  client.interceptors.response.use(
    (response) => response,
    (error: AxiosError<{ message?: string; code?: string }>) => {
      return Promise.reject(normalizeApiError(error));
    }
  );

  return client;
}

export function getHttpClient(key: ApiServiceKey, baseURL?: string) {
  if (!clients.has(key)) {
    clients.set(key, createHttpClient(baseURL));
  }

  return clients.get(key)!;
}

export function normalizeApiError(error: unknown): ApiError {
  if (axios.isAxiosError<{ message?: string; code?: string }>(error)) {
    return {
      message:
        error.response?.data?.message ??
        error.message ??
        "The request could not be completed.",
      status: error.response?.status,
      code: error.response?.data?.code,
    };
  }

  if (error instanceof Error) {
    return { message: error.message };
  }

  return { message: "An unknown API error occurred." };
}

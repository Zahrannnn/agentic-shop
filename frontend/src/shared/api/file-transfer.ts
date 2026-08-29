import type { AxiosInstance, AxiosProgressEvent } from "axios";

export type UploadProgress = {
  loaded: number;
  total?: number;
  percent?: number;
};

export async function downloadBlob(
  client: AxiosInstance,
  url: string,
  fallbackFileName = "download"
) {
  const response = await client.get<Blob>(url, { responseType: "blob" });
  const disposition = response.headers["content-disposition"];
  const fileName = getFileNameFromDisposition(disposition) ?? fallbackFileName;

  return {
    blob: response.data,
    fileName,
  };
}

export async function uploadFile(
  client: AxiosInstance,
  url: string,
  file: File | Blob,
  fieldName = "file",
  onProgress?: (progress: UploadProgress) => void
) {
  const form = new FormData();
  form.append(fieldName, file);

  const response = await client.post<{ location?: string; id?: string }>(url, form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (event: AxiosProgressEvent) => {
      if (!onProgress) {
        return;
      }

      onProgress({
        loaded: event.loaded,
        total: event.total,
        percent: event.total ? Math.round((event.loaded / event.total) * 100) : undefined,
      });
    },
  });

  return response.data;
}

export function getFileNameFromDisposition(disposition?: string) {
  if (!disposition) {
    return undefined;
  }

  const utf8Match = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }

  const match = /filename="?([^";]+)"?/i.exec(disposition);
  return match?.[1];
}

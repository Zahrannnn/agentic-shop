import type { ProfileFormValues } from "../types";

export async function saveProfile(values: ProfileFormValues) {
  await new Promise((resolve) => setTimeout(resolve, 450));
  return values;
}

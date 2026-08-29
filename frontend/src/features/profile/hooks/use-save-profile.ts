"use client";

import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { saveProfile } from "../api/profile-adapter";
import type { ProfileFormValues } from "../types";

export function useSaveProfile() {
  return useMutation({
    mutationFn: (values: ProfileFormValues) => saveProfile(values),
    onSuccess: () => {
      toast.success("Profile saved");
    },
    onError: () => {
      toast.error("Profile could not be saved");
    },
  });
}

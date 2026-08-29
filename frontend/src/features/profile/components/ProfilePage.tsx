"use client";

import { useForm } from "@tanstack/react-form";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { PageHeader } from "@/shared/components/layout/page-header";
import { defaultProfile } from "../constants/default-profile";
import { useSaveProfile } from "../hooks/use-save-profile";
import type { ProfileFormValues } from "../types";
import { profileSchema } from "../validations/profile-schema";

export function ProfilePage() {
  const saveProfile = useSaveProfile();
  const { setTheme } = useTheme();
  const form = useForm({
    defaultValues: defaultProfile,
    onSubmit: async ({ value }) => {
      const parsed = profileSchema.safeParse(value);

      if (!parsed.success) {
        return;
      }

      setTheme(parsed.data.theme);
      await saveProfile.mutateAsync(parsed.data);
    },
  });

  return (
    <>
      <PageHeader
        title="Profile"
        description="TanStack Form with Zod validation and a mutation boundary ready to replace with a REST call."
      />
      <Card>
        <CardHeader>
          <CardTitle>Profile settings</CardTitle>
          <CardDescription>
            This is local demo behavior using the same structure as a real API-backed form.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-5 lg:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault();
              event.stopPropagation();
              void form.handleSubmit();
            }}
          >
            <form.Field name="name">
              {(field) => (
                <div className="space-y-2">
                  <Label htmlFor={field.name}>Name</Label>
                  <Input
                    id={field.name}
                    value={field.state.value}
                    onBlur={field.handleBlur}
                    onChange={(event) => field.handleChange(event.target.value)}
                  />
                </div>
              )}
            </form.Field>
            <form.Field name="email">
              {(field) => (
                <div className="space-y-2">
                  <Label htmlFor={field.name}>Email</Label>
                  <Input
                    id={field.name}
                    type="email"
                    value={field.state.value}
                    onBlur={field.handleBlur}
                    onChange={(event) => field.handleChange(event.target.value)}
                  />
                </div>
              )}
            </form.Field>
            <form.Field name="role">
              {(field) => (
                <div className="space-y-2">
                  <Label htmlFor={field.name}>Role</Label>
                  <Input
                    id={field.name}
                    value={field.state.value}
                    onBlur={field.handleBlur}
                    onChange={(event) => field.handleChange(event.target.value)}
                  />
                </div>
              )}
            </form.Field>
            <form.Field name="theme">
              {(field) => (
                <div className="space-y-2">
                  <Label>Theme preference</Label>
                  <Select
                    value={field.state.value}
                    onValueChange={(value) =>
                      field.handleChange(value as ProfileFormValues["theme"])
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Choose theme" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="system">System</SelectItem>
                      <SelectItem value="light">Light</SelectItem>
                      <SelectItem value="dark">Dark</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
            </form.Field>
            <form.Field name="bio">
              {(field) => (
                <div className="space-y-2 lg:col-span-2">
                  <Label htmlFor={field.name}>Bio</Label>
                  <Textarea
                    id={field.name}
                    value={field.state.value}
                    onBlur={field.handleBlur}
                    onChange={(event) => field.handleChange(event.target.value)}
                  />
                </div>
              )}
            </form.Field>
            <div className="lg:col-span-2">
              <Button type="submit" disabled={saveProfile.isPending}>
                {saveProfile.isPending ? "Saving..." : "Save profile"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </>
  );
}

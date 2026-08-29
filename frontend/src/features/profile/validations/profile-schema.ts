import { z } from "zod";

export const profileSchema = z.object({
  name: z.string().min(2, "Name must contain at least 2 characters."),
  email: z.string().email("Enter a valid email."),
  role: z.string().min(2, "Role is required."),
  bio: z.string().max(240, "Bio must be 240 characters or less."),
  theme: z.enum(["system", "light", "dark"]),
});

import type { Metadata } from "next";
import { ProfilePage } from "@/features/profile";

export const metadata: Metadata = {
  title: "Profile",
};

export default function Page() {
  return <ProfilePage />;
}

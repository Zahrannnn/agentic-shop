import type { Metadata } from "next";
import { LoginPage } from "@/features/auth";

export const metadata: Metadata = {
  title: "Login",
  description: "Mock provider-agnostic login boundary.",
};

export default function Page() {
  return <LoginPage />;
}

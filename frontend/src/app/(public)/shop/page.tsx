import type { Metadata } from "next";
import { ShopPage } from "@/features/shopping";

export const metadata: Metadata = {
  title: "Shop",
  description:
    "A conversation with the shopping agent — one recommendation, reasons included.",
};

export default function Page() {
  return <ShopPage />;
}

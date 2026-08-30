import Link from "next/link";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/shared/components/feedback/empty-state";
import { routes } from "@/shared/constants/routes";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <EmptyState
        title="Page not found"
        description="The route does not exist in this boilerplate."
        action={
          <Button asChild>
            <Link href={routes.shop}>Back to the shop</Link>
          </Button>
        }
      />
    </main>
  );
}

import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-4 p-6">
      <Skeleton className="h-10 w-56" />
      <Skeleton className="h-64 w-full" />
    </main>
  );
}

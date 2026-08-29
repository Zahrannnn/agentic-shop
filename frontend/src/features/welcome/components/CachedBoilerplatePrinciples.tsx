export async function CachedBoilerplatePrinciples() {
  "use cache";

  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="text-sm font-semibold">Cached static shell</h3>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        This section is rendered through a cached Server Component. It is the
        stable part of the welcome page and demonstrates the Cache Components
        baseline used by this boilerplate.
      </p>
    </div>
  );
}

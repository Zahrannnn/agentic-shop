export async function DynamicBuildSignal() {
  await new Promise((resolve) => setTimeout(resolve, 600));

  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="text-sm font-semibold">Streamed dynamic section</h3>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        This section resolves after the static shell. Use this pattern for
        public pages where static content should appear before slower dynamic
        work finishes.
      </p>
    </div>
  );
}

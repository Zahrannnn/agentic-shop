import { CheckCircle2 } from "lucide-react";
import type { GuideItem } from "../types";

export function GuideList({ items }: { items: GuideItem[] }) {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {items.map((item) => (
        <div key={item.title} className="rounded-lg border bg-card p-4">
          <div className="mb-3 flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            <h3 className="text-sm font-semibold">{item.title}</h3>
          </div>
          <p className="text-sm leading-6 text-muted-foreground">
            {item.description}
          </p>
        </div>
      ))}
    </div>
  );
}

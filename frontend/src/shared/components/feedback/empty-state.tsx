import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";

type EmptyStateProps = {
  title: string;
  description: string;
  action?: ReactNode;
};

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <Card className="w-full max-w-md">
      <CardContent className="space-y-4 p-6 text-center">
        <div className="space-y-2">
          <h1 className="text-xl font-semibold">{title}</h1>
          <p className="text-sm leading-6 text-muted-foreground">{description}</p>
        </div>
        {action}
      </CardContent>
    </Card>
  );
}

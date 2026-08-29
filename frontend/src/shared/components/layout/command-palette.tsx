"use client";

import { Activity, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { routes } from "@/shared/constants/routes";
import { useRateLimitedSearch } from "@/shared/hooks/use-rate-limited-search";

const commands = [
  { label: "Welcome", href: routes.welcome },
  { label: "Dashboard", href: routes.dashboard },
  { label: "Profile", href: routes.profile },
  { label: "Health", href: routes.health },
];

type CommandPaletteProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const debouncedSearch = useRateLimitedSearch(setQuery);
  const filteredCommands = useMemo(
    () =>
      commands.filter((command) =>
        command.label.toLowerCase().includes(query.toLowerCase())
      ),
    [query]
  );

  return (
    <Activity mode={open ? "visible" : "hidden"} name="CommandPalette">
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="p-0">
          <DialogTitle className="sr-only">Command palette</DialogTitle>
          <div className="flex items-center gap-2 border-b px-4 py-3">
            <Search className="h-4 w-4 text-muted-foreground" />
            <Input
              autoFocus
              className="border-0 px-0 focus-visible:outline-0"
              placeholder="Jump to a route..."
              onChange={(event) => debouncedSearch(event.target.value)}
            />
          </div>
          <div className="p-2">
            {filteredCommands.map((command) => (
              <button
                key={command.href}
                type="button"
                className="flex w-full items-center rounded-md px-3 py-2 text-left text-sm hover:bg-muted focus-visible:outline-2"
                onClick={() => {
                  onOpenChange(false);
                  router.push(command.href);
                }}
              >
                {command.label}
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </Activity>
  );
}

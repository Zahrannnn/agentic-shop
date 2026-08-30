"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Menu, Search, UserRound, HeartPulse } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";
import { CommandPalette } from "@/shared/components/layout/command-palette";
import { ThemeToggle } from "@/shared/components/layout/theme-toggle";
import { routes } from "@/shared/constants/routes";
import { cn } from "@/shared/utils/cn";
import { useAuth } from "@/features/auth";

const navItems = [
  { label: "Shop", href: routes.shop, icon: LayoutDashboard },
  { label: "Health", href: routes.health, icon: HeartPulse },
];

function Sidebar() {
  const pathname = usePathname();

  return (
    <nav className="flex h-full flex-col gap-2">
      <Link href={routes.shop} className="mb-4 px-2 text-sm font-semibold">
        agentic-shop
      </Link>
      {navItems.map((item) => {
        const Icon = item.icon;
        const active = pathname === item.href;

        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground",
              active && "bg-muted text-foreground"
            )}
          >
            <Icon className="h-4 w-4" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [commandOpen, setCommandOpen] = useState(false);
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r bg-card p-4 lg:block">
        <Sidebar />
      </aside>
      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur">
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open menu">
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent>
              <Sidebar />
            </SheetContent>
          </Sheet>
          <Button
            type="button"
            variant="outline"
            className="h-9 w-full justify-start text-muted-foreground sm:max-w-xs"
            onClick={() => setCommandOpen(true)}
          >
            <Search className="h-4 w-4" />
            Command
          </Button>
          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />
            <Separator orientation="vertical" className="h-6" />
            <div className="hidden text-right text-xs sm:block">
              <p className="font-medium">{user?.name}</p>
              <p className="text-muted-foreground">{user?.email}</p>
            </div>
            <Button type="button" variant="ghost" size="sm" onClick={logout}>
              Logout
            </Button>
          </div>
        </header>
        <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-4 md:p-6">
          {children}
        </main>
      </div>
      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />
    </div>
  );
}

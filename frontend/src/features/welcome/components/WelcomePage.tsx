import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  Bot,
  CheckCircle2,
  Container,
  FileText,
  ShieldCheck,
  Sparkles,
  Terminal,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { routes } from "@/shared/constants/routes";
import {
  agentReadyUpdates,
  architectureRules,
  quickStart,
} from "../constants/guides";
import type { WelcomePageProps } from "../types";
import { GuideList } from "./GuideList";

const commandRows = [
  { command: "npm run dev", label: "local app" },
  { command: "npm run test:run", label: "unit checks" },
  { command: "npm run verify", label: "handoff" },
  { command: "npm run corelia -- feature <name>", label: "feature scaffold" },
];

export function WelcomePage({ cachedDemo, dynamicDemo }: WelcomePageProps) {
  return (
    <main className="min-h-screen bg-background">
      <section className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-10 md:px-6">
        <div className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="space-y-5">
            <div className="inline-flex items-center gap-2 rounded-md border bg-card px-3 py-1 text-sm text-muted-foreground">
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              Agent-ready CORELIA frontend standard
            </div>
            <div className="space-y-3">
              <h1 className="max-w-3xl text-4xl font-semibold tracking-normal text-balance md:text-5xl">
                A Next.js boilerplate that tells teams and agents where to work.
              </h1>
              <p className="max-w-2xl text-base leading-7 text-muted-foreground text-pretty">
                Feature-first architecture, local Next 16 docs, explicit handoff
                checks, and copyable starter routes keep the boilerplate useful
                without becoming a framework inside the framework.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Button asChild>
                <Link href={routes.login}>
                  Open demo app <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild variant="outline">
                <Link href={routes.health}>Check health</Link>
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">npm run verify</Badge>
              <Badge variant="success">docs/agent-playbook.md</Badge>
              <Badge variant="secondary">feature barrels</Badge>
            </div>
          </div>
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Terminal className="h-5 w-5 text-primary" />
                <CardTitle>Quick commands</CardTitle>
              </div>
              <CardDescription>
                Small script surface, clear handoff path.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="space-y-3 text-sm">
                {commandRows.map((item) => (
                  <div
                    key={item.command}
                    className="flex items-center justify-between gap-4"
                  >
                    <dt className="font-mono text-xs">{item.command}</dt>
                    <dd className="text-muted-foreground">{item.label}</dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>
        </div>

        <Separator />

        <section className="rounded-lg border bg-card p-5 md:p-6">
          <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
            <div className="max-w-2xl space-y-2">
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                <h2 className="text-xl font-semibold">New agent-ready updates</h2>
              </div>
              <p className="text-sm leading-6 text-muted-foreground">
                The boilerplate now exposes its safest workflow directly: a
                single verification command, a short task playbook, and starter
                imports that model the feature boundary agents should follow.
              </p>
            </div>
            <div className="inline-flex w-full items-center justify-center gap-2 rounded-md border bg-background px-4 py-2 text-sm font-medium sm:w-auto">
              <FileText className="h-4 w-4" />
              docs/agent-playbook.md
            </div>
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            {agentReadyUpdates.map((item) => (
              <div key={item.title} className="rounded-md bg-muted p-4">
                <div className="mb-2 flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  <h3 className="text-sm font-semibold">{item.title}</h3>
                </div>
                <p className="text-sm leading-6 text-muted-foreground">
                  {item.description}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-primary" />
            <h2 className="text-xl font-semibold">Start here</h2>
          </div>
          <GuideList items={quickStart} />
        </section>

        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-primary" />
            <h2 className="text-xl font-semibold">Architecture rules</h2>
          </div>
          <GuideList items={architectureRules} />
        </section>

        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <Container className="h-5 w-5 text-primary" />
            <h2 className="text-xl font-semibold">Cache Components demo</h2>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {cachedDemo}
            {dynamicDemo}
          </div>
        </section>
      </section>
    </main>
  );
}

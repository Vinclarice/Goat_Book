import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";

import { ThemeToggle } from "../ThemeToggle";

const BUTTON_VARIANTS = ["default", "outline", "secondary", "ghost", "destructive", "link"] as const;
const BUTTON_SIZES = ["sm", "default", "lg"] as const;

export function DevUiGallery() {
  const [digestEnabled, setDigestEnabled] = useState(true);

  return (
    <div className="max-w-4xl mx-auto px-4 py-10 space-y-10">
      <header className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-accent">Dev only</p>
          <h1 className="text-2xl font-bold">Component gallery</h1>
          <p className="text-muted-foreground text-sm">
            Visual QA for shadcn components against Clarice's tokens. Not shipped in production.
          </p>
        </div>
        <ThemeToggle />
      </header>

      <section className="space-y-3">
        <h2 className="font-bold">Button</h2>
        <div className="flex flex-col gap-3">
          {BUTTON_SIZES.map((size) => (
            <div key={size} className="flex flex-wrap items-center gap-2">
              {BUTTON_VARIANTS.map((variant) => (
                <Button key={variant} variant={variant} size={size}>
                  {variant}
                </Button>
              ))}
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="font-bold">Switch</h2>
        <div className="flex items-center gap-3">
          <Switch
            id="dev-digest-switch"
            checked={digestEnabled}
            onCheckedChange={setDigestEnabled}
          />
          <label htmlFor="dev-digest-switch" className="text-sm">
            Email me a daily summary ({digestEnabled ? "on" : "off"})
          </label>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="font-bold">Card</h2>
        <Card className="max-w-sm">
          <CardHeader>
            <CardTitle>Renew passport</CardTitle>
            <CardDescription>Errands · 3 days overdue</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Tagged travel. Due before the trip on the 14th.
          </CardContent>
          <CardFooter className="gap-2">
            <Button size="sm">Mark done</Button>
            <Button size="sm" variant="outline">
              Snooze
            </Button>
          </CardFooter>
        </Card>
      </section>
    </div>
  );
}

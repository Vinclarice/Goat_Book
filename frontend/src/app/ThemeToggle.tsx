import { useState } from "react";

import { Button } from "@/components/ui/button";

import { applyTheme, currentThemeChoice, type ThemeChoice } from "./theme";

interface Props {
  onChange?: (choice: ThemeChoice) => void;
  // Defaults to whatever's in localStorage (fine for the dev gallery,
  // which has no server-persisted preference to defer to). Preferences
  // passes the account's actual stored value instead, since it can
  // legitimately differ across devices/browsers.
  initialChoice?: ThemeChoice;
}

export function ThemeToggle({ onChange, initialChoice }: Props) {
  const [choice, setChoice] = useState<ThemeChoice>(initialChoice ?? currentThemeChoice());

  function choose(next: ThemeChoice) {
    applyTheme(next);
    setChoice(next);
    onChange?.(next);
  }

  return (
    <div className="inline-flex gap-1 rounded-lg border border-border bg-input p-1">
      {(["system", "light", "dark"] as const).map((option) => (
        <Button
          key={option}
          type="button"
          size="sm"
          variant={choice === option ? "default" : "ghost"}
          aria-pressed={choice === option}
          onClick={() => choose(option)}
        >
          {option[0].toUpperCase() + option.slice(1)}
        </Button>
      ))}
    </div>
  );
}

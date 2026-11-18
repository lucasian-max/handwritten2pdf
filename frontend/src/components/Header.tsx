import { Link, useLocation } from "react-router-dom";
import { Settings } from "lucide-react";
import { Button } from "@/components/ui/button";

export function Header() {
  const { pathname } = useLocation();

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="mx-auto flex h-14 max-w-4xl items-center justify-between px-4">
        <Link
          to="/"
          className="font-display text-lg tracking-tight text-ink outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:rounded-sm"
        >
          notes2latex
        </Link>
        <Button variant="ghost" size="sm" asChild>
          <Link
            to="/settings"
            aria-current={pathname === "/settings" ? "page" : undefined}
            className="text-muted-foreground aria-[current=page]:text-ink"
          >
            <Settings className="h-4 w-4" />
            <span className="hidden sm:inline">Settings</span>
            <span className="sr-only sm:hidden">Settings</span>
          </Link>
        </Button>
      </div>
    </header>
  );
}

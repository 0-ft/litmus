"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  FileText,
  ShieldAlert,
  Building2,
  RefreshCw,
  AlertTriangle,
  FlaskConical,
} from "lucide-react";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Papers", href: "/papers", icon: FileText },
  { name: "Assessments", href: "/assessments", icon: ShieldAlert },
  { name: "Flagged", href: "/flagged", icon: AlertTriangle },
  { name: "Facilities", href: "/facilities", icon: Building2 },
  { name: "Evaluation", href: "/evaluation", icon: FlaskConical },
  { name: "Scan", href: "/scan", icon: RefreshCw },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-64 border-r border-border bg-card">
      <div className="flex h-full flex-col">
        {/* Logo */}
        <div className="flex h-16 items-center border-b border-border px-6">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-primary/20 flex items-center justify-center">
              <ShieldAlert className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-foreground">Litmus</h1>
              <p className="text-xs text-muted-foreground">Biosecurity Scanner</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 px-3 py-4">
          {navigation.map((item) => {
            const isActive =
              pathname === item.href ||
              (item.href !== "/" && pathname.startsWith(item.href));

            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                <item.icon className="h-5 w-5" />
                {item.name}
                {item.name === "Flagged" && (
                  <span className="ml-auto flex h-5 w-5 items-center justify-center rounded-full bg-destructive/20 text-xs text-destructive">
                    !
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="border-t border-border p-4">
          <div className="rounded-lg bg-muted/50 p-3">
            <p className="text-xs text-muted-foreground">
              AI-powered screening of biology research for biosecurity risks.
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}


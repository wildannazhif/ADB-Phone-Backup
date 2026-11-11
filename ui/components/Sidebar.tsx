import {
  FolderSearch,
  HardDriveDownload,
  History,
  LayoutDashboard,
  Settings,
  Smartphone,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { BackendStateSnapshot, NavPage } from "@/types/backend";

interface SidebarProps {
  activePage: NavPage;
  onNavigate: (page: NavPage) => void;
  backendState: BackendStateSnapshot;
  isBackingUp: boolean;
  version: string;
}

const NAV_ITEMS: Array<{
  id: NavPage;
  label: string;
  icon: typeof LayoutDashboard;
}> = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "backup", label: "Backup", icon: HardDriveDownload },
  { id: "browser", label: "File Browser", icon: FolderSearch },
  { id: "history", label: "Backup History", icon: History },
  { id: "settings", label: "Settings", icon: Settings },
];

export function Sidebar({
  activePage,
  onNavigate,
  backendState,
  isBackingUp,
  version,
}: SidebarProps) {
  const isHealthy = backendState.state === "ready" && backendState.adb_available;
  const isCrashed = backendState.state === "crashed" || backendState.state === "stopped";

  return (
    <aside className="flex h-full w-56 shrink-0 flex-col border-r border-[var(--border-subtle)] bg-[var(--bg-sidebar)]">
      {/* Brand header */}
      <div className="flex items-center gap-2.5 border-b border-[var(--border-subtle)] px-4 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-sky-500/30 bg-sky-500/12 text-sky-500 dark:text-sky-400">
          <Smartphone className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="truncate text-xs font-semibold tracking-tight text-[var(--text-primary)]">
            ADB Phone Backup
          </div>
          <div className="text-[10px] font-medium text-[var(--text-muted)]">
            Smart Auto-Skip Engine
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-2.5">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = activePage === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate(item.id)}
              className={cn(
                "flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors duration-150 cursor-pointer",
                active
                  ? "bg-sky-500/12 text-sky-600 dark:text-sky-400 border border-sky-500/20"
                  : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] border border-transparent"
              )}
            >
              <span className="flex items-center gap-2.5">
                <Icon className="h-4 w-4 shrink-0" />
                <span>{item.label}</span>
              </span>
              {item.id === "backup" && isBackingUp && (
                <span className="h-2 w-2 rounded-full bg-sky-500 animate-pulse" />
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer status & version */}
      <div className="border-t border-[var(--border-subtle)] p-3 space-y-2">
        <div className="flex items-center justify-between rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] px-2.5 py-2">
          <div className="flex items-center gap-2 min-w-0">
            <span
              className={cn(
                "h-2 w-2 shrink-0 rounded-full",
                isCrashed
                  ? "bg-rose-500"
                  : isHealthy
                  ? "bg-emerald-500"
                  : "bg-amber-500"
              )}
            />
            <span className="truncate text-[11px] font-medium text-[var(--text-secondary)]">
              {isCrashed
                ? "Backend Offline"
                : !backendState.adb_available
                ? "ADB Missing"
                : "Engine Ready"}
            </span>
          </div>
          {backendState.pid && (
            <span className="font-mono text-[10px] text-[var(--text-muted)]">
              #{backendState.pid}
            </span>
          )}
        </div>

        <div className="flex items-center justify-between px-1 text-[10px] text-[var(--text-muted)]">
          <span>Windows Desktop</span>
          <span className="font-mono">v{version}</span>
        </div>
      </div>
    </aside>
  );
}

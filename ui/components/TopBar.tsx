import { Battery, HardDrive, RefreshCw, ShieldAlert, Smartphone } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { BackendStateSnapshot, DeviceInfo, NavPage } from "@/types/backend";

interface TopBarProps {
  activePage: NavPage;
  backendState: BackendStateSnapshot;
  selectedDevice: DeviceInfo | null;
  selectedSerial: string;
  onSelectSerial: (serial: string) => void;
  onRefreshDevices: () => void;
  isRefreshing: boolean;
}

const PAGE_TITLES: Record<NavPage, { title: string; subtitle: string }> = {
  dashboard: {
    title: "Dashboard",
    subtitle: "Device connection, backup overview, and recent activity",
  },
  backup: {
    title: "Backup",
    subtitle: "Configure Android source folders, Auto-Skip options, and live transfer",
  },
  browser: {
    title: "Android File Browser",
    subtitle: "Inspect directories on your device and select custom backup targets",
  },
  history: {
    title: "Backup History",
    subtitle: "Verified backup session logs stored locally on this PC",
  },
  settings: {
    title: "Settings",
    subtitle: "Appearance, ADB executable path, default folders, and log management",
  },
};

export function TopBar({
  activePage,
  backendState,
  selectedDevice,
  selectedSerial,
  onSelectSerial,
  onRefreshDevices,
  isRefreshing,
}: TopBarProps) {
  const meta = PAGE_TITLES[activePage];
  const devices = backendState.devices;

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-[var(--border-subtle)] bg-[var(--bg-card)]/60 px-6">
      <div className="min-w-0">
        <h1 className="text-sm font-semibold tracking-tight text-[var(--text-primary)]">
          {meta.title}
        </h1>
        <p className="truncate text-[11px] text-[var(--text-secondary)]">
          {meta.subtitle}
        </p>
      </div>

      {/* Right device status strip */}
      <div className="flex items-center gap-2.5">
        {!backendState.adb_available ? (
          <Badge variant="destructive" className="py-1">
            <ShieldAlert className="h-3 w-3" />
            <span>ADB Missing</span>
          </Badge>
        ) : devices.length === 0 ? (
          <Badge variant="secondary" className="py-1">
            <Smartphone className="h-3 w-3 text-[var(--text-muted)]" />
            <span>No USB Device</span>
          </Badge>
        ) : (
          <div className="flex items-center gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-2.5 py-1">
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                selectedDevice?.is_ready
                  ? "bg-emerald-500"
                  : selectedDevice?.status === "unauthorized"
                  ? "bg-amber-500"
                  : "bg-rose-500"
              )}
            />

            {devices.length > 1 ? (
              <select
                value={selectedSerial}
                onChange={(e) => onSelectSerial(e.target.value)}
                aria-label="Select connected Android device"
                className="bg-transparent text-xs font-medium text-[var(--text-primary)] outline-none cursor-pointer"
              >
                {devices.map((d) => (
                  <option key={d.serial} value={d.serial} className="bg-[var(--bg-card)]">
                    {d.display_name}
                  </option>
                ))}
              </select>
            ) : (
              <span className="max-w-52 truncate text-xs font-medium text-[var(--text-primary)]">
                {selectedDevice?.display_name}
              </span>
            )}

            {selectedDevice?.is_ready && (
              <div className="hidden items-center gap-2 border-l border-[var(--border-subtle)] pl-2 text-[11px] text-[var(--text-secondary)] md:flex">
                {selectedDevice.battery_level !== null && (
                  <span className="inline-flex items-center gap-1">
                    <Battery className="h-3 w-3 text-emerald-500" />
                    {selectedDevice.battery_level}%
                  </span>
                )}
                {selectedDevice.storage_free && (
                  <span className="inline-flex items-center gap-1">
                    <HardDrive className="h-3 w-3 text-sky-500" />
                    {selectedDevice.storage_free} free
                  </span>
                )}
              </div>
            )}
          </div>
        )}

        <Button
          variant="outline"
          size="sm"
          onClick={onRefreshDevices}
          disabled={isRefreshing || backendState.state !== "ready"}
          title="Refresh connected ADB devices"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", isRefreshing && "animate-spin")} />
          <span>Refresh</span>
        </Button>
      </div>
    </header>
  );
}

export const CITATION = "Section 43B(h) / Section 37(2)(g), Income Tax Act 2025";
export const CITATION_SHORT = "43B(h) / 37(2)(g)";

export type ClockStatus = "GREEN" | "AMBER" | "RED" | "PAID" | "EXCLUDED";
export type VendorStatus = "ELIGIBLE" | "EXCLUDED_TRADER" | "EXCLUDED_MEDIUM" | "PENDING_DECLARATION" | "NOT_REGISTERED";
export type UserRole = "treasury_staff" | "accountant" | "external_auditor" | "admin";

export function getClockStatusClass(status: ClockStatus): string {
  switch (status) {
    case "GREEN": return "clock-green";
    case "AMBER": return "clock-amber";
    case "RED": return "clock-red";
    case "PAID": return "clock-paid";
    default: return "clock-excluded";
  }
}

export function getClockStatusLabel(status: ClockStatus): string {
  switch (status) {
    case "GREEN": return "Safe";
    case "AMBER": return "Due Soon";
    case "RED": return "Overdue";
    case "PAID": return "Paid";
    default: return "Excluded";
  }
}

export function getVendorStatusLabel(status: VendorStatus): string {
  switch (status) {
    case "ELIGIBLE": return "Eligible MSE";
    case "EXCLUDED_TRADER": return "Excluded (Trader)";
    case "EXCLUDED_MEDIUM": return "Excluded (Medium)";
    case "PENDING_DECLARATION": return "Pending Declaration";
    default: return "Not Registered";
  }
}

export function formatINR(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatDate(date: string | null | undefined): string {
  if (!date) return "—";
  return new Date(date).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function getDaysLabel(days: number | null | undefined, status?: ClockStatus): string {
  if (status === "EXCLUDED" || status === "PAID") return "—";
  if (days === null || days === undefined) return "—";
  if (days > 0) return `${days}d left`;
  if (days === 0) return "Due today";
  return `${Math.abs(days)}d overdue`;
}

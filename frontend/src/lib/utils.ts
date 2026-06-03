export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
}

export function displayDate(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return value;
}

export async function resolveSearchParams<T>(params: T | Promise<T> | undefined): Promise<T | undefined> {
  return params instanceof Promise ? params : params;
}

export async function resolveRouteParams<T>(params: T | Promise<T>): Promise<T> {
  return params instanceof Promise ? params : params;
}

import { Search } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";

export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="flex min-w-0 flex-1 flex-col gap-2 text-sm font-medium text-foreground">
      {label}
      {children}
    </label>
  );
}

export function FilterBar({ children }: { children: ReactNode }) {
  return (
    <form className="flex flex-col gap-4 rounded-lg border border-border bg-background p-4 shadow-sm" method="get">
      <div className="grid gap-4 md:grid-cols-4">{children}</div>
      <div className="flex justify-end">
        <Button type="submit">
          <Search aria-hidden="true" data-icon="inline-start" />
          Search
        </Button>
      </div>
    </form>
  );
}

export function TextFilter({ label, name, value, placeholder }: { label: string; name: string; value?: string; placeholder?: string }) {
  return (
    <Field label={label}>
      <Input defaultValue={value || ""} name={name} placeholder={placeholder} />
    </Field>
  );
}

export function SelectFilter({
  label,
  name,
  value,
  options,
}: {
  label: string;
  name: string;
  value?: string;
  options: string[];
}) {
  return (
    <Field label={label}>
      <Select defaultValue={value || ""} name={name}>
        <option value="">Any</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </Select>
    </Field>
  );
}

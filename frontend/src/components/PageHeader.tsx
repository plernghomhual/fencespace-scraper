import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import type { DataSource } from "@/lib/types";

export function PageHeader({
  title,
  description,
  source,
  actions,
}: {
  title: string;
  description?: string;
  source?: DataSource;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 border-b border-border pb-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="flex max-w-3xl flex-col gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold tracking-normal text-foreground sm:text-4xl">{title}</h1>
          {source ? <Badge>{source === "mock" ? "Mock data" : "Live API"}</Badge> : null}
        </div>
        {description ? <p className="text-sm leading-6 text-muted-foreground">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}

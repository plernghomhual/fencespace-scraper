import { AlertCircle, Loader2 } from "lucide-react";

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-muted/35 px-6 py-10 text-center text-sm text-muted-foreground">
      {message}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-lg border border-destructive/35 bg-destructive/10 px-4 py-3 text-sm text-foreground"
    >
      <AlertCircle aria-hidden="true" data-icon="inline-start" />
      <span>{message}</span>
    </div>
  );
}

export function LoadingState({ message = "Loading FenceSpace data" }: { message?: string }) {
  return (
    <div className="flex min-h-48 items-center justify-center rounded-lg border border-border bg-muted/35 text-sm text-muted-foreground">
      <div className="flex items-center gap-2">
        <Loader2 aria-hidden="true" className="animate-spin" data-icon="inline-start" />
        <span>{message}</span>
      </div>
    </div>
  );
}

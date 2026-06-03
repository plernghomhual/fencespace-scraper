"use client";

import { ErrorState } from "@/components/StatePanels";
import { Button } from "@/components/ui/button";

export default function ErrorPage({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex flex-col gap-4">
      <ErrorState message={error.message || "The page failed to render."} />
      <div>
        <Button onClick={reset} type="button" variant="outline">
          Try again
        </Button>
      </div>
    </div>
  );
}

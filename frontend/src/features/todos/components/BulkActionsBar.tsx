import { Button } from "@/components/ui/button";
import { useBulkUpdateStatus } from "../api/todos";

interface BulkActionsBarProps {
  selectedIds: string[];
  onClear: () => void;
}

export function BulkActionsBar({ selectedIds, onClear }: BulkActionsBarProps) {
  const bulkUpdate = useBulkUpdateStatus();

  if (selectedIds.length === 0) return null;

  const applyStatus = (completed: boolean) => {
    bulkUpdate.mutate(
      { todoIds: selectedIds, completed },
      { onSuccess: onClear }
    );
  };

  return (
    <div className="flex items-center justify-between rounded-md border bg-muted/50 px-3 py-2 mb-3">
      <span className="text-sm text-muted-foreground">
        {selectedIds.length} selected
      </span>
      <div className="flex gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={bulkUpdate.isPending}
          onClick={() => applyStatus(true)}
        >
          Mark complete
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={bulkUpdate.isPending}
          onClick={() => applyStatus(false)}
        >
          Mark active
        </Button>
        <Button size="sm" variant="ghost" onClick={onClear}>
          Clear
        </Button>
      </div>
    </div>
  );
}

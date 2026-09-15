import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTags } from "@/features/tags/api/tags";
import type { TodoFilters } from "../api/todos";

interface FilterBarProps {
  filters: TodoFilters;
  onChange: (filters: TodoFilters) => void;
}

const selectClassName =
  "h-9 rounded-md border border-input bg-transparent px-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30";

export function FilterBar({ filters, onChange }: FilterBarProps) {
  const { data: tags } = useTags();
  const [keywordInput, setKeywordInput] = useState(filters.keyword ?? "");

  // Debounce the keyword filter so every keystroke doesn't trigger a new
  // request/query-key change.
  useEffect(() => {
    const timeout = setTimeout(() => {
      if (keywordInput !== (filters.keyword ?? "")) {
        onChange({ ...filters, keyword: keywordInput || undefined });
      }
    }, 300);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keywordInput]);

  const hasActiveFilters =
    filters.status || filters.tagId || filters.keyword || filters.dateFrom || filters.dateTo;

  const clearFilters = () => {
    setKeywordInput("");
    onChange({});
  };

  return (
    <div className="flex flex-wrap items-center gap-2 pb-4">
      <Input
        placeholder="Search todos..."
        value={keywordInput}
        onChange={(e) => setKeywordInput(e.target.value)}
        className="max-w-[200px]"
      />

      <select
        className={selectClassName}
        value={filters.status ?? ""}
        onChange={(e) =>
          onChange({ ...filters, status: (e.target.value || undefined) as TodoFilters["status"] })
        }
      >
        <option value="">All statuses</option>
        <option value="active">Active</option>
        <option value="completed">Completed</option>
      </select>

      <select
        className={selectClassName}
        value={filters.tagId ?? ""}
        onChange={(e) => onChange({ ...filters, tagId: e.target.value || undefined })}
      >
        <option value="">All tags</option>
        {tags?.map((tag) => (
          <option key={tag.id} value={tag.id}>
            {tag.name}
          </option>
        ))}
      </select>

      <Input
        type="date"
        value={filters.dateFrom ?? ""}
        onChange={(e) => onChange({ ...filters, dateFrom: e.target.value || undefined })}
        className="w-[150px]"
        aria-label="From date"
      />
      <Input
        type="date"
        value={filters.dateTo ?? ""}
        onChange={(e) => onChange({ ...filters, dateTo: e.target.value || undefined })}
        className="w-[150px]"
        aria-label="To date"
      />

      {hasActiveFilters && (
        <Button variant="ghost" size="sm" onClick={clearFilters}>
          <X className="h-3.5 w-3.5 mr-1" />
          Clear filters
        </Button>
      )}
    </div>
  );
}

import type { Tag } from "../api/tags";

interface TagBadgeProps {
  tag: Tag;
  onRemove?: () => void;
}

export function TagBadge({ tag, onRemove }: TagBadgeProps) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium"
      style={
        tag.color
          ? { backgroundColor: `${tag.color}20`, borderColor: tag.color, color: tag.color }
          : undefined
      }
    >
      {tag.name}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="ml-0.5 leading-none opacity-60 hover:opacity-100"
          aria-label={`Remove ${tag.name} tag`}
        >
          ×
        </button>
      )}
    </span>
  );
}

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Trash2, Pencil, Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useTags, useCreateTag, useUpdateTag, useDeleteTag } from "../api/tags";
import { tagSchema, type TagFormData } from "../schemas/tag";
import type { Tag } from "../api/tags";

interface TagManagerProps {
  open: boolean;
  onClose: () => void;
}

const DEFAULT_COLORS = ["#ef4444", "#f59e0b", "#22c55e", "#3b82f6", "#a855f7", "#ec4899"];

export function TagManager({ open, onClose }: TagManagerProps) {
  const { data: tags, isLoading } = useTags();
  const createTag = useCreateTag();
  const updateTag = useUpdateTag();
  const deleteTag = useDeleteTag();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<TagFormData>({ resolver: zodResolver(tagSchema) });

  const onCreate = (data: TagFormData) => {
    const color = DEFAULT_COLORS[(tags?.length ?? 0) % DEFAULT_COLORS.length];
    createTag.mutate(
      { name: data.name, color },
      { onSuccess: () => reset() }
    );
  };

  const startEditing = (tag: Tag) => {
    setEditingId(tag.id);
    setEditingName(tag.name);
  };

  const saveEditing = (tag: Tag) => {
    if (editingName.trim() && editingName !== tag.name) {
      updateTag.mutate({ id: tag.id, data: { name: editingName.trim(), color: tag.color ?? undefined } });
    }
    setEditingId(null);
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Manage Tags</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit(onCreate)} className="flex items-start gap-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="tag-name" className="sr-only">
              Tag name
            </Label>
            <Input id="tag-name" placeholder="New tag name" {...register("name")} />
            {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
          </div>
          <Button type="submit" disabled={createTag.isPending}>
            Add
          </Button>
        </form>

        <div className="space-y-1 max-h-64 overflow-y-auto">
          {isLoading && <p className="text-sm text-muted-foreground py-4">Loading tags...</p>}
          {tags?.length === 0 && (
            <p className="text-sm text-muted-foreground py-4">No tags yet</p>
          )}
          {tags?.map((tag) => (
            <div
              key={tag.id}
              className="flex items-center justify-between gap-2 rounded-md px-2 py-1.5 hover:bg-accent/50"
            >
              {editingId === tag.id ? (
                <>
                  <Input
                    autoFocus
                    value={editingName}
                    onChange={(e) => setEditingName(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && saveEditing(tag)}
                    className="h-8"
                  />
                  <div className="flex gap-1">
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => saveEditing(tag)}>
                      <Check className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => setEditingId(null)}
                    >
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </>
              ) : (
                <>
                  <span className="flex items-center gap-2 text-sm">
                    <span
                      className="h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: tag.color ?? "#94a3b8" }}
                    />
                    {tag.name}
                  </span>
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => startEditing(tag)}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive hover:text-destructive"
                      onClick={() => deleteTag.mutate(tag.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

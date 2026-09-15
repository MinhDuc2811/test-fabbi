import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useCreateTodo, useUpdateTodo, useAttachTag, useDetachTag } from "../api/todos";
import { todoSchema, type TodoFormData } from "../schemas/todo";
import type { Todo } from "../api/todos";
import { useTags } from "@/features/tags/api/tags";
import { TagBadge } from "@/features/tags/components/TagBadge";

interface TodoFormProps {
  mode: "create" | "edit";
  todo?: Todo;
  open: boolean;
  onClose: () => void;
}

export function TodoForm({ mode, todo, open, onClose }: TodoFormProps) {
  const createTodo = useCreateTodo();
  const updateTodo = useUpdateTodo();
  const attachTag = useAttachTag();
  const detachTag = useDetachTag();
  const { data: allTags } = useTags();
  const [pendingTagIds, setPendingTagIds] = useState<string[]>([]);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<TodoFormData>({
    resolver: zodResolver(todoSchema),
    defaultValues: {
      title: todo?.title || "",
      description: todo?.description || "",
    },
  });

  const onSubmit = (data: TodoFormData) => {
    if (mode === "create") {
      createTodo.mutate(data, {
        onSuccess: (newTodo) => {
          pendingTagIds.forEach((tagId) => {
            attachTag.mutate({ todoId: newTodo.id, tagId });
          });
          reset();
          setPendingTagIds([]);
          onClose();
        },
      });
    } else if (todo) {
      updateTodo.mutate(
        { id: todo.id, data },
        {
          onSuccess: () => {
            onClose();
          },
        }
      );
    }
  };

  const isPending = createTodo.isPending || updateTodo.isPending;

  const handleClose = () => {
    setPendingTagIds([]);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "Create Todo" : "Edit Todo"}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              placeholder="What needs to be done?"
              {...register("title")}
            />
            {errors.title && (
              <p className="text-sm text-destructive">
                {errors.title.message}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description (optional)</Label>
            <Input
              id="description"
              placeholder="Add details..."
              {...register("description")}
            />
            {errors.description && (
              <p className="text-sm text-destructive">
                {errors.description.message}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label>Tags</Label>
            {allTags?.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No tags yet - create one from Manage Tags first.
              </p>
            )}
            <div className="flex flex-wrap gap-1.5">
              {allTags?.map((tag) => {
                const isAttached =
                  mode === "edit" && todo
                    ? todo.tags.some((t) => t.id === tag.id)
                    : pendingTagIds.includes(tag.id);
                return (
                  <button
                    key={tag.id}
                    type="button"
                    disabled={attachTag.isPending || detachTag.isPending}
                    onClick={() => {
                      if (mode === "edit" && todo) {
                        if (isAttached) {
                          detachTag.mutate({ todoId: todo.id, tagId: tag.id });
                        } else {
                          attachTag.mutate({ todoId: todo.id, tagId: tag.id });
                        }
                      } else {
                        setPendingTagIds((prev) =>
                          isAttached ? prev.filter((id) => id !== tag.id) : [...prev, tag.id]
                        );
                      }
                    }}
                    className={isAttached ? "" : "opacity-40 hover:opacity-100"}
                  >
                    <TagBadge tag={tag} />
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending
                ? mode === "create"
                  ? "Creating..."
                  : "Saving..."
                : mode === "create"
                ? "Create"
                : "Save"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

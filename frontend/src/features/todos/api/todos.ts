import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { queryClient } from "@/lib/queryClient";
import type { Tag } from "@/features/tags/api/tags";

export interface Todo {
  id: string;
  title: string;
  description: string | null;
  completed: boolean;
  user_id: string;
  created_at: string;
  updated_at: string;
  tags: Tag[];
}

interface TodoListResponse {
  items: Todo[];
  total: number;
  page: number;
  size: number;
}

interface CreateTodoRequest {
  title: string;
  description?: string;
}

interface UpdateTodoRequest {
  title?: string;
  description?: string;
  completed?: boolean;
}

export interface TodoFilters {
  status?: "active" | "completed";
  tagId?: string;
  keyword?: string;
  dateFrom?: string;
  dateTo?: string;
}

export const EMPTY_FILTERS: TodoFilters = {};

export function useTodos(filters: TodoFilters = EMPTY_FILTERS, page: number = 1, size: number = 10000) {
  return useQuery({
    queryKey: ["todos", filters, page, size],
    queryFn: async (): Promise<TodoListResponse> => {
      const response = await api.get("/todos", {
        params: {
          page,
          size,
          status: filters.status,
          tag_id: filters.tagId,
          keyword: filters.keyword,
          date_from: filters.dateFrom,
          date_to: filters.dateTo,
        },
      });
      return response.data;
    },
  });
}

export function useCreateTodo() {
  return useMutation({
    mutationFn: async (data: CreateTodoRequest): Promise<Todo> => {
      const response = await api.post("/todos", data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["todos"] });
      toast.success("Todo created successfully!");
    },
    onError: () => {
      toast.error("Failed to create todo");
    },
  });
}


export function useUpdateTodo() {
  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: UpdateTodoRequest;
    }): Promise<Todo> => {
      const response = await api.put(`/todos/${id}`, data);
      return response.data;
    },
    onMutate: async ({ id, data }) => {
      // Cancel outgoing queries
      await queryClient.cancelQueries({ queryKey: ["todos"] });
      const previousQueries = queryClient.getQueriesData<TodoListResponse>({
        queryKey: ["todos"],
      });

      // Optimistically update every cached variant that contains this todo.
      queryClient.setQueriesData<TodoListResponse>({ queryKey: ["todos"] }, (old) => {
        if (!old) return old;
        return {
          ...old,
          items: old.items.map((todo) => (todo.id === id ? { ...todo, ...data } : todo)),
        };
      });

      return { previousQueries };
    },
    onError: (_err, _variables, context) => {
      context?.previousQueries?.forEach(([key, data]) => {
        queryClient.setQueryData(key, data);
      });
      toast.error("Failed to update todo");
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["todos"] });
    },
  });
}

export function useDeleteTodo() {
  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      await api.delete(`/todos/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["todos"] });
      toast.success("Todo deleted successfully!");
    },
    onError: () => {
      toast.error("Failed to delete todo");
    },
  });
}

export function useToggleTodo() {
  const updateTodo = useUpdateTodo();

  return {
    ...updateTodo,
    mutate: (todo: Todo) => {
      updateTodo.mutate({
        id: todo.id,
        data: { completed: !todo.completed },
      });
    },
  };
}

export function useAttachTag() {
  return useMutation({
    mutationFn: async ({ todoId, tagId }: { todoId: string; tagId: string }): Promise<void> => {
      await api.post(`/todos/${todoId}/tags/${tagId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["todos"] });
    },
    onError: () => {
      toast.error("Failed to attach tag");
    },
  });
}

export function useDetachTag() {
  return useMutation({
    mutationFn: async ({ todoId, tagId }: { todoId: string; tagId: string }): Promise<void> => {
      await api.delete(`/todos/${todoId}/tags/${tagId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["todos"] });
    },
    onError: () => {
      toast.error("Failed to detach tag");
    },
  });
}

export function useBulkUpdateStatus() {
  return useMutation({
    mutationFn: async ({
      todoIds,
      completed,
    }: {
      todoIds: string[];
      completed: boolean;
    }): Promise<{ updated: number }> => {
      const response = await api.patch("/todos/bulk-status", {
        todo_ids: todoIds,
        completed,
      });
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["todos"] });
      toast.success(`Updated ${data.updated} todo(s)`);
    },
    onError: () => {
      toast.error("Failed to update todos");
    },
  });
}

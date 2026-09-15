import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { queryClient } from "@/lib/queryClient";

export interface Tag {
  id: string;
  user_id: string;
  name: string;
  color: string | null;
  created_at: string;
  updated_at: string;
}

interface TagRequest {
  name: string;
  color?: string;
}

export function useTags() {
  return useQuery({
    queryKey: ["tags"],
    queryFn: async (): Promise<Tag[]> => {
      const response = await api.get("/tags");
      return response.data;
    },
  });
}

export function useCreateTag() {
  return useMutation({
    mutationFn: async (data: TagRequest): Promise<Tag> => {
      const response = await api.post("/tags", data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] });
      toast.success("Tag created successfully!");
    },
    onError: (error: unknown) => {
      const isDuplicate =
        typeof error === "object" &&
        error !== null &&
        "response" in error &&
        (error as { response?: { status?: number } }).response?.status === 409;
      toast.error(isDuplicate ? "A tag with this name already exists" : "Failed to create tag");
    },
  });
}

export function useUpdateTag() {
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: TagRequest }): Promise<Tag> => {
      const response = await api.patch(`/tags/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] });
      queryClient.invalidateQueries({ queryKey: ["todos"] });
      toast.success("Tag updated successfully!");
    },
    onError: (error: unknown) => {
      const isDuplicate =
        typeof error === "object" &&
        error !== null &&
        "response" in error &&
        (error as { response?: { status?: number } }).response?.status === 409;
      toast.error(isDuplicate ? "A tag with this name already exists" : "Failed to update tag");
    },
  });
}

export function useDeleteTag() {
  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      await api.delete(`/tags/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] });
      queryClient.invalidateQueries({ queryKey: ["todos"] });
      toast.success("Tag deleted successfully!");
    },
    onError: () => {
      toast.error("Failed to delete tag");
    },
  });
}

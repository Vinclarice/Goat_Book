import { useQuery } from "@tanstack/react-query";

import { ArchiveManager } from "../../ArchiveManager";
import { apiV1 } from "../../api/client";

export function ArchiveRoute() {
  const { data, error, isPending } = useQuery({
    queryKey: ["archive"],
    queryFn: async () => {
      const { data, error } = await apiV1.GET("/api/v1/archive");
      if (error) throw error;
      return data;
    },
  });

  if (isPending) return <p>Loading…</p>;
  if (error) return <p>Something went wrong.</p>;

  return <ArchiveManager initialData={data} />;
}

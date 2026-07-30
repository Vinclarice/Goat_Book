import { useQuery } from "@tanstack/react-query";

import { AgendaWorkspace } from "../../AgendaWorkspace";
import { apiV1 } from "../../api/client";

export function AgendaRoute() {
  const { data, error, isPending } = useQuery({
    queryKey: ["agenda"],
    queryFn: async () => {
      const { data, error } = await apiV1.GET("/api/v1/agenda");
      if (error) throw error;
      return data;
    },
  });

  if (isPending) return <p>Loading…</p>;
  if (error) return <p>Something went wrong.</p>;

  return <AgendaWorkspace initialData={data} />;
}

import { useQuery } from "@tanstack/react-query";

import { AgendaWorkspace } from "../../AgendaWorkspace";
import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { RouteFailure } from "./RouteFailure";

export function AgendaRoute() {
  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["agenda"],
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/agenda");
      if (!response.ok || !data) throw new RequestFailed(response.status);
      return data;
    },
  });

  if (isPending) return <p>Loading…</p>;
  if (error) return <RouteFailure status={statusOf(error)} onRetry={() => refetch()} />;

  return <AgendaWorkspace initialData={data} />;
}

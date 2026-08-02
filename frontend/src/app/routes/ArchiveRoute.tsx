import { useQuery } from "@tanstack/react-query";

import { ArchiveManager } from "../../ArchiveManager";
import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { RouteFailure } from "./RouteFailure";

export function ArchiveRoute() {
  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["archive"],
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/archive");
      if (!response.ok || !data) throw new RequestFailed(response.status);
      return data;
    },
  });

  if (isPending) return <p>Loading…</p>;
  if (error) return <RouteFailure status={statusOf(error)} onRetry={() => refetch()} />;

  return <ArchiveManager initialData={data} />;
}

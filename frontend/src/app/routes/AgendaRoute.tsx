import { useQuery } from "@tanstack/react-query";

import { apiV1 } from "../../api/client";

/**
 * Proof-of-chain only: login gate -> shell -> router -> query -> typed
 * client -> real data. Deliberately unstyled -- Steps 3-4 replace this
 * with the real Agenda route.
 */
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

  return <pre>{JSON.stringify(data, null, 2)}</pre>;
}

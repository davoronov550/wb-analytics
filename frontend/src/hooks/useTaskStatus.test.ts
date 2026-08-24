/** useTaskStatus polls a parse task and stops on a terminal state. */
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { useTaskStatus } from "./useTaskStatus";

afterEach(() => vi.restoreAllMocks());

function mockStatus(status: string, extra: Record<string, unknown> = {}) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      task_id: "t",
      query: "наушники",
      status,
      created: 2,
      updated: 0,
      collected_count: 2,
      error: null,
      finished_at: null,
      ...extra,
    }),
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

test("returns null when no task id is set", () => {
  const { result } = renderHook(() => useTaskStatus(null));
  expect(result.current).toBeNull();
});

test("fetches status and stops polling on a terminal state", async () => {
  const fetchMock = mockStatus("done");
  const { result } = renderHook(() => useTaskStatus("t"));
  await waitFor(() => expect(result.current?.status).toBe("done"));
  expect(result.current?.collected_count).toBe(2);
  expect(fetchMock).toHaveBeenCalledTimes(1); // terminal → no re-poll
});

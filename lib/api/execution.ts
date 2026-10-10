import { ApiClient } from "@/lib/api/client";
import { parseExecutionTask, parseExecutionTasks } from "@/lib/api/activity-agent-contract";
import type {
  ExecutionTask,
  ExecutionTaskInput,
  ExecutionTaskUpdateInput
} from "@/lib/types/activity-agent";

const api = new ApiClient();

export const executionApi = {
  list(activityId: string) {
    return api
      .get<unknown>(`/activities/${encodeURIComponent(activityId)}/execution-tasks`)
      .then((value) => parseExecutionTasks(value, activityId));
  },
  create(activityId: string, payload: ExecutionTaskInput) {
    return api
      .post<unknown>(`/activities/${encodeURIComponent(activityId)}/execution-tasks`, payload)
      .then((value) => parseExecutionTask(value, activityId));
  },
  confirm(activityId: string, taskId: string) {
    return api
      .post<unknown>(
        `/activities/${encodeURIComponent(activityId)}/execution-tasks/${encodeURIComponent(taskId)}/confirm`,
        {}
      )
      .then((value) => parseExecutionTask(value, activityId));
  },
  update(
    activityId: string,
    taskId: string,
    payload: ExecutionTaskUpdateInput
  ): Promise<ExecutionTask> {
    return api
      .patch<unknown>(
        `/activities/${encodeURIComponent(activityId)}/execution-tasks/${encodeURIComponent(taskId)}`,
        payload
      )
      .then((value) => parseExecutionTask(value, activityId));
  }
};

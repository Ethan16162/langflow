import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface GenerateWorkflowRequest {
  workflow_data: any;
  flow_name: string;
  description?: string;
}

export const useGenerateWorkflow: useMutationFunctionType<
  any,
  GenerateWorkflowRequest
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const GenerateWorkflowFn = async (
    payload: GenerateWorkflowRequest,
  ): Promise<any> => {
    const response = await api.post(
      `${getURL("COPILOT")}/generate-workflow`,
      payload,
    );
    return response.data;
  };

  const mutation: UseMutationResult<any, any, GenerateWorkflowRequest> = mutate(
    ["useGenerateWorkflow"],
    GenerateWorkflowFn,
    {
      onSuccess: (data) => {
        queryClient.refetchQueries({
          queryKey: ["useGetFolders"],
        });
        queryClient.refetchQueries({
          queryKey: ["useGetFolder"],
        });
        if (options?.onSuccess) {
          options.onSuccess(data, payload, undefined);
        }
      },
      ...options,
    },
  );

  return mutation;
};

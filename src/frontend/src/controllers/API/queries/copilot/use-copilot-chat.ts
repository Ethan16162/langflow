import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface CopilotMessage {
  role: "user" | "assistant";
  content: string;
}

export interface CopilotChatRequest {
  message: string;
  conversation_history?: CopilotMessage[];
}

export interface CopilotChatResponse {
  message: string;
  workflow_data?: any;
  flow_id?: string;
}

export const useCopilotChat: useMutationFunctionType<
  CopilotChatResponse,
  CopilotChatRequest
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const CopilotChatFn = async (
    payload: CopilotChatRequest,
  ): Promise<CopilotChatResponse> => {
    const response = await api.post(`${getURL("COPILOT")}/chat`, payload);
    return response.data;
  };

  const mutation: UseMutationResult<
    CopilotChatResponse,
    any,
    CopilotChatRequest
  > = mutate(["useCopilotChat"], CopilotChatFn, {
    ...options,
  });

  return mutation;
};

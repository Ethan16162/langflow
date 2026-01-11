import { useEffect, useMemo } from "react";
import JsonOutputViewComponent from "@/components/core/jsonOutputComponent/json-output-view";
import { MAX_TEXT_LENGTH } from "@/constants/constants";
import type { LogsLogType, OutputLogType } from "@/types/api";
import ForwardedIconComponent from "../../../../../../components/common/genericIconComponent";
import DataOutputComponent from "../../../../../../components/core/dataOutputComponent";
import SelectableDataOutputComponent from "../../../../../../components/core/selectableDataOutputComponent";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../../../../components/ui/alert";
import { Case } from "../../../../../../shared/components/caseComponent";
import TextOutputView from "../../../../../../shared/components/textOutputView";
import useFlowStore from "../../../../../../stores/flowStore";
import ErrorOutput from "./components";

// Define the props type
interface SwitchOutputViewProps {
  nodeId: string;
  outputName: string;
  type: "Outputs" | "Logs";
}

function SwitchOutputView({ nodeId, outputName, type }: SwitchOutputViewProps) {
  // 明确标记组件函数是否被调用
  // eslint-disable-next-line no-console
  console.warn("🔥 SwitchOutputView render", { nodeId, outputName, type });
  const flowPool = useFlowStore((state) => state.flowPool);
  const nodes = useFlowStore((state) => state.nodes);

  const flowPoolNode = (flowPool[nodeId] ?? [])[
    (flowPool[nodeId]?.length ?? 1) - 1
  ];

  // Get the node to access output configuration
  const currentNode = nodes.find((node) => node.id === nodeId);
  const outputConfig = currentNode?.data?.node?.outputs?.find(
    (output) => output.name === outputName,
  );

  // Check if this is a Tool output
  const isToolOutput =
    outputConfig &&
    (outputConfig.method === "to_toolkit" ||
      (outputConfig.types && outputConfig.types.includes("Tool")));

  // Check if this is Chroma component's search_results output (supports selection)
  const results: OutputLogType | LogsLogType =
    (type === "Outputs"
      ? (flowPoolNode?.data?.outputs?.[outputName] ??
        // 某些组件可能只在 logs 里暴露，我们做一个兜底
        flowPoolNode?.data?.logs?.[outputName])
      : flowPoolNode?.data?.logs?.[outputName]) ?? {};
  const resultType = results?.type;

  const isChromaSearchResults =
    currentNode?.data?.node?.display_name?.toLowerCase().includes("chroma") &&
    outputName === "search_results";

  console.log("isChromaSearchResults", isChromaSearchResults);

  let resultMessage = results?.message ?? {};

  console.log("resultMessage", resultMessage);

  const RECORD_TYPES = ["array", "message"];
  const JSON_TYPES = ["data", "object"];
  if ((resultMessage as any)?.raw) {
    resultMessage = resultMessage.raw;
  }

  const resultMessageMemoized = useMemo(() => {
    if (!resultMessage) return "";

    if (
      typeof resultMessage === "string" &&
      resultMessage.length > MAX_TEXT_LENGTH
    ) {
      return `${resultMessage.substring(0, MAX_TEXT_LENGTH)}...`;
    }
    if (Array.isArray(resultMessage)) {
      return resultMessage.map((item) => {
        if (item?.data && typeof item?.data === "object") {
          const truncatedData = Object.fromEntries(
            Object.entries(item?.data).map(([key, value]) => {
              if (typeof value === "string" && value.length > MAX_TEXT_LENGTH) {
                return [key, `${value.substring(0, MAX_TEXT_LENGTH)}...`];
              }
              return [key, value];
            }),
          );
          return { ...item, data: truncatedData };
        }
        return item;
      });
    }

    return resultMessage;
  }, [resultMessage]);

  // Temporary debug logs to help diagnose why Chroma search_results may appear empty
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.warn("🔥 Browser log: SwitchOutputView debugging ↓↓↓");
    // eslint-disable-next-line no-console
    console.log("[SwitchOutputView] nodeId:", nodeId);
    // eslint-disable-next-line no-console
    console.log("[SwitchOutputView] outputName:", outputName);
    // eslint-disable-next-line no-console
    console.log("[SwitchOutputView] raw results:", results);
    // eslint-disable-next-line no-console
    console.log("[SwitchOutputView] resultType:", resultType);
    // eslint-disable-next-line no-console
    console.log("[SwitchOutputView] resultMessage:", resultMessage);
    // eslint-disable-next-line no-console
    console.log(
      "[SwitchOutputView] resultMessageMemoized:",
      resultMessageMemoized,
    );
  }, [
    nodeId,
    outputName,
    results,
    resultType,
    resultMessage,
    resultMessageMemoized,
  ]);

  // Custom component for Tool output display
  const ToolOutputDisplay = ({ tools }) => {
    if (!Array.isArray(tools) || tools.length === 0) {
      return <div>No tools available</div>;
    }

    return (
      <div className="space-y-4">
        {tools?.map((tool, index) => (
          <div key={index} className="border rounded-lg p-4 bg-muted/20">
            <div
              data-testid="tool_name"
              className={
                "font-medium text-lg" + (tool?.description ? " mb-2" : "")
              }
            >
              {tool.name || `Tool ${index + 1}`}
            </div>
            {tool?.description && (
              <div
                data-testid="tool_description"
                className="text-sm text-muted-foreground mb-3"
              >
                {tool.description}
              </div>
            )}
            {tool?.tags && tool?.tags?.length > 0 && (
              <div data-testid="tool_tags" className="flex flex-wrap gap-2">
                {tool.tags.map((tag, tagIndex) => (
                  <span
                    key={tagIndex}
                    className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-primary/10 text-primary"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    );
  };

  return type === "Outputs" ? (
    <>
      <Case condition={isToolOutput && resultMessageMemoized}>
        <ToolOutputDisplay
          tools={
            Array.isArray(resultMessageMemoized)
              ? resultMessageMemoized
              : [resultMessageMemoized]
          }
        />
      </Case>
      <Case
        condition={(!resultType || resultType === "unknown") && !isToolOutput}
      >
        <div>NO OUTPUT</div>
      </Case>
      <Case
        condition={
          (resultType === "error" || resultType === "ValueError") &&
          !isToolOutput
        }
      >
        <ErrorOutput
          value={`${resultMessageMemoized?.errorMessage}\n\n${resultMessageMemoized?.stackTrace}`}
        />
      </Case>

      <Case condition={resultType === "text" && !isToolOutput}>
        <TextOutputView left={false} value={resultMessageMemoized} />
      </Case>

      <Case
        condition={
          RECORD_TYPES.includes(resultType) &&
          !isToolOutput &&
          !isChromaSearchResults
        }
      >
        <DataOutputComponent
          rows={
            Array.isArray(resultMessageMemoized)
              ? (resultMessageMemoized as Array<any>).every(
                  (item) => item?.data,
                )
                ? (resultMessageMemoized as Array<any>).map(
                    (item) => item?.data,
                  )
                : resultMessageMemoized
              : Object.keys(resultMessageMemoized)?.length > 0
                ? [resultMessageMemoized]
                : []
          }
          pagination={true}
          columnMode="union"
        />
      </Case>

      {/* 强制：只要是 Chroma 的 search_results，一律使用可选择表格展示 */}
      <Case condition={isChromaSearchResults}>
        {(() => {
          // 计算要传递给表格的 rows
          let computedRows: any[] = [];
          if (Array.isArray(resultMessageMemoized)) {
            // 检查每个元素是否有嵌套的 data 字段
            const hasNestedData = (resultMessageMemoized as Array<any>).every(
              (item) => item?.data && typeof item.data === "object",
            );
            if (hasNestedData) {
              // 展开 item.data，提取出平级的字段（id, _index, file_path, text 等）
              computedRows = (resultMessageMemoized as Array<any>).map(
                (item) => item.data,
              );
            } else {
              // 如果没有嵌套 data，直接使用原始数组
              computedRows = resultMessageMemoized;
            }
          } else if (
            resultMessageMemoized &&
            typeof resultMessageMemoized === "object" &&
            Object.keys(resultMessageMemoized as any).length > 0
          ) {
            computedRows = [resultMessageMemoized];
          }

          // 调试日志：确认计算出的 rows 结构（仅在开发环境）
          if (process.env.NODE_ENV === "development") {
            console.log("🔥 Chroma search_results - computedRows:", {
              computedRowsLength: computedRows.length,
              firstRow: computedRows[0],
              allRows: computedRows,
            });
          }

          return (
            <SelectableDataOutputComponent
              rows={computedRows}
              pagination={true}
              columnMode="union"
              nodeId={nodeId}
              outputName={outputName}
            />
          );
        })()}
      </Case>
      <Case condition={JSON_TYPES.includes(resultType) && !isToolOutput}>
        <JsonOutputViewComponent
          nodeId={nodeId}
          outputName={outputName}
          data={resultMessageMemoized}
        />
      </Case>

      <Case condition={resultType === "stream" && !isToolOutput}>
        <div className="flex h-full w-full items-center justify-center align-middle">
          <Alert variant={"default"} className="w-fit">
            <ForwardedIconComponent
              name="AlertCircle"
              className="h-5 w-5 text-primary"
            />
            <AlertTitle>{"Streaming is not supported"}</AlertTitle>
            <AlertDescription>
              {
                "Use the playground to interact with components that stream data"
              }
            </AlertDescription>
          </Alert>
        </div>
      </Case>
    </>
  ) : (
    <DataOutputComponent
      rows={
        Array.isArray(results)
          ? (results as Array<any>).every((item) => item?.data)
            ? (results as Array<any>).map((item) => item?.data)
            : results
          : Object.keys(results)?.length > 0
            ? [results]
            : []
      }
      pagination={true}
      columnMode="union"
    />
  );
}

export default SwitchOutputView;

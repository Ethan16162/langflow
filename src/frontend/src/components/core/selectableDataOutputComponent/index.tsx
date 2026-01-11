import type {
  ColDef,
  ColGroupDef,
  SelectionChangedEvent,
} from "ag-grid-community";
import { useEffect, useRef, useState } from "react";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import useFlowStore from "@/stores/flowStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { extractColumnsFromRows } from "../../../utils/utils";

interface SelectableDataOutputComponentProps {
  pagination: boolean;
  rows: any[];
  columnMode?: "intersection" | "union";
  nodeId: string;
  outputName: string;
}

function SelectableDataOutputComponent({
  pagination,
  rows,
  columnMode = "union",
  nodeId,
  outputName,
}: SelectableDataOutputComponentProps) {
  const maxItemsLength = useUtilityStore(
    (state) => state.serializationMaxItemsLength,
  );
  const [rowsInternal, setRowsInternal] = useState(
    rows.slice(0, maxItemsLength),
  );
  const [selectedRows, setSelectedRows] = useState<any[]>([]);
  const agGridRef = useRef<any>(null);

  const nodes = useFlowStore((state) => state.nodes);
  const node = nodes.find((n) => n.id === nodeId);

  const { handleOnNewValue } = useHandleOnNewValue({
    node: node?.data?.node || ({} as any),
    nodeId,
    name: "selected_result_ids",
  });

  // src/frontend/src/components/core/selectableDataOutputComponent/index.tsx
  useEffect(() => {
    const rowsSliced = rows.slice(0, maxItemsLength);
    // 去掉“判断row是否是对象”的逻辑，直接用原始rows
    setRowsInternal(rowsSliced);
    // Reset selection when rows change
    setSelectedRows([]);
    if (agGridRef.current?.api) {
      agGridRef.current.api.deselectAll();
    }
  }, [rows, maxItemsLength]);

  // 调试日志：确认收到的 rows 和提取的列（仅在开发环境）
  useEffect(() => {
    if (process.env.NODE_ENV === "development") {
      console.log("🔥 SelectableDataOutputComponent - rowsInternal:", {
        rowsInternalLength: rowsInternal.length,
        firstRow: rowsInternal[0],
        allRows: rowsInternal,
      });
    }
  }, [rowsInternal]);

  const columns = extractColumnsFromRows(rowsInternal, columnMode);

  // useEffect(() => {
  //   if (process.env.NODE_ENV === "development") {
  //     console.log("🔥 SelectableDataOutputComponent - columns:", {
  //       columnsLength: columns.length,
  //       columns: columns,
  //     });
  //   }
  // }, [columns]);

  const columnDefs = columns.map((col, idx) => ({
    ...col,
    resizable: true,
    sortable: true,
    filter: true,
  })) as (ColDef<any> | ColGroupDef<any>)[];

  const handleSelectionChanged = (event: SelectionChangedEvent) => {
    const selectedData = event.api.getSelectedRows();
    setSelectedRows(selectedData);
  };

  const handleApplySelection = () => {
    // Extract IDs from selected rows
    // The row structure: row is already item.data, so ID should be in row.id or row._index
    const selectedIds = selectedRows
      .map((row, index) => {
        // 优先使用  _index，其次使用id，最后使用行索引
        const id = row?._index?.toString() || row?.id || String(index);
        return id;
      })
      .filter(
        (id): id is string => id !== null && id !== undefined && id !== "",
      );

    if (selectedIds.length === 0) {
      console.warn("No valid IDs found in selected rows:", selectedRows);
      return;
    }

    console.log("🔥 Applying selection with IDs:", selectedIds);

    // Update the component's selected_result_ids field
    handleOnNewValue({
      value: JSON.stringify(selectedIds),
    });
  };

  // 调试：确认传递给 TableComponent 的数据
  useEffect(() => {
    if (process.env.NODE_ENV === "development") {
      console.log(
        "🔥 SelectableDataOutputComponent - Final props to TableComponent:",
        {
          rowsInternalLength: rowsInternal.length,
          columnDefsLength: columnDefs.length,
          columnDefs: columnDefs,
          firstRowData: rowsInternal[0],
        },
      );
    }
  }, [rowsInternal, columnDefs]);

  // 确保有数据才渲染表格
  if (!rowsInternal || rowsInternal.length === 0) {
    return (
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            Select results to filter
          </span>
        </div>
        <div className="flex h-full w-full items-center justify-center rounded-md border p-4">
          <span className="text-sm text-muted-foreground">
            No data available
          </span>
        </div>
      </div>
    );
  }

  if (!columnDefs || columnDefs.length === 0) {
    return (
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            Select results to filter
          </span>
        </div>
        <div className="flex h-full w-full items-center justify-center rounded-md border p-4">
          <span className="text-sm text-muted-foreground">
            No columns available
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 h-full">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          {selectedRows.length > 0
            ? `${selectedRows.length} result${selectedRows.length > 1 ? "s" : ""} selected`
            : "Select results to filter"}
        </span>
        {selectedRows.length > 0 && (
          <Button
            variant="default"
            size="sm"
            onClick={handleApplySelection}
            className="h-8"
          >
            <ForwardedIconComponent name="Check" className="h-4 w-4 mr-1" />
            Apply Selection
          </Button>
        )}
      </div>
      <div className="w-full flex-1 min-h-[400px]">
        <TableComponent
          ref={agGridRef}
          autoSizeStrategy={{
            type: "fitGridWidth",
            defaultMinWidth: maxItemsLength,
          }}
          key={`selectableDataOutputComponent-${rowsInternal.length}-${columnDefs.length}`}
          overlayNoRowsTemplate="No data available"
          paginationInfo={
            rows.length > maxItemsLength ? rows[maxItemsLength] : undefined
          }
          suppressRowClickSelection={false}
          rowSelection="multiple"
          onSelectionChanged={handleSelectionChanged}
          pagination={pagination}
          columnDefs={columnDefs}
          rowData={rowsInternal}
          getRowId={(params) => {
            // 使用 id 字段作为唯一标识，如果没有则使用 _index，最后使用数据对象的字符串表示
            if (params.data?.id) {
              return String(params.data.id);
            }
            if (params.data?._index !== undefined) {
              return String(params.data._index);
            }
            // 如果都没有，使用数据对象的字符串表示作为后备方案
            return String(params.data) || String(Math.random());
          }}
          rowHeight={50}
          headerHeight={40}
          defaultColDef={{
            flex: 1,
            minWidth: 100,
          }}
          displayEmptyAlert={false}
        />
      </div>
    </div>
  );
}

export default SelectableDataOutputComponent;

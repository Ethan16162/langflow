# Langflow 工作流构建与执行详细分析

## 概述

Langflow 采用前后端分离架构，前端通过拖拽构建工作流，将工作流配置以 JSON 格式传送到后端，后端则负责解析、构建图结构并执行。

---

## 第一部分：前端如何传输工作流配置

### 1.1 工作流在前端的构成

前端使用 React Flow（xy-flow）库进行可视化构建，工作流由以下部分组成：

```typescript
// src/frontend/src/types/flow
type FlowType = {
  id: string;
  name: string;
  description?: string;
  data: ReactFlowJsonObject<AllNodeType, EdgeType>; // 关键：包含 nodes 和 edges
  folder_id?: string;
  endpoint_name?: string;
  is_component?: boolean;
  // ... 其他字段
}

// data 结构（ReactFlow标准格式）
type ReactFlowJsonObject = {
  nodes: AllNodeType[];      // 节点列表
  edges: EdgeType[];          // 连接关系
  viewport?: { x, y, zoom }  // 视图状态
}
```

### 1.2 前端保存工作流的方式

**文件位置：** [src/frontend/src/hooks/flows/use-save-flow.ts](src/frontend/src/hooks/flows/use-save-flow.ts)

**保存流程：**
```typescript
const useSaveFlow = () => {
  const saveFlow = async (flow?: FlowType): Promise<void> => {
    // 1. 获取当前流的最新状态
    const currentFlow = useFlowStore.getState().currentFlow;
    const nodes = useFlowStore.getState().nodes;
    const edges = useFlowStore.getState().edges;
    const reactFlowInstance = useFlowStore.getState().reactFlowInstance;

    // 2. 构建完整的工作流对象
    flow = {
      ...currentFlow,
      data: {
        ...flowData,
        nodes,              // 当前节点列表
        edges,              // 当前连接列表
        viewport: reactFlowInstance?.getViewport() // 视图状态
      }
    };

    // 3. 调用 PATCH /api/v1/flows/{id} 发送到后端
    const { id, name, data, description, folder_id, endpoint_name, locked } = flow;
    mutate({
      id,
      name,
      data: data!,        // JSON 格式的工作流配置
      description,
      folder_id,
      endpoint_name,
      locked
    });
  };
};
```

### 1.3 传输的 JSON 格式示例

前端以以下格式发送到后端：

```json
{
  "id": "flow-uuid",
  "name": "MyFlow",
  "description": "Flow description",
  "data": {
    "nodes": [
      {
        "id": "node-1",
        "data": {
          "type": "ChatInput",
          "display_name": "Chat Input",
          "node": {
            "template": {
              "input_value": { "value": "", "type": "str" }
            }
          }
        },
        "position": { "x": 100, "y": 100 }
      },
      {
        "id": "node-2",
        "data": {
          "type": "OpenAI",
          "display_name": "OpenAI LLM",
          "node": {
            "template": {
              "model": { "value": "gpt-4", "type": "str" },
              "temperature": { "value": 0.7, "type": "float" }
            }
          }
        },
        "position": { "x": 300, "y": 100 }
      }
    ],
    "edges": [
      {
        "source": "node-1",
        "target": "node-2",
        "data": {
          "sourceHandle": {
            "id": "node-1",
            "name": "message",
            "dataType": "ChatMessage"
          },
          "targetHandle": {
            "id": "node-2",
            "fieldName": "input",
            "type": "str"
          }
        }
      }
    ],
    "viewport": { "x": 0, "y": 0, "zoom": 1 }
  },
  "folder_id": "folder-uuid",
  "endpoint_name": "my-flow"
}
```

### 1.4 API 端点

**文件位置：** [src/frontend/src/controllers/API/queries/flows/use-patch-update-flow.ts](src/frontend/src/controllers/API/queries/flows/use-patch-update-flow.ts)

```typescript
const PatchUpdateFlowFn = async (payload: IPatchUpdateFlow): Promise<any> => {
  // 发送 PATCH 请求到后端
  const response = await api.patch(`${getURL("FLOWS")}/${id}`, payload);
  // getURL("FLOWS") 返回 "/api/v1/flows"
  // 完整端点：PATCH /api/v1/flows/{flow_id}
  return response.data;
};
```

---

## 第二部分：后端接收与构建工作流

### 2.1 后端存储工作流的数据模型

**文件位置：** [src/backend/base/langflow/services/database/models/flow/model.py](src/backend/base/langflow/services/database/models/flow/model.py)

```python
class Flow(FlowBase, table=True):
    id: UUID                                  # 工作流唯一标识
    name: str                                 # 工作流名称
    description: str | None                  # 工作流描述
    data: dict | None                        # 核心：存储的工作流配置 JSON
    user_id: UUID | None                     # 用户 ID
    folder_id: UUID | None                   # 文件夹 ID
    endpoint_name: str | None                # 端点名称
    is_component: bool                       # 是否为组件
    webhook: bool                            # 是否支持 webhook
    locked: bool                             # 是否锁定
    updated_at: datetime                     # 更新时间
    # ... 其他字段

    def to_data(self):
        """转换为数据对象"""
        return Data(data={
            "id": self.id,
            "data": self.data,  # 保存的工作流配置
            "name": self.name,
            "description": self.description,
            "updated_at": self.updated_at
        })
```

### 2.2 后端保存工作流

**文件位置：** [src/backend/base/langflow/api/v1/flows.py](src/backend/base/langflow/api/v1/flows.py#L350)

```python
@router.patch("/{flow_id}", response_model=FlowRead, status_code=200)
async def update_flow(
    *,
    session: DbSession,
    flow_id: UUID,
    flow: FlowUpdate,  # 包含新的 data JSON
    current_user: CurrentActiveUser,
):
    """更新工作流"""
    db_flow = await _read_flow(session=session, flow_id=flow_id, user_id=current_user.id)

    # 将前端发送的配置保存到数据库
    update_data = flow.model_dump(exclude_unset=True, exclude_none=True)

    for key, value in update_data.items():
        setattr(db_flow, key, value)  # 包括 data 字段

    # 同时保存到文件系统（如果配置了）
    await _save_flow_to_fs(db_flow)

    await session.commit()
    return db_flow
```

### 2.3 数据库中的实际存储

工作流的 `data` 字段在数据库中以 JSON 格式存储：

```python
# 在 Flow 模型中
data: dict | None = Field(default=None, sa_column=Column(JSON))
```

---

## 第三部分：后端执行工作流

### 3.1 工作流执行的入口端点

**文件位置：** [src/backend/base/langflow/api/v1/endpoints.py](src/backend/base/langflow/api/v1/endpoints.py#L349)

#### 简化模式（推荐）
```python
@router.post("/run/{flow_id_or_name}", response_model=None)
async def simplified_run_flow(
    *,
    flow: Annotated[FlowRead | None, Depends(get_flow_by_id_or_endpoint_name)],
    input_request: SimplifiedAPIRequest | None = None,
    stream: bool = False,
    api_key_user: Annotated[UserRead, Depends(api_key_security)],
    context: dict | None = None,
    http_request: Request,
):
    """
    执行工作流的主入口
    POST /api/v1/run/{flow_id_or_name}

    请求体示例：
    {
      "input_value": "用户输入的消息",
      "input_type": "chat",
      "output_type": "chat",
      "tweaks": {
        "OpenAI-1": {
          "temperature": 0.5,
          "model": "gpt-3.5-turbo"
        }
      },
      "session_id": "optional-session-id"
    }
    """
    # 1. 从数据库获取工作流
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")

    # 2. 准备执行参数
    graph_data = flow.data.copy()

    # 3. 应用 tweaks（参数调整）
    graph_data = process_tweaks(graph_data, input_request.tweaks or {}, stream=stream)

    # 4. 从 JSON 构建图对象
    graph = Graph.from_payload(
        graph_data,
        flow_id=str(flow.id),
        user_id=str(api_key_user.id),
        flow_name=flow.name,
        context=context
    )

    # 5. 执行工作流
    result = await simple_run_flow(
        flow=flow,
        input_request=input_request,
        stream=stream,
        api_key_user=api_key_user,
        context=context
    )

    return result
```

#### 高级模式
```python
@router.post("/run/advanced/{flow_id_or_name}", response_model=RunResponse)
async def experimental_run_flow(
    *,
    inputs: list[InputValueRequest] | None = None,
    outputs: list[str] | None = None,
    tweaks: Tweaks | None = None,
    stream: bool = False,
    session_id: str | None = None,
    api_key_user: Annotated[UserRead, Depends(api_key_security)],
):
    """
    高级执行模式，支持多个输入、自定义输出和会话
    POST /api/v1/run/advanced/{flow_id_or_name}
    """
    # 类似流程，但支持更多自定义选项
```

### 3.2 工作流执行的核心流程

**文件位置：** [src/backend/base/langflow/processing/process.py](src/backend/base/langflow/processing/process.py)

#### 第一步：解析工作流配置
```python
def process_tweaks(
    graph_data: dict[str, Any],
    tweaks: Tweaks | dict[str, dict[str, Any]],
    *,
    stream: bool = False
) -> dict[str, Any]:
    """
    应用参数调整到工作流配置

    tweaks 示例：
    {
      "OpenAI-1": {
        "temperature": 0.5
      },
      "ChatInput-1": {
        "input_value": "new value"
      }
    }
    """
    nodes = graph_data.get("nodes", [])
    nodes_map = {node.get("id"): node for node in nodes}

    # 将 tweaks 应用到对应的节点
    for node_id, node_tweaks in tweaks.items():
        if node := nodes_map.get(node_id):
            apply_tweaks(node, node_tweaks)

    return graph_data
```

#### 第二步：从 JSON 构建图对象
```python
# 文件位置：src/lfx/src/lfx/graph/graph/base.py

@classmethod
def from_payload(
    cls,
    payload: dict,
    flow_id: str | None = None,
    flow_name: str | None = None,
    user_id: str | None = None,
    context: dict | None = None,
) -> Graph:
    """
    从前端发送的 JSON 构建可执行的图对象

    输入：
    {
      "data": {
        "nodes": [...],
        "edges": [...]
      }
    }
    """
    # 1. 提取节点和边
    if "data" in payload:
        payload = payload["data"]

    vertices = payload["nodes"]      # 节点列表
    edges = payload["edges"]         # 边列表

    # 2. 创建 Graph 实例
    graph = cls(
        flow_id=flow_id,
        flow_name=flow_name,
        user_id=user_id,
        context=context
    )

    # 3. 添加节点和边到图中
    graph.add_nodes_and_edges(vertices, edges)

    return graph
```

#### 第三步：添加节点和边
```python
def add_nodes_and_edges(self, nodes: list[NodeData], edges: list[EdgeData]) -> None:
    """
    构建图的拓扑结构
    """
    self._vertices = nodes
    self._edges = edges
    self.raw_graph_data = {"nodes": nodes, "edges": edges}

    # 标记顶层节点（用于执行起点）
    self.top_level_vertices = []
    for vertex in self._vertices:
        if vertex_id := vertex.get("id"):
            self.top_level_vertices.append(vertex_id)

    # 处理工作流（检测循环、拓扑排序等）
    self._graph_data = process_flow(self.raw_graph_data)

    # 初始化图结构
    self.initialize()
```

#### 第四步：执行工作流
```python
async def run_graph_internal(
    graph: Graph,
    flow_id: str,
    *,
    stream: bool = False,
    session_id: str | None = None,
    inputs: list[InputValueRequest] | None = None,
    outputs: list[str] | None = None,
    event_manager: EventManager | None = None,
) -> tuple[list[RunOutputs], str]:
    """
    内部工作流执行函数
    """
    # 1. 准备输入
    inputs = inputs or []
    effective_session_id = session_id or flow_id

    components = []
    inputs_list = []
    types = []

    for input_value_request in inputs:
        components.append(input_value_request.components or [])
        inputs_list.append({INPUT_FIELD_NAME: input_value_request.input_value})
        types.append(input_value_request.type)

    # 2. 运行图
    graph.session_id = effective_session_id
    run_outputs = await graph.arun(
        inputs=inputs_list,
        inputs_components=components,
        types=types,
        outputs=outputs or [],
        stream=stream,
        session_id=effective_session_id,
        fallback_to_env_vars=fallback_to_env_vars,
        event_manager=event_manager,
    )

    return run_outputs, effective_session_id
```

#### 第五步：异步运行（arun）
```python
async def arun(
    self,
    inputs: list[dict[str, str]],
    *,
    inputs_components: list[list[str]] | None = None,
    types: list[InputType | None] | None = None,
    outputs: list[str] | None = None,
    session_id: str | None = None,
    stream: bool = False,
    fallback_to_env_vars: bool = False,
    event_manager: EventManager | None = None,
) -> list[RunOutputs]:
    """
    执行图的主方法
    """
    vertex_outputs = []

    # 标准化输入
    if not isinstance(inputs, list):
        inputs = [inputs]
    elif not inputs:
        inputs = [{}]

    # 对每个输入集合运行一次
    for run_inputs, components, input_type in zip(
        inputs, inputs_components, types, strict=True
    ):
        # 1. 运行单次迭代
        run_outputs = await self._run(
            inputs=run_inputs,
            input_components=components,
            input_type=input_type,
            outputs=outputs or [],
            stream=stream,
            session_id=session_id or "",
            fallback_to_env_vars=fallback_to_env_vars,
            event_manager=event_manager,
        )

        # 2. 收集输出
        run_output_object = RunOutputs(
            inputs=run_inputs,
            outputs=run_outputs
        )
        vertex_outputs.append(run_output_object)

    return vertex_outputs
```

#### 第六步：单次运行（_run）
```python
async def _run(
    self,
    *,
    inputs: dict[str, str],
    input_components: list[str],
    input_type: InputType | None,
    outputs: list[str],
    stream: bool,
    session_id: str,
    fallback_to_env_vars: bool,
    event_manager: EventManager | None = None,
) -> list[ResultData | None]:
    """
    实际执行图的方法
    """
    # 1. 设置输入值到对应的节点
    self._set_inputs(input_components, inputs, input_type)

    # 2. 更新会话 ID
    for vertex_id in self.has_session_id_vertices:
        vertex = self.get_vertex(vertex_id)
        vertex.update_raw_params({"session_id": session_id})

    # 3. 缓存图状态（用于会话管理）
    cache_service = get_chat_service()
    if cache_service and self.flow_id:
        await cache_service.set_cache(self.flow_id, self)

    # 4. 核心执行：处理图中的所有节点
    start_component_id = find_start_component_id(self._is_input_vertices)
    await self.process(
        start_component_id=start_component_id,
        fallback_to_env_vars=fallback_to_env_vars,
        event_manager=event_manager,
    )

    # 5. 收集输出
    vertex_outputs = []
    for vertex in self.vertices:
        if not vertex.built:
            continue

        # 消费异步生成器（流模式）
        if not vertex.result and not stream and hasattr(vertex, "consume_async_generator"):
            await vertex.consume_async_generator()

        # 收集指定的输出节点结果
        if (
            (not outputs and vertex.is_output)
            or (vertex.display_name in outputs or vertex.id in outputs)
        ):
            vertex_outputs.append(vertex.result)

    return vertex_outputs
```

### 3.3 工作流执行的完整数据流

```
前端拖拽构建
    ↓
工作流 JSON 配置 (nodes + edges + viewport)
    ↓
POST /api/v1/flows/{id} 保存到数据库
    ↓
数据库中存储为 Flow.data (JSON 格式)
    ↓
POST /api/v1/run/{flow_id} 请求执行
    ↓
从数据库加载 Flow.data
    ↓
process_tweaks() - 应用参数调整
    ↓
Graph.from_payload() - 从 JSON 构建图对象
    ↓
graph.add_nodes_and_edges() - 构建拓扑结构
    ↓
graph.arun() - 异步执行
    ↓
graph._run() - 单次迭代运行
    ↓
graph.process() - 拓扑排序并执行所有节点
    ↓
收集输出并返回响应
```

---

## 第四部分：关键概念详解

### 4.1 Tweaks（参数微调）

Tweaks 允许在运行时动态修改节点参数，无需保存新的工作流：

```python
# 执行请求示例
POST /api/v1/run/my-flow
{
  "input_value": "Hello",
  "tweaks": {
    "OpenAI-1": {
      "model": "gpt-4",
      "temperature": 0.9
    },
    "ChatInput-1": {
      "input_value": "Overridden input"
    }
  }
}

# 后端会：
# 1. 加载已保存的工作流配置
# 2. 使用 tweaks 覆盖指定节点的参数
# 3. 使用修改后的配置执行
# 4. 不修改数据库中的工作流
```

### 4.2 会话管理（Session）

会话用于维护跨多次请求的状态（如对话历史）：

```python
# 第一次请求
POST /api/v1/run/flow-id
{
  "input_value": "Hello"
  // session_id 不提供，后端生成
}
Response: { "session_id": "abc-123", "outputs": [...] }

# 第二次请求，使用相同的 session_id
POST /api/v1/run/flow-id
{
  "input_value": "Follow up",
  "session_id": "abc-123"  // 重用会话
}
// 流的组件可以访问之前的状态
```

### 4.3 流媒体（Streaming）

当 `stream=true` 时，执行过程中的事件实时发送给客户端：

```python
# 流媒体响应
POST /api/v1/run/flow-id?stream=true
Response:
SSE (Server-Sent Events)
data: {"type":"token","data":"Hello"}
data: {"type":"token","data":" "}
data: {"type":"token","data":"world"}
data: {"type":"end","data":{"result":"Hello world"}}
```

---

## 总结

### 前端到后端的工作流传输流程：

1. **构建阶段**（前端）
   - 用户拖拽组件到画布
   - 连接组件形成工作流
   - 数据存储在 Zustand stores 中

2. **保存阶段**（前端 → 后端）
   - 提取当前的 nodes、edges、viewport
   - 打包为 `{ id, name, data: { nodes, edges, viewport }, ... }`
   - PATCH /api/v1/flows/{id} 发送到后端

3. **存储阶段**（后端）
   - 解析请求，验证权限
   - 保存到数据库中的 Flow 表，data 字段存储 JSON

4. **执行阶段**（后端）
   - POST /api/v1/run/{flow_id} 请求
   - 从数据库加载 Flow.data
   - 应用 tweaks（如果有）
   - Graph.from_payload() 从 JSON 构建图对象
   - 执行每个节点并收集输出

### 关键代码位置对应表

| 功能 | 前端位置 | 后端位置 |
|------|--------|---------|
| 工作流保存 | `hooks/flows/use-save-flow.ts` | `api/v1/flows.py#update_flow()` |
| 工作流运行 | N/A（API 调用） | `api/v1/endpoints.py#simplified_run_flow()` |
| 图构建 | N/A | `lfx/graph/graph/base.py#from_payload()` |
| 图执行 | N/A | `lfx/graph/graph/base.py#arun()/_run()` |
| 数据模型 | `types/flow.ts` | `services/database/models/flow/model.py` |

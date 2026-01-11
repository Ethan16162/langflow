# async def test():
#     llm = ChatOpenAI(
#         model="glm-4.7",
#         openai_api_key="71dd92e623954e818289ca9edda5f454.IFn9uiyvXmkhar5Q",  # 你的 Google API Key
#         temperature=1.0,
#         base_url="https://open.bigmodel.cn/api/paas/v4/"
#     )

#     resp = await llm.ainvoke([HumanMessage(content="Hello")])
#     print(resp.content)

# asyncio.run(test())

import json
from pathlib import Path

# ====================== TEST： 直接读取答案
# 读取并解析 JSON
json_file = Path(
    "/mnt/d/HonorStoreDownload/WSL/code/langflow/langflow/src/backend/base/langflow/agent_workflow/answer.json"
)


# 在线程池中执行阻塞操作
def _load_json():
    with json_file.open("r", encoding="utf-8") as f:
        return json.load(f)


data = _load_json()
import pdb

pdb.set_trace()
a = 1
# Extract JSON from response (handle markdown code blocks)

# from zai import ZhipuAiClient

# client = ZhipuAiClient(api_key="71dd92e623954e818289ca9edda5f454.IFn9uiyvXmkhar5Q")  # 请填写您自己的 API Key

# response = client.chat.completions.create(
#     model="glm-4.7",
#     messages=[
#         {"role": "user", "content": "作为一名营销专家，请为我的产品创作一个吸引人的口号"},
#         {"role": "assistant", "content": "当然，要创作一个吸引人的口号，请告诉我一些关于您产品的信息"},
#         {"role": "user", "content": "智谱AI开放平台"}
#     ],
#     thinking={
#         "type": "enabled",    # 启用深度思考模式
#     },
#     max_tokens=65536,          # 最大输出 tokens
#     temperature=1.0           # 控制输出的随机性
# )

# # 获取完整回复
# print(response.choices[0].message)

import json
import re
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, MultilineInput
from lfx.schema.message import Message
from lfx.template.field.base import Output


class EditComponent(Component):
    display_name = "Edit Component (text-only)"
    description = "Extract and return only the `text` field for easier editing (hides file_path, id, etc.)."
    icon = "code"
    name = "EditComponentTextOnly"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Input Value",
            info="Raw component output (can be JSON string or dict)",
            value="",
            tool_mode=True,
        ),
        MultilineInput(
            name="editable_text",
            display_name="✏️ Edit Output (gys)",
            value="",
            required=False,
            advanced=False,
        ),
    ]

    outputs = [
        Output(
            display_name="Parsed Text",
            name="parsed_text",
            info="Only the extracted/edited text content.",
            method="build_output",
        ),
    ]

    def _extract_text_from_obj(self, value: Any) -> str:
        """Robust extraction:
         - If dict: collect nested 'text' entries (deep search).
         - If list: collect texts from each element.
         - If string:
            * try json.loads (single JSON)
            * try to decode multiple concatenated JSON objects via JSONDecoder().raw_decode
            * regex fallback for "text": "..."
            * otherwise return raw string
        Returns a joined string (multiple texts separated by separators).
        """
        if value is None:
            return ""

        # --- dict handling (deep collect)
        if isinstance(value, dict):
            collected: list[str] = []

            def collect_from_dict(d: dict):
                out = []
                for k, v in d.items():
                    if k == "text" and isinstance(v, str):
                        out.append(v.strip())
                    elif isinstance(v, dict):
                        out.extend(collect_from_dict(v))
                    elif isinstance(v, list):
                        out.extend(collect_from_list(v))
                    elif isinstance(v, str):
                        # keep other strings as fallback
                        out.append(v.strip())
                return out

            def collect_from_list(lst: list):
                out = []
                for it in lst:
                    if isinstance(it, dict):
                        out.extend(collect_from_dict(it))
                    elif isinstance(it, list):
                        out.extend(collect_from_list(it))
                    elif isinstance(it, str):
                        out.append(it.strip())
                return out

            collected = collect_from_dict(value)
            collected = [t for t in collected if t]
            return "\n\n".join(collected).strip()

        # --- list handling
        if isinstance(value, list):
            texts: list[str] = []
            for it in value:
                texts.append(self._extract_text_from_obj(it))
            texts = [t for t in texts if t]
            return "\n\n".join(texts).strip()

        # --- string handling (most complex)
        if isinstance(value, str):
            s = value.strip()

            # 1) try single JSON
            try:
                parsed = json.loads(s)
                return self._extract_text_from_obj(parsed)
            except Exception:
                pass

            # 2) try multiple concatenated JSON objects using raw_decode
            decoder = json.JSONDecoder()
            idx = 0
            n = len(s)
            parsed_objs: list[Any] = []
            while idx < n:
                # skip whitespace
                while idx < n and s[idx].isspace():
                    idx += 1
                if idx >= n:
                    break
                try:
                    obj, end = decoder.raw_decode(s, idx)
                    parsed_objs.append(obj)
                    idx = end
                except Exception:
                    # can't parse further as JSON -> break to fallback
                    break

            if parsed_objs:
                texts: list[str] = []
                for obj in parsed_objs:
                    texts.append(self._extract_text_from_obj(obj))
                texts = [t for t in texts if t]
                if texts:
                    # 用分隔符把不同对象的 text 分开，便于阅读/编辑
                    return "\n\n---\n\n".join(texts).strip()

            # 3) fallback: regex find all "text": "..."
            matches = re.findall(r"\"text\"\s*:\s*\"([\s\S]*?)\"", s)
            if matches:
                cleaned = [m.encode("utf-8").decode("unicode_escape").strip() for m in matches]
                return "\n\n".join(cleaned).strip()

            # 4) 最终回退：原始字符串
            return s

        # any other type -> str
        return str(value)

    def build_output(self) -> Message:
        # 优先使用用户在 editable_text 里做的修改
        user_edited = getattr(self, "editable_text", None)
        if user_edited:
            out_text = user_edited.strip()
        else:
            raw = getattr(self, "input_value", "")
            out_text = self._extract_text_from_obj(raw)

        if not isinstance(out_text, str):
            out_text = str(out_text)

        message = Message(text=out_text)
        self.status = message
        return message

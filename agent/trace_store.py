"""
轻量链路追踪器 - 记录 Agent 工具调用过程
不依赖 hello_agents 重型框架，直接原生实现
"""
import time
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime


@dataclass
class ToolCallRecord:
    tool_name: str
    input_str: str
    output_str: str
    duration_ms: int
    success: bool
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))


@dataclass
class TraceRecord:
    session_id: str
    question: str
    agent_mode: str          # "react" 或 "reflection"
    tool_calls: List[ToolCallRecord] = field(default_factory=list)
    total_duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    start_time: float = field(default_factory=time.time)

    def add_tool_call(self, name: str, inp: str, out: str, duration_ms: int, success: bool = True):
        self.tool_calls.append(ToolCallRecord(
            tool_name=name,
            input_str=str(inp)[:200],   # 截断，避免日志过大
            output_str=str(out)[:300],
            duration_ms=duration_ms,
            success=success,
        ))

    def finish(self, input_tokens: int = 0, output_tokens: int = 0):
        self.total_duration_ms = int((time.time() - self.start_time) * 1000)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("start_time", None)
        return d

    @property
    def tool_count(self) -> int:
        return len(self.tool_calls)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def format_sidebar(self) -> str:
        """格式化为 Streamlit 侧边栏展示文本"""
        lines = []
        if self.tool_calls:
            lines.append("🔍 **本轮工具调用**")
            for tc in self.tool_calls:
                icon = "✅" if tc.success else "❌"
                lines.append(f"{icon} `{tc.tool_name}` — {tc.duration_ms}ms")
        else:
            lines.append("🔍 本轮无工具调用")
        return "\n".join(lines)


class TraceStore:
    """当前会话的 Trace 存储（内存级，Streamlit 通过 session_state 持久化）"""

    def __init__(self):
        self._current: Optional[TraceRecord] = None
        self._history: List[TraceRecord] = []

    def start(self, session_id: str, question: str, agent_mode: str = "react") -> TraceRecord:
        self._current = TraceRecord(
            session_id=session_id,
            question=question,
            agent_mode=agent_mode,
        )
        return self._current

    @property
    def current(self) -> Optional[TraceRecord]:
        return self._current

    def finish_current(self, input_tokens: int = 0, output_tokens: int = 0):
        if self._current:
            self._current.finish(input_tokens, output_tokens)
            self._history.append(self._current)
            self._current = None

    @property
    def last(self) -> Optional[TraceRecord]:
        return self._history[-1] if self._history else None

    def all_records(self) -> List[TraceRecord]:
        return list(self._history)

    def total_tokens_used(self) -> int:
        return sum(r.total_tokens for r in self._history)


# 全局单例（在 app.py 和 agent 之间共享时通过 session_state 注入）
_global_trace_store = TraceStore()


def get_trace_store() -> TraceStore:
    return _global_trace_store

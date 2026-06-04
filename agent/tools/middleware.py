import time
from typing import Callable
from utils.prompt_loader import load_system_prompts, load_report_prompts
from langchain.agents import AgentState
from langchain.agents.middleware import wrap_tool_call, before_model, dynamic_prompt, ModelRequest
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command
from utils.logger_handler import logger
from agent.trace_store import get_trace_store


# 报告触发关键词（检测到时标记 report 上下文）
REPORT_TRIGGER_KEYWORDS = ["报告", "诊断", "分析报告", "综合评估", "activate_report_mode"]


@wrap_tool_call
def monitor_tool(
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    """工具调用监控：记录日志 + 耗时统计 + Trace 写入"""
    tool_name = request.tool_call['name']
    tool_args = request.tool_call['args']

    logger.info(f"[tool monitor] 执行工具：{tool_name}")
    logger.info(f"[tool monitor] 传入参数：{tool_args}")

    t0 = time.time()
    try:
        result = handler(request)
        duration_ms = int((time.time() - t0) * 1000)
        logger.info(f"[tool monitor] 工具 {tool_name} 调用成功，耗时 {duration_ms}ms")

        # 写入 Trace
        trace = get_trace_store().current
        if trace:
            out_str = result.content if hasattr(result, "content") else str(result)
            trace.add_tool_call(
                name=tool_name,
                inp=str(tool_args),
                out=out_str,
                duration_ms=duration_ms,
                success=True,
            )

        # 检测报告模式触发
        if tool_name == "activate_report_mode":
            request.runtime.context["report"] = True

        return result

    except Exception as e:
        duration_ms = int((time.time() - t0) * 1000)
        logger.error(f"[tool monitor] 工具 {tool_name} 调用失败，原因：{str(e)}")

        # 写入失败 Trace
        trace = get_trace_store().current
        if trace:
            trace.add_tool_call(
                name=tool_name,
                inp=str(tool_args),
                out=f"ERROR: {str(e)}",
                duration_ms=duration_ms,
                success=False,
            )
        # 改为回传自然语言，触发自我纠错
        return ToolMessage(
            content=f"Action Failed: 工具执行失败。错误原因: {str(e)}。请检查你的参数类型和必填项，然后重新思考并调用。",
            tool_call_id=request.tool_call["id"],
            name=tool_name
        )


@before_model
def log_before_model(
        state: AgentState,
        runtime: Runtime,
):
    """模型调用前日志"""
    logger.info(f"[log_before_model] 即将调用模型，带有 {len(state['messages'])} 条消息。")
    last_msg = state['messages'][-1]
    logger.debug(f"[log_before_model] {type(last_msg).__name__} | {str(last_msg.content)[:100].strip()}")
    return None


@dynamic_prompt
def report_prompt_switch(request: ModelRequest):
    """动态提示词切换：普通问答 / 报告生成"""
    is_report = request.runtime.context.get("report", False)
    if is_report:
        return load_report_prompts()
    return load_system_prompts()

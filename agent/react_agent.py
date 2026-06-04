import uuid
from typing import List, Dict
from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools.agent_tools import (
    rag_query, get_realtime_traffic,
    get_road_status, get_current_time, activate_report_mode
)
from agent.tools.sql_tool import analyze_historical_traffic_sql
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch
from agent.trace_store import get_trace_store
from utils.logger_handler import logger

# 报告模式触发关键词
REPORT_KEYWORDS = ["报告", "诊断", "综合分析", "分析报告", "生成报告"]

_ALL_TOOLS = [
    rag_query,
    get_realtime_traffic,
    analyze_historical_traffic_sql,
    get_road_status,
    get_current_time,
    activate_report_mode,
]


class ReactAgent:
    def __init__(self):
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompts(),
            tools=_ALL_TOOLS,
            middleware=[monitor_tool, log_before_model, report_prompt_switch],
        )

    def _is_report_request(self, query: str) -> bool:
        """判断用户是否在请求生成报告"""
        return any(kw in query for kw in REPORT_KEYWORDS)

    def execute_stream(self, query: str, session_id: str = None, history_messages: List[Dict] = None):
        """
        流式执行 Agent，同时记录 Trace
        Yields: str 文本片段
        """
        if not session_id:
            session_id = str(uuid.uuid4())[:8]

        # 判断 Agent 模式
        agent_mode = "reflection" if self._is_report_request(query) else "react"

        # 启动 Trace
        trace_store = get_trace_store()
        trace = trace_store.start(
            session_id=session_id,
            question=query,
            agent_mode=agent_mode,
        )
        logger.info(f"[ReactAgent] 开始执行，模式={agent_mode}，session={session_id}")

        if history_messages is not None:
            input_dict = {"messages": history_messages}
        else:
            input_dict = {
                "messages": [{"role": "user", "content": query}]
            }

        try:
            final_state = None
            if agent_mode == "react":
                # 普通问答模式：直接推流
                for chunk in self.agent.stream(
                    input_dict,
                    stream_mode="values",
                    context={"report": False},
                ):
                    latest_message = chunk["messages"][-1]
                    # 只推送 AI 回复（过滤掉 tool_calls 等空内容）
                    if latest_message.type == "ai" and latest_message.content and not latest_message.tool_calls:
                        yield latest_message.content.strip() + "\n"
            else:
                # Reflection 报告模式：挂起推流，组装上下文后丢给状态机
                yield "⏳ **[报告模式启动]** 正在自主调度工具收集交通数据...\n"
                
                for chunk in self.agent.stream(
                    input_dict,
                    stream_mode="values",
                    context={"report": True},
                ):
                    final_state = chunk
                
                yield "✨ 数据收集完毕，后台挂起 Reflection 反思状态机进行闭门审查（Draft -> Review -> Refine），请稍候...\n\n"
                
                # 从 final_state 中提取所有的 Tool 返回结果作为 Context Data
                context_data = ""
                for msg in final_state["messages"]:
                    if msg.type == "tool":
                        context_data += f"[Tool {msg.name} 返回数据]: {msg.content}\n"
                        
                # 显式拉起 Reflection 状态机
                from agent.reflection_wrapper import TrafficReportReflector
                reflector = TrafficReportReflector(max_rounds=1) # 1次迭代足够
                final_report, logs = reflector.generate(context_data, query)
                
                # 推送最终生成的完美报告
                yield final_report + "\n"

        except Exception as e:
            logger.error(f"[ReactAgent] 执行发生致命错误: {e}")
            yield f"\n\n**系统错误**: {str(e)}\n"
        finally:
            # 结束 Trace
            trace_store.finish_current(input_tokens=0, output_tokens=0)
            logger.info(
                f"[ReactAgent] 执行完成，工具调用 {trace.tool_count} 次，"
                f"总耗时 {trace.total_duration_ms}ms"
            )


if __name__ == '__main__':
    agent = ReactAgent()
    for chunk in agent.execute_stream("帮我生成中山路的交通诊断报告"):
        print(chunk, end="", flush=True)

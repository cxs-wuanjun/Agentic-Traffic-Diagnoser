"""
TransAI 交通智能分析助手
Streamlit 主入口：流式对话 + 侧边栏追踪 + 知识库文档上传
"""
import os
import time
import tempfile
import uuid

import streamlit as st
from agent.react_agent import ReactAgent
from agent.trace_store import get_trace_store
from rag.rag_service import RagSummarizeService
from rag.vector_store import VectorStoreService
from agent.history_manager import HistoryManager

# ──────────────────────── 页面基础配置 ────────────────────────
st.set_page_config(
    page_title="TransAI 交通智能分析助手",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────── 初始化状态 ────────────────────────
if "agent" not in st.session_state:

    st.session_state["agent"] = ReactAgent()
    st.session_state["trace_store"] = get_trace_store()
    st.session_state["vs"] = VectorStoreService()
    # 启动时加载初始知识库
    st.session_state["vs"].load_document()
    st.session_state["kb_loaded"] = True

if "history_manager" not in st.session_state:
    # 核心记忆管理器，默认保留最近 5 轮对话
    st.session_state["history_manager"] = HistoryManager(max_rounds=5)

if "messages" not in st.session_state:
    # UI 展示用的完整消息列表（不截断）
    st.session_state["messages"] = []

if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())[:8]

if "last_trace" not in st.session_state:
    st.session_state["last_trace"] = None

# ──────────────────────── 侧边栏 ────────────────────────
with st.sidebar:
    st.markdown("## 🚦 TransAI")
    st.markdown("**交通智能分析助手**")
    st.divider()

    # ── Agent 状态面板 ──
    st.markdown("### ⚡ 运行状态")
    trace_store = st.session_state.get("trace_store")
    last_trace = st.session_state.get("last_trace")

    if last_trace:
        # Agent 模式标签
        mode_label = "📋 报告生成" if last_trace.agent_mode == "reflection" else "🤖 ReAct 问答"
        st.info(f"**Agent 模式**：{mode_label}")

        col1, col2 = st.columns(2)
        col1.metric("⏱️ 响应时间", f"{last_trace.total_duration_ms}ms")
        col2.metric("🔧 工具调用", f"{last_trace.tool_count} 次")

        if last_trace.tool_calls:
            st.markdown("**🔍 本轮工具调用**")
            for tc in last_trace.tool_calls:
                icon = "✅" if tc.success else "❌"
                st.markdown(
                    f"{icon} `{tc.tool_name}` — **{tc.duration_ms}ms**",
                    help=f"输入: {tc.input_str[:100]}\n输出: {tc.output_str[:200]}"
                )
    else:
        st.caption("等待首次查询...")

    st.divider()

    # ── 知识库文档上传 ──
    st.markdown("### 📚 知识库管理")
    st.caption("支持导入 .txt / .pdf 交通相关文档，导入后可直接参与 RAG 问答")

    uploaded_file = st.file_uploader(
        "上传文档到知识库",
        type=["txt", "pdf"],
        help="文档内容将被向量化存入知识库，支持重复上传检测（相同文件自动跳过）",
        key="kb_uploader"
    )

    if uploaded_file is not None:
        if st.button("📥 导入到知识库", use_container_width=True):
            with st.spinner("正在向量化处理文档..."):
                try:
                    # 保存到临时文件
                    suffix = ".pdf" if uploaded_file.name.endswith(".pdf") else ".txt"
                    with tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=suffix,
                        mode="wb"
                    ) as tmp:
                        tmp.write(uploaded_file.read())
                        tmp_path = tmp.name

                    vs: VectorStoreService = st.session_state["vs"]
                    success, msg = vs.add_single_document(tmp_path)

                    os.unlink(tmp_path)  # 清理临时文件

                    if success:
                        st.success(msg)
                    else:
                        st.warning(msg)
                except Exception as e:
                    st.error(f"导入失败: {str(e)}")

    st.divider()

    # ── 使用提示 ──
    st.markdown("### 💡 使用提示")
    st.markdown("""
- 📍 路口查询：输入路口名称或编号
- 🛣️ 路段状态：输入路段名称查询拥堵
- 📋 生成报告：包含「报告」「诊断」关键词
- 📚 知识问答：信号控制、拥堵成因等
    """)

    # ── 清空对话 ──
    if st.button("🗑️ 清空对话", use_container_width=True):
        st.session_state["messages"] = []
        st.session_state["history_manager"].clear()
        st.session_state["last_trace"] = None
        st.session_state["session_id"] = str(uuid.uuid4())[:8]
        st.rerun()

# ──────────────────────── 主聊天区域 ────────────────────────
st.markdown(
    "<h2 style='text-align:center; margin-bottom:0'>🚦 TransAI 交通智能分析助手</h2>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align:center; color:gray; margin-top:4px'>基于 LangChain ReAct Agent · RAG 知识库 · Reflection 报告生成</p>",
    unsafe_allow_html=True,
)
st.divider()

# ── 示例问题快捷按钮 ──
if not st.session_state["messages"]:
    st.markdown("#### 💬 快速提问")
    example_cols = st.columns(3)
    examples = [
        ("🚦 路口查询", "查询A001路口当前交通状态"),
        ("🛣️ 路段状态", "中山路现在堵不堵？"),
        ("📋 生成报告", "帮我生成A002路口的交通诊断报告"),
        ("⚠️ 事故查询", "查一下中山路今天发生了哪些事故"),
        ("📚 专业知识", "拥堵等级是怎么划分的？"),
        ("🕐 当前时间", "现在是什么时间？"),
    ]
    for i, (label, query) in enumerate(examples):
        col = example_cols[i % 3]
        if col.button(label, key=f"example_{i}", use_container_width=True, help=query):
            st.session_state["pending_query"] = query
            st.rerun()
    st.divider()

# ── 历史消息展示 ──
for message in st.session_state["messages"]:
    st.chat_message(message["role"]).write(message["content"])

# ── 处理示例问题点击 ──
pending = st.session_state.pop("pending_query", None)

# ── 用户输入 ──
prompt = st.chat_input("请输入您的问题，例如：查询中山路路口当前拥堵状态")

# 合并 pending 和手动输入
active_query = pending or prompt

if active_query:
    # 显示用户消息
    st.chat_message("user").write(active_query)
    st.session_state["messages"].append({"role": "user", "content": active_query})
    
    # 记录到记忆管理器
    hm: HistoryManager = st.session_state["history_manager"]
    hm.append("user", active_query)

    # 更新 trace_store 的 session_id（保持会话连贯）
    trace_store = st.session_state["trace_store"]

    response_chunks = []
    with st.spinner("🧠 AI 分析中..."):
        agent: ReactAgent = st.session_state["agent"]
        
        # 将携带历史上下文的消息列表传给 Agent
        context_messages = hm.get_messages()
        
        res_stream = agent.execute_stream(
            query=active_query,
            session_id=st.session_state["session_id"],
            history_messages=context_messages
        )

        def capture(generator, cache_list):
            for chunk in generator:
                cache_list.append(chunk)
                for char in chunk:
                    time.sleep(0.005)   # 流式打字效果（稍快一些）
                    yield char

        st.chat_message("assistant").write_stream(capture(res_stream, response_chunks))

    # 保存回复
    full_response = "".join(response_chunks)
    st.session_state["messages"].append({"role": "assistant", "content": full_response})
    hm.append("assistant", full_response)

    # 更新最新 Trace 到 session_state（侧边栏展示）
    last = trace_store.last
    if last:
        st.session_state["last_trace"] = last

    st.rerun()

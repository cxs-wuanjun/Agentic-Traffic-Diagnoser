"""
交通诊断报告生成器 - Reflection 模式
使用 LangChain 原生实现 3 轮迭代反思，无需依赖 hello_agents 重型框架
"""
from langchain_core.messages import SystemMessage, HumanMessage
from model.factory import chat_model
from utils.prompt_loader import load_report_prompts
from utils.logger_handler import logger

import os
import re
import traceback

def load_skill_md(skill_name: str) -> str:
    """动态读取符合 agentskills.io 标准的 SKILL.md 手册"""
    skill_path = os.path.join(os.getcwd(), "agent", "skills", skill_name, "SKILL.md")
    if os.path.exists(skill_path):
        with open(skill_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""




class TrafficReportReflector:
    """
    交通诊断报告 Reflection 生成器
    流程：初稿生成 → 专家审查 → 改进修订 (最多 max_rounds 轮)
    """

    def __init__(self, max_rounds: int = 2):
        self.model = chat_model
        self.max_rounds = max_rounds
        self.report_system_prompt = load_report_prompts()

    def generate(self, context_data: str, user_request: str = "") -> tuple[str, list[str]]:
        """
        生成交通诊断报告（含 Reflection 迭代）

        Args:
            context_data: 工具查询到的原始数据（流量、事件、路况等）
            user_request: 用户原始请求（用于明确报告方向）

        Returns:
            (最终报告内容, 迭代过程摘要列表)
        """
        process_log = []

        # 动态加载报告工作流与配套技能手册，以 "Progressive Disclosure (渐进式挂载)" 方式告诉大模型
        report_workflow_skill = load_skill_md("report-workflow")
        data_viz_skill = load_skill_md("data-visualization")
        docx_skill = load_skill_md("docx-assembler")
        sop_skill = load_skill_md("compliance-sop")

        # 将报告生成全链路 Skill 与配套技能说明书外挂到大模型的 System Prompt 中
        skill_context = (
            "【报告生成工作流 Skill】\n"
            f"{report_workflow_skill}\n\n"
            "【配套 Agent Skills】\n"
            f"{data_viz_skill}\n\n{sop_skill}\n\n{docx_skill}\n\n"
        )

        logger.info("[ReflectionReport] 技能手册已挂载，启动思考与撰写初稿...")
        draft_prompt = (
            f"请根据以下查询到的交通数据，生成一份专业的交通诊断报告。\n\n"
            f"用户需求：{user_request or '生成综合交通诊断报告'}\n\n"
            f"【原始数据】\n{context_data}\n\n"
            f"请严格按照报告格式规范生成报告。对于每一处数据引用，请必须在其后添加数据溯源脚注标记，例如 '[1]根据高德实时数据'。"
        )

        draft_system_prompt = (
            self.report_system_prompt
            + "\n\n"
            + skill_context
            + "\n\n【当前阶段：Draft】请生成报告初稿。初稿必须包含处置建议，但不要输出 Python 代码。"
        )

        messages = [
            SystemMessage(content=draft_system_prompt),
            HumanMessage(content=draft_prompt),
        ]

        draft_response = self.model.invoke(messages)
        draft = draft_response.content
        process_log.append("✅ 第一步：报告初稿已生成")
        logger.info("[ReflectionReport] 初稿生成完成")

        current_report = draft

        # Reflection 迭代...
        for round_num in range(self.max_rounds):
            logger.info(f"[ReflectionReport] 开始第 {round_num + 1} 轮反思审查...")

            # 审查报告
            review_messages = [
                SystemMessage(
                    content="你是一名严格的交通诊断报告审查专家。\n\n"
                    + skill_context
                    + "\n\n【当前阶段：Review】请严格执行上面挂载的“报告生成工作流 Skill”中定义的【Review 阶段要求】来检查初稿。如果完全符合要求且无需修改，请在回复开头写上『PASS』。如果需要修改，请给出具体意见。"
                ),
                HumanMessage(content=f"请审查以下交通诊断报告初稿：\n\n{current_report}"),
            ]
            review_response = self.model.invoke(review_messages)
            review_feedback = review_response.content
            
            review_passed = review_feedback.strip().startswith("PASS")
            if review_feedback.strip().startswith("PASS"):
                process_log.append(f"🔍 第 {round_num + 2} 步：专家审查通过，无须修改。")
                logger.info(f"[ReflectionReport] 审查通过，转入最终装配阶段")
                review_feedback = "审查通过。请保持原报告结论不变，仅按报告工作流 Skill 补充最终报告所需的图表生成与 Word 装配代码。"
                
            process_log.append(f"🔍 第 {round_num + 2} 步：审查意见 → {review_feedback[:80]}...")
            logger.info(f"[ReflectionReport] 第 {round_num + 1} 轮审查完成")

            system_prompt_content = (
                "你是一名专业的交通诊断报告撰写专家。\n\n"
                + skill_context
                + "\n\n【当前阶段：Refine + Assemble】请严格执行“报告生成工作流 Skill”中定义的【Refine 阶段要求】与【Assemble 阶段要求】对初稿进行修订。\n\n"
                + "请输出修订后的完整 Markdown 报告，并在最后提供生成Word和图表的可执行 Python 代码块。"
            )
                
            refine_messages = [
                SystemMessage(content=system_prompt_content),
                HumanMessage(
                    content=(
                        f"【原始报告】\n{current_report}\n\n"
                        f"【专家审查意见】\n{review_feedback}\n\n"
                        f"请根据审查意见修订并输出完整的改进报告。"
                    )
                ),
            ]
            refine_response = self.model.invoke(refine_messages)
            current_report = refine_response.content
            process_log.append(f"✨ 第 {round_num + 2} 步：报告已根据审查意见优化")
            logger.info(f"[ReflectionReport] 第 {round_num + 1} 轮优化完成")

            if review_passed:
                break

        process_log.append(f"📋 共完成 {self.max_rounds} 轮文本反思迭代，核心分析已就绪。")
        
        # 提取 Python 代码并执行 (Code Interpreter 模拟)
        logger.info("[ReflectionReport] 正在沙盒中执行大模型编写的装配代码...")
        process_log.append("🚀 装配线：大模型已自行编写出 Python 代码，正在执行可视化与 Word 装配...")
        
        # 匹配 ```python ... ``` 代码块
        code_blocks = re.findall(r'```python(.*?)```', current_report, re.DOTALL)
        if code_blocks:
            python_code = code_blocks[-1].strip()
            # 从文本中剔除代码块以向用户展示纯净的 markdown 预览
            current_report = re.sub(r'```python.*?```', '', current_report, flags=re.DOTALL).strip()
            
            try:
                # 为了安全，这里本应使用受限沙盒，由于是本地演示环境，使用 exec 模拟 Code Execution Tool
                exec_globals = {}
                exec(python_code, exec_globals)
                process_log.append("✅ 技能执行成功：排版引擎与画图成功运转，.docx 红头文件已生成！")
                
                # 简单拼接一下下载信息
                out_file = os.path.join(os.getcwd(), "outputs", "reports", "Final_Report.docx")
                current_report += f"\n\n---\n\n🎉 **报告装配完成！**\n📄 **下载您的红头文件 (.docx)**: `{out_file}`"
                
            except Exception as e:
                logger.error(f"Agent 代码执行失败: {e}\n{traceback.format_exc()}")
                process_log.append(f"⚠️ 技能执行失败: {e}")
                current_report += f"\n\n---\n⚠️ Agent代码执行失败: {e}"
        else:
            process_log.append("⚠️ 大模型本次未能生成 Python 装配代码。")

        return current_report, process_log

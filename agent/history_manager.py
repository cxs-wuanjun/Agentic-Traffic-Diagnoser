import os
from typing import List, Dict, Any
from utils.logger_handler import logger

# 获取压缩模型
def get_compress_model():
    from model.factory import chat_model
    # 按照需求：如果有小模型APIKey，则用小模型（例如 qwen-turbo），否则用大模型兜底
    small_api_key = os.environ.get("SMALL_MODEL_API_KEY", "")
    if small_api_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="qwen-turbo", # 预设的小模型
            temperature=0.1,
            api_key=small_api_key,
            base_url=os.environ.get("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        )
    return chat_model

class HistoryManager:
    """轻量级历史管理器（支持动态摘要压缩）"""
    def __init__(self, max_rounds: int = 4, enable_compression: bool = True):
        """
        :param max_rounds: 最大保留的完整明细对话轮数
        :param enable_compression: 是否开启 LLM 动态摘要压缩
        """
        self._messages: List[Dict[str, Any]] = []
        self.max_rounds = max_rounds
        self.enable_compression = enable_compression
        self.summary_context = "" # 保存过去生成的摘要

    def append(self, role: str, content: str):
        """追加一条新消息"""
        self._messages.append({"role": role, "content": content})
        self._trim_history()

    def get_messages(self) -> List[Dict[str, Any]]:
        """获取当前截断后的历史记录，如果开启压缩，会将摘要作为系统消息前置"""
        msgs = []
        if self.summary_context:
            msgs.append({"role": "system", "content": f"之前的对话摘要（请谨记这些背景信息）：\n{self.summary_context}"})
        msgs.extend(self._messages)
        return msgs

    def clear(self):
        """清空历史"""
        self._messages.clear()
        self.summary_context = ""

    def _trim_history(self):
        """滑动窗口压缩核心逻辑"""
        user_msg_count = sum(1 for msg in self._messages if msg.get("role") == "user")
        
        # 如果超出设定的最大轮数，则截断
        if user_msg_count > self.max_rounds:
            target_user_idx = user_msg_count - self.max_rounds
            current_user_idx = 0
            cut_index = 0
            
            for i, msg in enumerate(self._messages):
                if msg.get("role") == "user":
                    current_user_idx += 1
                    if current_user_idx > target_user_idx:
                        cut_index = i
                        break
            
            if cut_index > 0:
                outdated_msgs = self._messages[:cut_index]
                self._messages = self._messages[cut_index:]
                
                # 动态压缩逻辑
                if self.enable_compression:
                    self._compress_outdated(outdated_msgs)

    def _compress_outdated(self, outdated_msgs: List[Dict[str, Any]]):
        """调用 LLM 压缩丢弃的历史记录"""
        try:
            model = get_compress_model()
            
            text_to_compress = ""
            for m in outdated_msgs:
                text_to_compress += f"{m['role'].upper()}: {m['content'][:200]}\n"
                
            prompt = f"""请仔细阅读以下对话记录，并将其压缩提炼为一个简短的摘要。
之前已有的摘要（如果有）：{self.summary_context}
被截断的旧历史对话：
{text_to_compress}
请合并这些信息，保留其中的关键实体（如地名、时间、核心需求、得出的核心结论），丢弃无效闲聊。
输出最新的连贯摘要（直接输出内容，不要任何客套话）："""
            
            resp = model.invoke(prompt)
            self.summary_context = resp.content.strip()
            logger.info("[HistoryManager] 触发动态压缩成功！")
        except Exception as e:
            logger.error(f"[HistoryManager] 历史记录动态压缩失败: {e}")

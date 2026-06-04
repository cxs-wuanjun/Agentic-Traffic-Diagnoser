from langchain_chroma import Chroma
from langchain_core.documents import Document
from utils.config_handler import chroma_conf

from model.factory import embed_model

from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.path_tool import get_abs_path
from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from utils.logger_handler import logger

import os


class VectorStoreService:
    def __init__(self):
        self.vector_store = Chroma(
            collection_name=chroma_conf["collection_name"],
            embedding_function=embed_model,
            persist_directory=chroma_conf["persist_directory"],
        )

        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separators"],
            length_function=len,
        )

    def get_retriever(self, search_kwargs=None):
        if search_kwargs is None:
            search_kwargs = {"k": chroma_conf["k"]}
        return self.vector_store.as_retriever(search_kwargs=search_kwargs)

    def load_document(self):
        """
        从数据文件夹内读取数据文件，转为向量存入向量库
        要计算文件的MD5做去重
        :return: None
        """

        def check_md5_hex(md5_for_check: str):
            if not os.path.exists(get_abs_path(chroma_conf["md5_hex_store"])):
                # 创建文件
                open(get_abs_path(chroma_conf["md5_hex_store"]), "w", encoding="utf-8").close()
                return False            # md5 没处理过

            with open(get_abs_path(chroma_conf["md5_hex_store"]), "r", encoding="utf-8") as f:
                for line in f.readlines():
                    line = line.strip()
                    if line == md5_for_check:
                        return True     # md5 处理过

                return False            # md5 没处理过

        def save_md5_hex(md5_for_check: str):
            with open(get_abs_path(chroma_conf["md5_hex_store"]), "a", encoding="utf-8") as f:
                f.write(md5_for_check + "\n")

        def get_file_documents(read_path: str):
            if read_path.endswith("txt"):
                return txt_loader(read_path)

            if read_path.endswith("pdf"):
                return pdf_loader(read_path)

            return []

        allowed_files_path: list[str] = listdir_with_allowed_type(
            get_abs_path(chroma_conf["data_path"]),
            tuple(chroma_conf["allow_knowledge_file_type"]),
        )

        for path in allowed_files_path:
            # 获取文件的MD5
            md5_hex = get_file_md5_hex(path)

            if check_md5_hex(md5_hex):
                logger.info(f"[加载知识库]{path}内容已经存在知识库内，跳过")
                continue

            try:
                documents: list[Document] = get_file_documents(path)

                if not documents:
                    logger.warning(f"[加载知识库]{path}内没有有效文本内容，跳过")
                    continue

                split_document: list[Document] = self.spliter.split_documents(documents)

                if not split_document:
                    logger.warning(f"[加载知识库]{path}分片后没有有效文本内容，跳过")
                    continue

                # 将内容存入向量库
                self.vector_store.add_documents(split_document)

                # 记录这个已经处理好的文件的md5，避免下次重复加载
                save_md5_hex(md5_hex)

                logger.info(f"[加载知识库]{path} 内容加载成功")
            except Exception as e:
                # exc_info为True会记录详细的报错堆栈，如果为False仅记录报错信息本身
                logger.error(f"[加载知识库]{path}加载失败：{str(e)}", exc_info=True)
                continue


    def add_single_document(self, file_path: str) -> tuple[bool, str]:
        """
        动态添加单个文档到向量库（支持用户运行时上传）

        Args:
            file_path: 文件绝对路径，支持 .txt 和 .pdf

        Returns:
            (success: bool, message: str)
        """
        if not os.path.exists(file_path):
            return False, f"文件不存在: {file_path}"

        def check_md5_hex(md5_for_check: str):
            store_path = get_abs_path(chroma_conf["md5_hex_store"])
            if not os.path.exists(store_path):
                open(store_path, "w", encoding="utf-8").close()
                return False
            with open(store_path, "r", encoding="utf-8") as f:
                for line in f.readlines():
                    if line.strip() == md5_for_check:
                        return True
            return False

        def save_md5_hex(md5_for_check: str):
            with open(get_abs_path(chroma_conf["md5_hex_store"]), "a", encoding="utf-8") as f:
                f.write(md5_for_check + "\n")

        try:
            md5_hex = get_file_md5_hex(file_path)
            if check_md5_hex(md5_hex):
                return False, f"文档已存在于知识库中（内容相同），跳过导入"

            if file_path.endswith(".txt"):
                documents = txt_loader(file_path)
            elif file_path.endswith(".pdf"):
                documents = pdf_loader(file_path)
            else:
                return False, f"不支持的文件类型，仅支持 .txt 和 .pdf"

            if not documents:
                return False, "文件内容为空或解析失败"

            split_docs = self.spliter.split_documents(documents)
            if not split_docs:
                return False, "文档分片后内容为空"

            self.vector_store.add_documents(split_docs)
            save_md5_hex(md5_hex)

            import os as _os
            fname = _os.path.basename(file_path)
            logger.info(f"[用户上传] {fname} 已成功添加到知识库，共 {len(split_docs)} 个分片")
            return True, f"✅ 文档「{fname}」已成功导入知识库（{len(split_docs)} 个知识分片）"

        except Exception as e:
            logger.error(f"[用户上传] 添加文档失败: {str(e)}", exc_info=True)
            return False, f"导入失败: {str(e)}"


if __name__ == '__main__':

    vs = VectorStoreService()

    vs.load_document()

    retriever = vs.get_retriever()

    res = retriever.invoke("迷路")
    for r in res:
        print(r.page_content)
        print("-"*20)



"""可观察、可审计的交通 RAG 知识库构建流水线。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import chromadb
from chromadb.config import Settings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from model.factory import embed_model
from utils.config_handler import chroma_conf
from utils.file_handler import pdf_loader, txt_loader
from utils.path_tool import get_project_root


EventCallback = Callable[[dict[str, Any]], None]


@dataclass
class ParsedFile:
    filename: str
    path: str
    file_type: str
    bytes: int
    sha256: str
    pages: int
    nonempty_pages: int
    characters: int
    chunks: int = 0
    status: str = "parsed"


class KnowledgeBaseBuilder:
    def __init__(
        self,
        data_path: str | None = None,
        persist_directory: str = "chroma_db_v2",
        collection_name: str = "traffic_agent_v2",
        batch_size: int = 16,
    ):
        self.project_root = Path(get_project_root()).resolve()
        configured_data_path = data_path or chroma_conf["data_path"]
        self.data_path = (self.project_root / configured_data_path).resolve()
        self.persist_directory = (self.project_root / persist_directory).resolve()
        self.collection_name = collection_name
        self.batch_size = batch_size
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separators"],
            length_function=len,
        )

    def _emit(
        self,
        callback: EventCallback | None,
        stage: str,
        message: str,
        progress: float,
        **data: Any,
    ) -> None:
        event = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "stage": stage,
            "message": message,
            "progress": round(max(0.0, min(1.0, progress)), 4),
            "data": data,
        }
        if callback:
            callback(event)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _discover(self) -> list[Path]:
        allowed = tuple(f".{ext.lower().lstrip('.')}" for ext in chroma_conf["allow_knowledge_file_type"])
        return sorted(
            path
            for path in self.data_path.iterdir()
            if path.is_file() and path.suffix.lower() in allowed
        )

    def _load(self, path: Path) -> list[Document]:
        if path.suffix.lower() == ".txt":
            return txt_loader(str(path))
        if path.suffix.lower() == ".pdf":
            return pdf_loader(str(path))
        return []

    def _safe_clean_target(self) -> None:
        if not self.persist_directory.exists():
            return
        if self.persist_directory.parent != self.project_root:
            raise RuntimeError(f"拒绝清理项目目录之外的向量库：{self.persist_directory}")
        if not self.persist_directory.name.startswith("chroma_db"):
            raise RuntimeError(f"拒绝清理非 chroma_db 目录：{self.persist_directory}")
        shutil.rmtree(self.persist_directory)

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    def build(
        self,
        callback: EventCallback | None = None,
        dry_run: bool = False,
        resume: bool = False,
    ) -> dict[str, Any]:
        started_at = datetime.now()
        run_id = started_at.strftime("%Y%m%d_%H%M%S")
        artifact_dir = self.project_root / "outputs" / "kb_build" / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        events: list[dict[str, Any]] = []

        def emit(stage: str, message: str, progress: float, **data: Any) -> None:
            event = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "stage": stage,
                "message": message,
                "progress": round(progress, 4),
                "data": data,
            }
            events.append(event)
            self._emit(callback, stage, message, progress, **data)

        files = self._discover()
        emit("discover", f"发现 {len(files)} 份可入库中文文档", 0.02, files=[p.name for p in files])

        parsed_files: list[ParsedFile] = []
        all_chunks: list[dict[str, Any]] = []
        for file_index, path in enumerate(files, start=1):
            t0 = time.perf_counter()
            documents = self._load(path)
            nonempty_documents = [doc for doc in documents if doc.page_content.strip()]
            characters = sum(len(doc.page_content) for doc in nonempty_documents)
            record = ParsedFile(
                filename=path.name,
                path=str(path.relative_to(self.project_root)).replace("\\", "/"),
                file_type=path.suffix.lower().lstrip("."),
                bytes=path.stat().st_size,
                sha256=self._sha256(path),
                pages=len(documents),
                nonempty_pages=len(nonempty_documents),
                characters=characters,
                status="parsed" if characters else "empty",
            )

            split_docs = self.splitter.split_documents(nonempty_documents)
            record.chunks = len(split_docs)
            for chunk_index, chunk in enumerate(split_docs):
                content = chunk.page_content.strip()
                chunk_id = hashlib.sha256(
                    f"{record.sha256}:{chunk_index}:{content}".encode("utf-8")
                ).hexdigest()[:32]
                metadata = {
                    **chunk.metadata,
                    "source": str(path),
                    "filename": path.name,
                    "file_sha256": record.sha256,
                    "chunk_index": chunk_index,
                    "total_chunks": len(split_docs),
                    "file_type": record.file_type,
                }
                all_chunks.append(
                    {
                        "id": chunk_id,
                        "content": content,
                        "characters": len(content),
                        "metadata": metadata,
                    }
                )

            parsed_files.append(record)
            elapsed_ms = round((time.perf_counter() - t0) * 1000)
            progress = 0.05 + 0.30 * file_index / max(len(files), 1)
            emit(
                "parse_and_split",
                f"{path.name}: {record.characters} 字符 → {record.chunks} 个分片",
                progress,
                file=asdict(record),
                elapsed_ms=elapsed_ms,
                chunk_samples=[chunk.page_content[:160] for chunk in split_docs[:2]],
            )

        self._write_jsonl(artifact_dir / "chunks.jsonl", all_chunks)
        (artifact_dir / "documents.json").write_text(
            json.dumps([asdict(item) for item in parsed_files], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        emit(
            "split_complete",
            f"切片完成：{sum(x.characters for x in parsed_files)} 字符，{len(all_chunks)} 个分片",
            0.38,
            chunks_file=str((artifact_dir / "chunks.jsonl").relative_to(self.project_root)),
        )

        embedding_batches: list[dict[str, Any]] = []
        retrieval_checks: list[dict[str, Any]] = []
        vector_dimension = 0
        stored_count = 0

        if not dry_run:
            if not resume:
                self._safe_clean_target()
            self.persist_directory.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=Settings(anonymized_telemetry=False),
            )
            collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            total_batches = math.ceil(len(all_chunks) / self.batch_size)
            for batch_number, start in enumerate(range(0, len(all_chunks), self.batch_size), start=1):
                batch = all_chunks[start : start + self.batch_size]
                texts = [item["content"] for item in batch]
                ids = [item["id"] for item in batch]
                existing = collection.get(ids=ids, include=["embeddings"]) if resume else {"ids": []}
                existing_ids = set(existing.get("ids") or [])
                if len(existing_ids) == len(ids):
                    existing_embeddings = existing.get("embeddings")
                    if existing_embeddings is not None and len(existing_embeddings) > 0:
                        vector_dimension = len(existing_embeddings[0])
                    batch_report = {
                        "batch": batch_number,
                        "items": len(batch),
                        "dimension": vector_dimension,
                        "elapsed_ms": 0,
                        "skipped": True,
                        "reason": "断点续建：该批次已存在",
                        "first_chunk_id": batch[0]["id"],
                    }
                    embedding_batches.append(batch_report)
                    progress = 0.40 + 0.50 * batch_number / max(total_batches, 1)
                    emit(
                        "embedding_resume",
                        f"向量批次 {batch_number}/{total_batches} 已存在，跳过重复调用",
                        progress,
                        **batch_report,
                    )
                    continue

                vectors = None
                elapsed_ms = 0
                for attempt in range(1, 6):
                    t0 = time.perf_counter()
                    try:
                        vectors = embed_model.embed_documents(texts)
                        elapsed_ms = round((time.perf_counter() - t0) * 1000)
                        break
                    except Exception as exc:
                        elapsed_ms += round((time.perf_counter() - t0) * 1000)
                        if attempt >= 5:
                            emit(
                                "embedding_failed",
                                f"向量批次 {batch_number}/{total_batches} 连续失败 5 次",
                                0.40 + 0.50 * (batch_number - 1) / max(total_batches, 1),
                                batch=batch_number,
                                error=str(exc),
                            )
                            self._write_jsonl(artifact_dir / "events.jsonl", events)
                            raise
                        wait_seconds = min(2 ** attempt, 20)
                        emit(
                            "embedding_retry",
                            f"向量批次 {batch_number}/{total_batches} 第 {attempt} 次失败，{wait_seconds} 秒后重试",
                            0.40 + 0.50 * (batch_number - 1) / max(total_batches, 1),
                            batch=batch_number,
                            attempt=attempt,
                            wait_seconds=wait_seconds,
                            error=str(exc),
                        )
                        time.sleep(wait_seconds)

                assert vectors is not None
                if not vectors or len(vectors) != len(batch):
                    raise RuntimeError(f"第 {batch_number} 批向量数量异常")
                dimensions = {len(vector) for vector in vectors}
                if len(dimensions) != 1:
                    raise RuntimeError(f"第 {batch_number} 批向量维度不一致：{dimensions}")
                vector_dimension = dimensions.pop()
                norms = [math.sqrt(sum(value * value for value in vector)) for vector in vectors]
                collection.upsert(
                    ids=ids,
                    documents=texts,
                    metadatas=[item["metadata"] for item in batch],
                    embeddings=vectors,
                )
                batch_report = {
                    "batch": batch_number,
                    "items": len(batch),
                    "dimension": vector_dimension,
                    "elapsed_ms": elapsed_ms,
                    "skipped": False,
                    "norm_min": min(norms),
                    "norm_max": max(norms),
                    "sample_vector": vectors[0][:8],
                    "first_chunk_id": batch[0]["id"],
                }
                embedding_batches.append(batch_report)
                progress = 0.40 + 0.50 * batch_number / max(total_batches, 1)
                emit(
                    "embedding",
                    f"向量批次 {batch_number}/{total_batches}: {len(batch)} 条 × {vector_dimension} 维",
                    progress,
                    **batch_report,
                )

            stored_count = collection.count()
            emit("store", f"Chroma 写入完成，共 {stored_count} 个向量", 0.93, count=stored_count)

            test_queries = [
                "道路交通事故发生后应当如何处置",
                "城市道路拥堵和交通运行状态如何评价",
                "校车安全管理有哪些要求",
                "城市公共交通运营安全责任",
            ]
            query_vectors = embed_model.embed_documents(test_queries)
            for query, vector in zip(test_queries, query_vectors):
                result = collection.query(query_embeddings=[vector], n_results=3)
                hits = []
                for index, document in enumerate(result.get("documents", [[]])[0]):
                    metadata = result.get("metadatas", [[]])[0][index]
                    distance = result.get("distances", [[]])[0][index]
                    hits.append(
                        {
                            "filename": metadata.get("filename"),
                            "chunk_index": metadata.get("chunk_index"),
                            "distance": distance,
                            "preview": document[:180],
                        }
                    )
                retrieval_checks.append({"query": query, "hits": hits})
                emit(
                    "retrieval_check",
                    f"检索验收：{query} → {len(hits)} 条结果",
                    0.95 + 0.04 * len(retrieval_checks) / len(test_queries),
                    query=query,
                    hits=hits,
                )

        finished_at = datetime.now()
        report = {
            "run_id": run_id,
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": finished_at.isoformat(timespec="seconds"),
            "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
            "dry_run": dry_run,
            "resume": resume,
            "data_path": str(self.data_path),
            "persist_directory": str(self.persist_directory),
            "collection_name": self.collection_name,
            "documents": [asdict(item) for item in parsed_files],
            "total_documents": len(parsed_files),
            "total_characters": sum(item.characters for item in parsed_files),
            "total_chunks": len(all_chunks),
            "embedding_batches": embedding_batches,
            "vector_dimension": vector_dimension,
            "stored_count": stored_count,
            "retrieval_checks": retrieval_checks,
            "artifacts": {
                "documents": str((artifact_dir / "documents.json").relative_to(self.project_root)),
                "chunks": str((artifact_dir / "chunks.jsonl").relative_to(self.project_root)),
                "events": str((artifact_dir / "events.jsonl").relative_to(self.project_root)),
            },
        }
        self._write_jsonl(artifact_dir / "embedding_batches.jsonl", embedding_batches)
        self._write_jsonl(artifact_dir / "events.jsonl", events)
        report_path = artifact_dir / "report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        latest_path = self.project_root / "outputs" / "kb_build" / "latest_report.json"
        shutil.copy2(report_path, latest_path)
        emit("complete", "知识库构建与检索验收完成", 1.0, report=str(report_path))
        return report


def console_callback(event: dict[str, Any]) -> None:
    print(
        f"[{event['time']}] [{event['stage']}] "
        f"{event['progress'] * 100:6.2f}% {event['message']}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="构建可观察的交通 RAG 知识库")
    parser.add_argument("--dry-run", action="store_true", help="只执行解析与切片，不调用嵌入模型")
    parser.add_argument("--persist-directory", default="chroma_db_v2")
    parser.add_argument("--collection-name", default="traffic_agent_v2")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--resume", action="store_true", help="从目标集合中已有的批次继续构建")
    args = parser.parse_args()
    builder = KnowledgeBaseBuilder(
        persist_directory=args.persist_directory,
        collection_name=args.collection_name,
        batch_size=args.batch_size,
    )
    report = builder.build(callback=console_callback, dry_run=args.dry_run, resume=args.resume)
    print(json.dumps({
        "documents": report["total_documents"],
        "chunks": report["total_chunks"],
        "vectors": report["stored_count"],
        "dimension": report["vector_dimension"],
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

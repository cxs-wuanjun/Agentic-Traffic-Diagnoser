"""下载并整理国家法律法规数据库中的中文交通领域语料。"""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
from pathlib import Path

import requests
from docx import Document
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "traffic_knowledge"
SOURCE_DIR = KNOWLEDGE_DIR / "source_files"
MANIFEST_PATH = KNOWLEDGE_DIR / "corpus_manifest.json"

SEARCH_URL = "https://flk.npc.gov.cn/law-search/search/list"
DETAIL_URL = "https://flk.npc.gov.cn/law-search/search/flfgDetails"
DOWNLOAD_URL = "https://flk.npc.gov.cn/law-search/download/pc"

DOCUMENTS = [
    ("中华人民共和国道路交通安全法", "law_road_traffic_safety_2021"),
    ("中华人民共和国道路交通安全法实施条例", "regulation_road_traffic_safety_implementation_2017"),
    ("城市公共交通条例", "regulation_urban_public_transport_2024"),
    ("公路安全保护条例", "regulation_highway_safety_protection_2011"),
    ("中华人民共和国公路法", "law_highway"),
    ("中华人民共和国道路运输条例", "regulation_road_transport"),
    ("城市道路管理条例", "regulation_urban_roads"),
    ("收费公路管理条例", "regulation_toll_roads"),
    ("校车安全管理条例", "regulation_school_bus_safety"),
    ("危险化学品安全管理条例", "regulation_hazardous_chemicals"),
    ("中华人民共和国突发事件应对法", "law_emergency_response"),
    ("生产安全事故应急条例", "regulation_work_safety_emergency"),
    ("生产安全事故报告和调查处理条例", "regulation_accident_reporting_investigation"),
    ("中华人民共和国安全生产法", "law_work_safety"),
    ("中华人民共和国大气污染防治法", "law_air_pollution_prevention"),
    ("中华人民共和国噪声污染防治法", "law_noise_pollution_prevention"),
    ("中华人民共和国无障碍环境建设法", "law_accessible_environment"),
    ("铁路交通事故应急救援和调查处理条例", "regulation_railway_accident_emergency"),
]


def clean_title(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def search_current(session: requests.Session, title: str) -> dict:
    payload = {
        "searchRange": 1,
        "sxrq": [],
        "gbrq": [],
        "searchType": 2,
        "sxx": [],
        "gbrqYear": [],
        "flfgCodeId": [],
        "zdjgCodeId": [],
        "searchContent": title,
        "orderByParam": {"order": "-1", "sort": ""},
        "pageNum": 1,
        "pageSize": 20,
    }
    response = session.post(SEARCH_URL, json=payload, timeout=60)
    response.raise_for_status()
    rows = response.json().get("rows", [])
    matches = [row for row in rows if clean_title(row.get("title")) == title and row.get("sxx") == 3]
    if not matches:
        raise RuntimeError(f"没有找到现行官方文本：{title}")
    matches.sort(key=lambda row: row.get("gbrq") or "", reverse=True)
    return matches[0]


def get_detail(session: requests.Session, bbbs: str) -> dict:
    response = session.get(DETAIL_URL, params={"bbbs": bbbs}, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 200 or not payload.get("data"):
        raise RuntimeError(f"法规详情读取失败：{bbbs}")
    return payload["data"]


def get_download_url(session: requests.Session, bbbs: str, file_format: str) -> str:
    response = session.get(
        DOWNLOAD_URL,
        params={"bbbs": bbbs, "format": file_format},
        timeout=60,
    )
    response.raise_for_status()
    url = (response.json().get("data") or {}).get("url")
    if not url:
        raise RuntimeError(f"官方记录没有 {file_format} 下载地址：{bbbs}")
    return url


def download(session: requests.Session, url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, stream=True, timeout=180) as response:
        response.raise_for_status()
        with destination.open("wb") as output:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    output.write(chunk)


def docx_to_text(source: Path, destination: Path, detail: dict) -> None:
    document = Document(source)
    bbbs = detail["bbbs"]
    lines = [
        f"# {detail['title']}",
        "",
        "来源：国家法律法规数据库（全国人大常委会办公厅维护）",
        f"制定机关：{detail.get('zdjgName') or '未标明'}",
        f"公布日期：{detail.get('gbrq') or '未标明'}",
        f"施行日期：{detail.get('sxrq') or '未标明'}",
        f"来源接口：{DETAIL_URL}?bbbs={bbbs}",
        "说明：以下正文由官方 DOCX 文件机械抽取，未进行内容改写。",
        "",
    ]
    lines.extend(paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip())
    for table in document.tables:
        for row in table.rows:
            values = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            if any(values):
                lines.append(" | ".join(values))
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_document(session: requests.Session, title: str, stem: str) -> dict:
    row = search_current(session, title)
    detail = get_detail(session, row["bbbs"])
    oss_file = detail.get("ossFile") or {}

    # PDF（包括扫描件）作为原始档案保留在 source_files，不直接参与向量化。
    pdf_source_path = None
    if oss_file.get("ossPdfPath"):
        pdf_source_path = SOURCE_DIR / f"{stem}.pdf"
        legacy_pdf = KNOWLEDGE_DIR / f"{stem}.pdf"
        if legacy_pdf.exists() and not pdf_source_path.exists():
            legacy_pdf.replace(pdf_source_path)
        elif not pdf_source_path.exists():
            download(session, get_download_url(session, row["bbbs"], "pdf"), pdf_source_path)
        if pdf_source_path.read_bytes()[:5] != b"%PDF-":
            raise RuntimeError(f"下载文件不是有效 PDF：{pdf_source_path.name}")

    # 官方 PDF 中存在扫描件。优先使用 DOCX 抽取文本，保证每份入库文件都有可检索正文。
    if oss_file.get("ossWordPath"):
        source_path = SOURCE_DIR / f"{stem}.docx"
        output_path = KNOWLEDGE_DIR / f"{stem}.txt"
        if not source_path.exists():
            download(session, get_download_url(session, row["bbbs"], "docx"), source_path)
        if source_path.read_bytes()[:2] != b"PK":
            raise RuntimeError(f"下载文件不是有效 DOCX：{source_path.name}")
        docx_to_text(source_path, output_path, detail)
        source_format = "docx-derived-txt"
    elif oss_file.get("ossPdfPath"):
        output_path = KNOWLEDGE_DIR / f"{stem}.pdf"
        if not output_path.exists() and pdf_source_path:
            shutil.copy2(pdf_source_path, output_path)
        if output_path.read_bytes()[:5] != b"%PDF-":
            raise RuntimeError(f"下载文件不是有效 PDF：{output_path.name}")
        source_path = output_path
        source_format = "pdf"
    else:
        raise RuntimeError(f"官方记录没有可下载文件：{title}")

    return {
        "title": detail["title"],
        "bbbs": row["bbbs"],
        "authority": detail.get("zdjgName"),
        "published": detail.get("gbrq"),
        "effective": detail.get("sxrq"),
        "status": "现行",
        "source": f"{DETAIL_URL}?bbbs={row['bbbs']}",
        "source_format": source_format,
        "knowledge_file": str(output_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "source_file": str(source_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "pdf_source_file": (
            str(pdf_source_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
            if pdf_source_path
            else None
        ),
        "size": output_path.stat().st_size,
        "sha256": sha256(output_path),
    }


def main() -> None:
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 Traffic-RAG-Corpus-Builder/1.0",
            "Referer": "https://flk.npc.gov.cn/",
        }
    )
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=None,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))

    manifest = []
    failures = []
    for title, stem in DOCUMENTS:
        try:
            record = build_document(session, title, stem)
            manifest.append(record)
            print(f"[OK] {title} -> {record['knowledge_file']}")
        except Exception as exc:  # 逐份继续，最终统一报告失败项
            failures.append({"title": title, "error": str(exc)})
            print(f"[FAILED] {title}: {exc}")

    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "source": "国家法律法规数据库",
                "source_home": "https://flk.npc.gov.cn/",
                "documents": manifest,
                "failures": failures,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"完成：成功 {len(manifest)} 份，失败 {len(failures)} 份")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

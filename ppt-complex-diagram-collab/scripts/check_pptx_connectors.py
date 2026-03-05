"""校验 PPTX 中 connector 的粘连完整性与目标节点合法性。

定位与作用
----------
用于验证“可编辑复杂图（如系统架构图）”中的连接线是否真正粘连到 shape，避免出现
“看起来连上了，但拖动后散线/连错对象”的问题。

核心流程
----------
1. 读取 pptx（zip）里的 slide XML；
2. 建立 shape_id -> 文本 的映射；
3. 遍历每条 connector（p:cxnSp），检查是否同时存在 stCxn/endCxn；
4. 校验连接端点 id 是否存在；
5. 可选：禁止连接到特定前缀节点（例如 "Lane "）。

失败策略
----------
发现结构错误或非法连接时，返回非零退出码并打印错误明细。
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}


@dataclass
class ConnectorRecord:
    """表示一条 connector 的结构化结果。"""

    connector_id: str
    from_shape_id: str | None
    to_shape_id: str | None
    from_idx: str | None
    to_idx: str | None
    from_text: str
    to_text: str


def _read_slide_xml(pptx_path: Path, slide_num: int) -> ET.Element:
    """读取指定页 slide XML（slide_num 从 1 开始）。"""
    member = f"ppt/slides/slide{slide_num}.xml"
    with ZipFile(pptx_path) as archive:
        try:
            raw = archive.read(member)
        except KeyError as exc:
            raise ValueError(f"slide 不存在: {member}") from exc
    return ET.fromstring(raw)


def _collect_shape_text(root: ET.Element) -> dict[str, str]:
    """收集当前 slide 的 shape id 与文本内容映射。"""
    mapping: dict[str, str] = {}
    for shape in root.findall(".//p:sp", NS):
        nv = shape.find("./p:nvSpPr/p:cNvPr", NS)
        if nv is None:
            continue
        shape_id = nv.get("id")
        if not shape_id:
            continue
        text_nodes = [node.text for node in shape.findall(".//a:t", NS) if node.text]
        mapping[shape_id] = "".join(text_nodes).strip()
    return mapping


def _collect_connectors(root: ET.Element, shape_text_map: dict[str, str]) -> list[ConnectorRecord]:
    """收集当前 slide 所有 connector 与端点文本。"""
    records: list[ConnectorRecord] = []
    for connector in root.findall(".//p:cxnSp", NS):
        nv = connector.find("./p:nvCxnSpPr/p:cNvPr", NS)
        connector_id = nv.get("id") if nv is not None else "unknown"

        st = connector.find("./p:nvCxnSpPr/p:cNvCxnSpPr/a:stCxn", NS)
        ed = connector.find("./p:nvCxnSpPr/p:cNvCxnSpPr/a:endCxn", NS)

        from_shape_id = st.get("id") if st is not None else None
        from_idx = st.get("idx") if st is not None else None
        to_shape_id = ed.get("id") if ed is not None else None
        to_idx = ed.get("idx") if ed is not None else None

        records.append(
            ConnectorRecord(
                connector_id=connector_id,
                from_shape_id=from_shape_id,
                to_shape_id=to_shape_id,
                from_idx=from_idx,
                to_idx=to_idx,
                from_text=shape_text_map.get(from_shape_id or "", ""),
                to_text=shape_text_map.get(to_shape_id or "", ""),
            )
        )
    return records


def _slide_numbers(pptx_path: Path, selected_slides: list[int] | None) -> list[int]:
    """返回要检查的 slide 编号列表（1-based）。"""
    if selected_slides:
        return selected_slides

    with ZipFile(pptx_path) as archive:
        slide_names = [
            name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        ]
    indices = sorted(int(name.split("slide")[-1].split(".xml")[0]) for name in slide_names)
    return indices


def _validate_records(records: list[ConnectorRecord], shape_text_map: dict[str, str], forbid_prefixes: list[str]) -> list[str]:
    """执行连接器合法性校验，返回错误列表。"""
    errors: list[str] = []

    for record in records:
        cid = record.connector_id
        if not record.from_shape_id or not record.to_shape_id:
            errors.append(f"conn#{cid}: 缺少 stCxn 或 endCxn")
            continue

        if record.from_shape_id not in shape_text_map:
            errors.append(f"conn#{cid}: 起点 shape id 无法解析 ({record.from_shape_id})")
        if record.to_shape_id not in shape_text_map:
            errors.append(f"conn#{cid}: 终点 shape id 无法解析 ({record.to_shape_id})")

        for prefix in forbid_prefixes:
            if record.from_text.startswith(prefix):
                errors.append(f"conn#{cid}: 起点非法前缀 '{prefix}' -> {record.from_text!r}")
            if record.to_text.startswith(prefix):
                errors.append(f"conn#{cid}: 终点非法前缀 '{prefix}' -> {record.to_text!r}")

    return errors


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="校验 PPTX connector 粘连与目标节点合法性")
    parser.add_argument("--pptx", required=True, type=Path, help="待检查的 pptx 文件路径")
    parser.add_argument("--slide", type=int, action="append", dest="slides", help="指定检查某一页，可重复")
    parser.add_argument(
        "--forbid-prefix",
        action="append",
        default=["Lane "],
        help="禁止 connector 连接到此前缀的 shape 文本，可重复",
    )
    parser.add_argument("--json-out", type=Path, help="可选：输出结构化结果到 json 文件")
    return parser.parse_args()


def main() -> int:
    """主流程：遍历 slide，校验 connector，并输出摘要。"""
    args = parse_args()
    pptx_path = args.pptx.resolve()

    if not pptx_path.exists():
        print(f"[ERROR] pptx 不存在: {pptx_path}")
        return 2

    slide_nums = _slide_numbers(pptx_path, args.slides)
    all_errors: list[str] = []
    all_records: dict[int, list[dict[str, str | None]]] = {}

    for slide_num in slide_nums:
        root = _read_slide_xml(pptx_path, slide_num)
        shape_text_map = _collect_shape_text(root)
        records = _collect_connectors(root, shape_text_map)
        errors = _validate_records(records, shape_text_map, args.forbid_prefix)

        print(f"[INFO] slide {slide_num}: shapes={len(shape_text_map)} connectors={len(records)} errors={len(errors)}")

        if errors:
            for err in errors:
                print(f"  - {err}")

        all_errors.extend(f"slide {slide_num}: {err}" for err in errors)
        all_records[slide_num] = [
            {
                "connector_id": rec.connector_id,
                "from_shape_id": rec.from_shape_id,
                "to_shape_id": rec.to_shape_id,
                "from_idx": rec.from_idx,
                "to_idx": rec.to_idx,
                "from_text": rec.from_text,
                "to_text": rec.to_text,
            }
            for rec in records
        ]

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(all_records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[INFO] 写入 JSON: {args.json_out}")

    if all_errors:
        print(f"[FAIL] 检查失败，总错误数: {len(all_errors)}")
        return 1

    print("[OK] 所有 connector 校验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())

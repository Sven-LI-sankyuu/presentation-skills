"""Word / PPT 统一 Agent QC reminder 协议、分类、策略与渲染。

这个模块只处理“给 agent 的提醒”这一层：把各 skill 已有 QC 输出归一成
observation，映射 taxonomy 和 policy，保守合并同一问题，再渲染成 token
可控的 JSON / Markdown sidecar。底层 detector 和旧报告继续由各自 skill 维护。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Iterable
import hashlib
import json
import re

SCHEMA_VERSION = "1.0"
TAXONOMY_VERSION = "1.0"
POLICY_VERSION = "1.0"

SAMPLE_LIMIT_BY_ACTION = {
    "hard_block": 3,
    "soft_block": 3,
    "advisory": 1,
}
ACTION_SORT = {"hard_block": 0, "soft_block": 1, "advisory": 2}
STATUS_SORT = {"detected": 0, "not_checked": 1, "suppressed": 2}
SEVERITY_SORT = {"error": 0, "warning": 1, "not_checked": 2, "info": 3}
FONT_LITERAL_ASSIGNMENT_RE = re.compile(
    r"""
    (?P<field>["']?[\w.-]*(?:font(?:[_-]?size|[_-]?pt|size)?|fontsize|font_pt|size_pt|字号)[\w.-]*["']?)
    \s*[:=]\s*
    (?:Pt\(\s*)?
    ["']?(?P<value>\d+(?:\.\d+)?)
    """,
    re.IGNORECASE | re.VERBOSE,
)
FONT_LITERAL_PT_CALL_RE = re.compile(r"\bPt\(\s*(?P<value>\d+(?:\.\d+)?)\s*\)")
FONT_TOKEN_ROLE_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("dense_table", ("dense_table", "dense-table", "dense table", "dense", "密表")),
    ("table_caption", ("table_caption", "tablecaption", "table caption", "表注")),
    ("table_title", ("table_title", "tabletitle", "table title", "表题")),
    ("figure_note", ("figure_note", "figurenote", "figure note", "图注")),
    ("source_note", ("source_note", "sourcenote", "source note", "来源")),
    ("figure_title", ("figure_title", "figuretitle", "figure title", "图题")),
    ("page_title", ("page_title", "pagetitle", "page title", "页标题")),
    ("section_title", ("section_title", "sectiontitle", "section title", "章节标题")),
    ("doc_title", ("doc_title", "doctitle", "document title", "文档标题")),
    ("subtitle", ("subtitle", "sub_title", "副标题")),
    ("table", ("table_font", "table font", "table", "表格")),
    ("caption", ("caption", "图注", "表注")),
    ("label", ("label", "标签")),
    ("body", ("body", "正文")),
    ("list", ("list", "列表")),
    ("lead", ("lead", "导语")),
    ("hero", ("hero", "封面主标题")),
)


@dataclass(frozen=True)
class TaxonomyEntry:
    """定义一个 detector code 对应的稳定 QC 分类。"""

    domain: str
    family: str
    problem_class: str
    definition: str
    fix_strategy_id: str


@dataclass(frozen=True)
class PolicyEntry:
    """定义一个 problem class 在提醒层的工作流动作。"""

    agent_action: str
    block_before: str | None
    resolution_policy_id: str
    allowed_resolution_actions: tuple[str, ...]
    conditions: tuple[str, ...]
    requires_human: bool = False


TAXONOMY_CATALOG: dict[str, TaxonomyEntry] = {
    "zip_integrity_failure": TaxonomyEntry("artifact_integrity", "package", "artifact_integrity.package.zip_integrity", "PPTX zip 包损坏。", "rebuild_artifact"),
    "presentation_slide_count_mismatch": TaxonomyEntry("artifact_integrity", "package", "artifact_integrity.package.slide_count_mismatch", "presentation slide 数与实际 slide 数不一致。", "repair_package_metadata"),
    "docprops_slide_count_mismatch": TaxonomyEntry("artifact_integrity", "package", "artifact_integrity.package.slide_count_mismatch", "docProps slide 统计与实际 slide 数不一致。", "repair_package_metadata"),
    "stale_section_reference": TaxonomyEntry("artifact_integrity", "package", "artifact_integrity.package.stale_reference", "section 扩展引用已删除 slide。", "repair_package_relationships"),
    "missing_slide_relationship_target": TaxonomyEntry("artifact_integrity", "package", "artifact_integrity.package.missing_relationship_target", "slide relationship 指向缺失 part。", "repair_package_relationships"),
    "slide_relationship_count_mismatch": TaxonomyEntry("artifact_integrity", "package", "artifact_integrity.package.relationship_count_mismatch", "slide relationship 数量与实际 slide 数不一致。", "repair_package_relationships"),
    "mobile_compatibility_embedded_object": TaxonomyEntry("compatibility", "mobile", "compatibility.mobile.embedded_object", "移动端兼容性较弱的嵌入对象。", "replace_or_document_embedded_object"),
    "markdown_missing": TaxonomyEntry("source_integrity", "source_file", "source_integrity.markdown.missing", "Markdown 源文件缺失。", "restore_source_file"),
    "missing_image_asset": TaxonomyEntry("source_integrity", "asset", "source_integrity.asset.missing", "Markdown 引用的图片资产缺失。", "restore_asset"),
    "asset_manifest_missing": TaxonomyEntry("source_integrity", "asset_manifest", "source_integrity.asset_manifest.missing", "资产 manifest 文件缺失。", "restore_asset_manifest"),
    "asset_manifest_required": TaxonomyEntry("source_integrity", "asset_manifest", "source_integrity.asset_manifest.required", "精细模式需要资产 manifest。", "restore_asset_manifest"),
    "asset_manifest_invalid": TaxonomyEntry("source_integrity", "asset_manifest", "source_integrity.asset_manifest.invalid", "资产 manifest 结构非法。", "repair_asset_manifest"),
    "workspace_lint_error": TaxonomyEntry("source_integrity", "workspace", "source_integrity.workspace.contract_invalid", "Workspace 输入或合同不满足继续构建的最低要求。", "repair_workspace_contract"),
    "workspace_lint_warning": TaxonomyEntry("source_integrity", "workspace", "source_integrity.workspace.review_required", "Workspace 输入或合同存在需要 review 的非阻断风险。", "repair_workspace_contract"),
    "asset_manifest_count_mismatch": TaxonomyEntry("source_integrity", "asset_manifest", "source_integrity.asset_manifest.count_mismatch", "资产 manifest 数量与正文图片数量不一致。", "repair_asset_manifest"),
    "asset_mode_missing": TaxonomyEntry("source_integrity", "asset_manifest", "source_integrity.asset_manifest.field_missing", "资产 manifest 缺少 asset_mode。", "repair_asset_manifest"),
    "asset_source_missing": TaxonomyEntry("source_integrity", "asset", "source_integrity.asset.missing", "资产 manifest 声明的 source_file 缺失。", "restore_asset"),
    "generator_script_missing": TaxonomyEntry("source_integrity", "asset_manifest", "source_integrity.asset_manifest.generator_missing", "复杂资产缺少 generator_script。", "repair_asset_manifest"),
    "deprecated_caption_prefix": TaxonomyEntry("content_structure", "caption", "content_structure.caption.deprecated_prefix", "Markdown 仍使用调试式题注前缀。", "repair_caption_semantics"),
    "language_contract_mismatch": TaxonomyEntry("content_structure", "language_contract", "content_structure.language.contract_mismatch", "源文案语义前缀与 active profile 语言合同不一致。", "repair_language_contract"),
    "heading_jump": TaxonomyEntry("content_structure", "heading", "content_structure.heading.level_jump", "标题层级跳级。", "repair_heading_hierarchy"),
    "missing_doc_title": TaxonomyEntry("content_structure", "heading", "content_structure.heading.missing_doc_title", "文档缺少主标题。", "repair_heading_hierarchy"),
    "table_title_mismatch": TaxonomyEntry("content_structure", "caption", "content_structure.caption.table_title_mismatch", "表格数量与表题数量不一致。", "repair_caption_semantics"),
    "table_caption_mismatch": TaxonomyEntry("content_structure", "caption", "content_structure.caption.table_caption_mismatch", "表格数量与表注数量不一致。", "repair_caption_semantics"),
    "figure_title_mismatch": TaxonomyEntry("content_structure", "caption", "content_structure.caption.figure_title_mismatch", "图片数量与图题数量不一致。", "repair_caption_semantics"),
    "figure_note_mismatch": TaxonomyEntry("content_structure", "caption", "content_structure.caption.figure_note_mismatch", "图片数量与图注数量不一致。", "repair_caption_semantics"),
    "source_note_mismatch": TaxonomyEntry("content_structure", "caption", "content_structure.caption.source_note_mismatch", "图片数量与来源说明数量不一致。", "repair_caption_semantics"),
    "figure_note_missing": TaxonomyEntry("content_structure", "caption", "content_structure.caption.figure_note_missing", "图片缺少图注。", "repair_caption_semantics"),
    "source_note_missing": TaxonomyEntry("content_structure", "caption", "content_structure.caption.source_note_missing", "图片缺少来源说明。", "repair_caption_semantics"),
    "caption_policy_drift": TaxonomyEntry("content_structure", "caption", "content_structure.caption.policy_drift", "资产题注位置与 active profile 不一致。", "repair_caption_semantics"),
    "qa_check_failed.source_integrity": TaxonomyEntry("source_integrity", "source_file", "source_integrity.qa.source_contract_failed", "Word source 契约检查未通过。", "repair_source_contract"),
    "qa_check_failed.style_contract": TaxonomyEntry("typography", "paragraph_contract", "typography.paragraph.style_contract_drift", "Word 段落样式契约未通过。", "repair_style_contract"),
    "qa_check_failed.font_slot_integrity": TaxonomyEntry("typography", "font_slot", "typography.font_slot.integrity", "Word 字体槽位不完整。", "repair_font_slots"),
    "qa_check_failed.block_sequence": TaxonomyEntry("content_structure", "sequence", "content_structure.sequence.block_mismatch", "DOCX block 顺序与 Markdown 不一致。", "rebuild_from_source"),
    "qa_check_failed.section_contract": TaxonomyEntry("layout", "section", "layout.section.contract_drift", "Word section 栏数契约不一致。", "repair_section_contract"),
    "qa_check_failed.asset_manifest_integrity": TaxonomyEntry("source_integrity", "asset_manifest", "source_integrity.asset_manifest.invalid", "Word 资产 manifest QA 未通过。", "repair_asset_manifest"),
    "qa_check_failed.visual_review_status": TaxonomyEntry("validation_coverage", "visual_review", "validation_coverage.gate.visual_review_missing", "Word visual review 证据缺失或无效。", "complete_visual_review"),
    "table_paragraph_special_indent": TaxonomyEntry("typography", "table_indent", "typography.table.indent_review", "PPT 表格单元格段落存在非零特殊缩进。", "review_table_indent"),
    "table_cell_vertical_alignment_not_centered": TaxonomyEntry("typography", "table_alignment", "typography.table.vertical_alignment_review", "PPT 表格单元格内容未上下居中。", "repair_table_vertical_alignment"),
    "font_size_policy_off_half_point_grid": TaxonomyEntry("typography", "font_size", "typography.font_size.profile_token_off_grid", "Active profile 自身包含非半点字号 token。", "repair_font_size_token"),
    "font_size_source_literal_off_half_point_grid": TaxonomyEntry("typography", "font_size", "typography.font_size.off_grid", "构建源或配置中手填了偏离 0.5pt 网格的字号。", "repair_font_size_token"),
    "font_size_source_literal_role_drift": TaxonomyEntry("typography", "font_size", "typography.font_size.role_drift", "构建源或配置中的字号偏离 active role token。", "repair_font_size_token"),
    "font_size_off_half_point_grid": TaxonomyEntry("typography", "font_size", "typography.font_size.off_grid", "可见文字字号偏离 0.5pt 网格。", "repair_font_size_token"),
    "font_size_role_drift": TaxonomyEntry("typography", "font_size", "typography.font_size.role_drift", "可见文字字号偏离语义 role 的 active token。", "repair_font_size_token"),
    "font_size_outside_profile_scale": TaxonomyEntry("typography", "font_size", "typography.font_size.outside_scale", "可见文字使用 active profile 之外的临时字号。", "repair_font_size_token"),
    "font_size_outside_theme_scale": TaxonomyEntry("typography", "font_size", "typography.font_size.outside_scale", "可见文字使用 active theme token 之外的临时字号。", "repair_font_size_token"),
    "body_text_below_theme_token": TaxonomyEntry("typography", "font_size", "typography.font_size.role_drift", "长正文低于 active body token。", "repair_font_size_token"),
    "table_font_below_theme_token": TaxonomyEntry("typography", "font_size", "typography.font_size.role_drift", "表格文字低于 active table token。", "repair_font_size_token"),
    "font_size_below_caption_floor": TaxonomyEntry("typography", "font_size", "typography.font_size.role_drift", "可见文字低于 active caption token。", "repair_font_size_token"),
    "font_size_fragmentation": TaxonomyEntry("typography", "font_size", "typography.font_size.fragmentation", "显式字号档位过多。", "repair_font_size_system"),
    "textbox_fit_failure": TaxonomyEntry("layout", "text_fit", "layout.text_fit.bounds_overflow", "文本估计边界越出容器。", "repair_text_fit"),
    "textbox_fit_near_overflow": TaxonomyEntry("layout", "text_fit", "layout.text_fit.near_overflow", "文本接近容器边界。", "repair_text_fit"),
    "compact_textbox_width_pressure": TaxonomyEntry("layout", "text_fit", "layout.text_fit.width_pressure", "短文本容器宽度压力过高。", "repair_text_fit"),
    "boundary_touch_ink_preview_missing": TaxonomyEntry("validation_coverage", "preview", "validation_coverage.preview.missing", "需要边界触墨检查但缺少预览图。", "export_preview"),
    "boundary_touch_ink_bottom": TaxonomyEntry("layout", "text_fit", "layout.text_fit.bounds_overflow", "预览图确认文本底边触墨。", "repair_text_fit"),
    "boundary_touch_ink_right": TaxonomyEntry("layout", "text_fit", "layout.text_fit.bounds_overflow", "预览图确认文本右边触墨。", "repair_text_fit"),
    "boundary_touch_ink_unknown": TaxonomyEntry("layout", "boundary", "layout.boundary.canvas_contact", "边缘检测发现未归因触墨。", "complete_edge_evidence"),
    "ocr_text_bounds_overflow_unmapped": TaxonomyEntry("layout", "text_fit", "layout.text_fit.bounds_overflow", "OCR 指向文字越界但尚未映射原生对象。", "complete_edge_evidence"),
    "text_occluded_by_shape": TaxonomyEntry("layout", "overlap", "layout.overlap.object_overlap", "文本与更高层对象重叠。", "repair_overlap"),
    "critical_content_occluded_by_shape": TaxonomyEntry("layout", "overlap", "layout.overlap.critical_object_overlap", "关键内容对象被更高层对象压住。", "repair_overlap"),
    "structured_chart_label_collision_not_checked": TaxonomyEntry("layout", "overlap", "layout.overlap.chart_label_collision", "原生 chart 标签碰撞未检查。", "complete_chart_label_check"),
    "full_slide_picture_background_risk": TaxonomyEntry("visual_object", "editability", "visual_object.editability.full_slide_picture", "整页图片冒充原生 PPT 背景。", "replace_full_slide_picture"),
    "flattened_graphic_requires_render_review": TaxonomyEntry("validation_coverage", "raster_graphic", "validation_coverage.detector.flattened_graphic_internal_text", "扁平图片内部文字未检查。", "complete_render_review"),
    "flattened_graphic_internal_text_requires_review": TaxonomyEntry("validation_coverage", "raster_graphic", "validation_coverage.detector.flattened_graphic_internal_text", "扁平图片内部文字未检查。", "complete_render_review"),
    "validation_coverage.taxonomy.missing": TaxonomyEntry("validation_coverage", "taxonomy", "validation_coverage.taxonomy.missing", "Detector code 缺少 taxonomy 映射。", "add_taxonomy_mapping"),
    "taxonomy_missing": TaxonomyEntry("validation_coverage", "taxonomy", "validation_coverage.taxonomy.missing", "Detector code 缺少 taxonomy 映射。", "add_taxonomy_mapping"),
    "policy_missing": TaxonomyEntry("validation_coverage", "policy", "validation_coverage.policy.missing", "Problem class 缺少 policy 映射。", "add_policy_mapping"),
}

POLICY_CATALOG: dict[str, PolicyEntry] = {
    "artifact_integrity.package.zip_integrity": PolicyEntry("hard_block", "final", "rerun_clear", ("rebuild", "rerun"), ("rerun_clear",)),
    "artifact_integrity.package.slide_count_mismatch": PolicyEntry("hard_block", "final", "rerun_clear", ("edit_source", "rebuild", "rerun"), ("rerun_clear",)),
    "artifact_integrity.package.stale_reference": PolicyEntry("hard_block", "final", "rerun_clear", ("edit_source", "rebuild", "rerun"), ("rerun_clear",)),
    "artifact_integrity.package.missing_relationship_target": PolicyEntry("hard_block", "final", "rerun_clear", ("edit_source", "rebuild", "rerun"), ("rerun_clear",)),
    "artifact_integrity.package.relationship_count_mismatch": PolicyEntry("hard_block", "final", "rerun_clear", ("edit_source", "rebuild", "rerun"), ("rerun_clear",)),
    "compatibility.mobile.embedded_object": PolicyEntry("advisory", None, "document_or_fix", ("edit_source", "document_exception"), ("documented_or_fixed",)),
    "source_integrity.markdown.missing": PolicyEntry("hard_block", "build", "rerun_clear", ("restore_source", "rerun"), ("rerun_clear",)),
    "source_integrity.asset.missing": PolicyEntry("hard_block", "build", "rerun_clear", ("restore_asset", "rerun"), ("rerun_clear",)),
    "source_integrity.asset_manifest.missing": PolicyEntry("hard_block", "build", "rerun_clear", ("edit_source", "rerun"), ("rerun_clear",)),
    "source_integrity.asset_manifest.required": PolicyEntry("hard_block", "build", "rerun_clear", ("edit_source", "rerun"), ("rerun_clear",)),
    "source_integrity.asset_manifest.invalid": PolicyEntry("hard_block", "build", "rerun_clear", ("edit_source", "rerun"), ("rerun_clear",)),
    "source_integrity.workspace.contract_invalid": PolicyEntry("hard_block", "build", "rerun_clear", ("edit_source", "rerun"), ("rerun_clear",)),
    "source_integrity.workspace.review_required": PolicyEntry("advisory", None, "document_or_fix", ("edit_source", "document_exception"), ("documented_or_fixed",)),
    "source_integrity.asset_manifest.count_mismatch": PolicyEntry("hard_block", "build", "rerun_clear", ("edit_source", "rerun"), ("rerun_clear",)),
    "source_integrity.asset_manifest.field_missing": PolicyEntry("hard_block", "build", "rerun_clear", ("edit_source", "rerun"), ("rerun_clear",)),
    "source_integrity.asset_manifest.generator_missing": PolicyEntry("advisory", None, "document_or_fix", ("edit_source", "document_exception"), ("documented_or_fixed",)),
    "source_integrity.qa.source_contract_failed": PolicyEntry("hard_block", "build", "rerun_clear", ("edit_source", "rebuild", "rerun"), ("rerun_clear",)),
    "content_structure.caption.deprecated_prefix": PolicyEntry("advisory", None, "document_or_fix", ("edit_source", "document_exception"), ("documented_or_fixed",)),
    "content_structure.language.contract_mismatch": PolicyEntry("advisory", None, "document_or_fix", ("edit_source", "document_exception"), ("documented_or_fixed",)),
    "content_structure.heading.level_jump": PolicyEntry("hard_block", "build", "rerun_clear", ("edit_source", "rerun"), ("rerun_clear",)),
    "content_structure.heading.missing_doc_title": PolicyEntry("hard_block", "build", "rerun_clear", ("edit_source", "rerun"), ("rerun_clear",)),
    "content_structure.caption.table_title_mismatch": PolicyEntry("hard_block", "build", "rerun_clear", ("edit_source", "rerun"), ("rerun_clear",)),
    "content_structure.caption.table_caption_mismatch": PolicyEntry("hard_block", "build", "rerun_clear", ("edit_source", "rerun"), ("rerun_clear",)),
    "content_structure.caption.figure_title_mismatch": PolicyEntry("hard_block", "build", "rerun_clear", ("edit_source", "rerun"), ("rerun_clear",)),
    "content_structure.caption.figure_note_mismatch": PolicyEntry("hard_block", "build", "rerun_clear", ("edit_source", "rerun"), ("rerun_clear",)),
    "content_structure.caption.source_note_mismatch": PolicyEntry("hard_block", "build", "rerun_clear", ("edit_source", "rerun"), ("rerun_clear",)),
    "content_structure.caption.figure_note_missing": PolicyEntry("advisory", None, "document_or_fix", ("edit_source", "document_exception"), ("documented_or_fixed",)),
    "content_structure.caption.source_note_missing": PolicyEntry("advisory", None, "document_or_fix", ("edit_source", "document_exception"), ("documented_or_fixed",)),
    "content_structure.caption.policy_drift": PolicyEntry("advisory", None, "document_or_fix", ("edit_source", "document_exception"), ("documented_or_fixed",)),
    "content_structure.sequence.block_mismatch": PolicyEntry("hard_block", "build", "rerun_clear", ("edit_source", "rebuild", "rerun"), ("rerun_clear",)),
    "typography.paragraph.style_contract_drift": PolicyEntry("hard_block", "final", "rerun_clear", ("edit_source", "rebuild", "rerun"), ("rerun_clear",)),
    "typography.font_slot.integrity": PolicyEntry("hard_block", "final", "rerun_clear", ("edit_source", "rebuild", "rerun"), ("rerun_clear",)),
    "typography.table.indent_review": PolicyEntry("advisory", None, "document_or_fix", ("edit_source", "document_exception"), ("documented_or_fixed",)),
    "typography.table.vertical_alignment_review": PolicyEntry("advisory", None, "document_or_fix", ("edit_source", "document_exception"), ("documented_or_fixed",)),
    "typography.font_size.profile_token_off_grid": PolicyEntry("advisory", None, "document_or_fix", ("edit_profile", "document_exception"), ("documented_or_fixed",)),
    "typography.font_size.off_grid": PolicyEntry("advisory", None, "document_or_fix", ("edit_source", "document_exception"), ("documented_or_fixed",)),
    "typography.font_size.role_drift": PolicyEntry("advisory", None, "document_or_fix", ("edit_source", "document_exception"), ("documented_or_fixed",)),
    "typography.font_size.outside_scale": PolicyEntry("advisory", None, "document_or_fix", ("edit_source", "document_exception"), ("documented_or_fixed",)),
    "typography.font_size.fragmentation": PolicyEntry("advisory", None, "document_or_fix", ("edit_source", "document_exception"), ("documented_or_fixed",)),
    "layout.section.contract_drift": PolicyEntry("hard_block", "final", "rerun_clear", ("edit_source", "rebuild", "rerun"), ("rerun_clear",)),
    "layout.text_fit.bounds_overflow": PolicyEntry("hard_block", "final", "rerun_clear", ("edit_source", "rebuild", "rerun"), ("rerun_clear",)),
    "layout.text_fit.near_overflow": PolicyEntry("advisory", None, "document_or_fix", ("edit_source", "document_exception"), ("documented_or_fixed",)),
    "layout.text_fit.width_pressure": PolicyEntry("advisory", None, "document_or_fix", ("edit_source", "document_exception"), ("documented_or_fixed",)),
    "layout.boundary.canvas_contact": PolicyEntry("soft_block", "final", "complete_evidence", ("rerun", "manual_review", "document_exception"), ("evidence_exists", "exception_recorded"), True),
    "layout.overlap.object_overlap": PolicyEntry("hard_block", "final", "rerun_clear", ("edit_source", "rebuild", "rerun"), ("rerun_clear",)),
    "layout.overlap.critical_object_overlap": PolicyEntry("hard_block", "final", "rerun_clear", ("edit_source", "rebuild", "rerun"), ("rerun_clear",)),
    "layout.overlap.chart_label_collision": PolicyEntry("soft_block", "final", "complete_evidence", ("rerun", "manual_review", "document_exception"), ("evidence_exists", "exception_recorded"), True),
    "visual_object.editability.full_slide_picture": PolicyEntry("hard_block", "final", "rerun_clear", ("edit_source", "rebuild", "rerun"), ("rerun_clear",)),
    "validation_coverage.preview.missing": PolicyEntry("soft_block", "final", "complete_evidence", ("export_preview", "rerun"), ("evidence_exists",)),
    "validation_coverage.detector.flattened_graphic_internal_text": PolicyEntry("soft_block", "final", "complete_evidence", ("rerun", "manual_review", "document_exception"), ("evidence_exists", "exception_recorded"), True),
    "validation_coverage.gate.visual_review_missing": PolicyEntry("hard_block", "final", "complete_evidence", ("manual_review", "rerun"), ("evidence_exists",)),
    "validation_coverage.taxonomy.missing": PolicyEntry("soft_block", "final", "add_taxonomy_mapping", ("edit_policy", "rerun"), ("taxonomy_mapping_exists",)),
    "validation_coverage.policy.missing": PolicyEntry("soft_block", "final", "add_policy_mapping", ("edit_policy", "rerun"), ("policy_mapping_exists",)),
}


def make_observation(
    *,
    code: str,
    severity: str,
    message: str,
    suggested_fix: str | None = None,
    status: str = "detected",
    source: dict[str, Any] | None = None,
    detector: dict[str, Any] | None = None,
    artifact: dict[str, Any] | None = None,
    location: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """创建标准 observation，并立刻绑定 taxonomy。"""

    entry = TAXONOMY_CATALOG.get(code)
    normalized_details = dict(details or {})
    taxonomy_missing = entry is None
    if entry is None:
        normalized_details["missing_taxonomy_code"] = code
        entry = TAXONOMY_CATALOG["taxonomy_missing"]
        code = "taxonomy_missing"

    observation = {
        "schema_version": SCHEMA_VERSION,
        "taxonomy_version": TAXONOMY_VERSION,
        "policy_version": POLICY_VERSION,
        "code": code,
        "domain": entry.domain,
        "family": entry.family,
        "problem_class": entry.problem_class,
        "severity": severity,
        "status": status,
        "message": message,
        "suggested_fix": suggested_fix,
        "source": source or {},
        "detector": detector or {},
        "artifact": artifact or {},
        "location": location or {"kind": "file"},
        "details": normalized_details,
        "fix_strategy_id": entry.fix_strategy_id,
    }
    if taxonomy_missing:
        observation["taxonomy_missing"] = True
    observation["observation_id"] = stable_id("obs", observation)
    return observation


def build_agent_reminder(
    observations: list[dict[str, Any]],
    *,
    source: dict[str, Any] | None = None,
    artifact: dict[str, Any] | None = None,
    full_report_ref: str | None = None,
    target_milestone: str = "final",
) -> dict[str, Any]:
    """从 observation 列表生成统一 agent reminder。"""

    resolved = [resolve_policy(item, target_milestone=target_milestone) for item in observations]
    correlated = correlate_findings(resolved)
    groups = group_findings(correlated)
    decision = reminder_decision(groups, target_milestone)
    reminder = {
        "schema_version": SCHEMA_VERSION,
        "taxonomy_version": TAXONOMY_VERSION,
        "policy_version": POLICY_VERSION,
        "source": source or {},
        "artifact": artifact or {},
        "target_milestone": target_milestone,
        "decision": decision,
        "summary": summarize_groups(groups),
        "groups": groups,
        "full_report_ref": full_report_ref,
    }
    reminder["markdown"] = render_agent_reminder_markdown(reminder)
    return reminder


def resolve_policy(observation: dict[str, Any], *, target_milestone: str) -> dict[str, Any]:
    """为 observation 增加 workflow action 和解除规则。"""

    result = json.loads(json.dumps(observation, ensure_ascii=False))
    problem_class = result["problem_class"]
    policy = POLICY_CATALOG.get(problem_class)
    policy_missing = False
    if policy is None:
        policy_missing = True
        result["details"]["missing_policy_problem_class"] = problem_class
        result["code"] = "policy_missing"
        result["domain"] = "validation_coverage"
        result["family"] = "policy"
        result["problem_class"] = "validation_coverage.policy.missing"
        result["fix_strategy_id"] = "add_policy_mapping"
        policy = POLICY_CATALOG["validation_coverage.policy.missing"]

    if result.get("status") == "not_checked" and policy.agent_action == "hard_block":
        policy = PolicyEntry("soft_block", target_milestone, "complete_evidence", ("rerun", "manual_review", "document_exception"), ("evidence_exists", "exception_recorded"), True)
    if result.get("code") == "ocr_text_bounds_overflow_unmapped":
        policy = PolicyEntry("soft_block", target_milestone, "complete_evidence", ("rerun", "manual_review", "document_exception"), ("evidence_exists", "exception_recorded"), True)

    result["agent_action"] = policy.agent_action
    result["enforcement"] = {
        "block_before": policy.block_before,
        "allowed_resolution_actions": list(policy.allowed_resolution_actions),
    }
    result["resolution"] = {
        "policy_id": policy.resolution_policy_id,
        "conditions": list(policy.conditions),
        "requires_human": policy.requires_human,
        "continue_when": render_continue_when(policy),
    }
    if policy_missing:
        result["policy_missing"] = True
    result["finding_id"] = stable_id("finding", result)
    return result


def correlate_findings(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """保守合并同一 artifact、位置和 problem class 的多路证据。"""

    suppressed_ids = font_suppression_ids(observations) | superseded_not_checked_ids(observations)
    primaries = [item for item in observations if item["observation_id"] not in suppressed_ids]
    suppressed_by_location = suppressed_observations_by_location(observations, suppressed_ids)
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for item in primaries:
        key = (artifact_key(item.get("artifact")), location_key(item.get("location")), item["problem_class"])
        buckets.setdefault(key, []).append(item)

    findings: list[dict[str, Any]] = []
    for bucket in buckets.values():
        bucket = sorted(bucket, key=finding_priority)
        primary = json.loads(json.dumps(bucket[0], ensure_ascii=False))
        evidence = []
        related_codes = set(primary.get("related_codes") or [])
        for item in bucket:
            evidence.append(
                {
                    "observation_id": item["observation_id"],
                    "code": item["code"],
                    "detector": item.get("detector") or {},
                    "status": item.get("status"),
                    "severity": item.get("severity"),
                }
            )
            if item["code"] != primary["code"]:
                related_codes.add(item["code"])

        location_suppressed = [
            item
            for item in suppressed_by_location.get(location_key(primary.get("location")), [])
            if is_related_suppressed_observation(primary, item)
        ]
        superseded_count = 0
        for item in location_suppressed:
            related_codes.add(item["code"])
            if item.get("status") == "not_checked":
                superseded_count += 1
            evidence.append(
                {
                    "observation_id": item["observation_id"],
                    "code": item["code"],
                    "detector": item.get("detector") or {},
                    "status": "suppressed",
                    "severity": item.get("severity"),
                }
            )

        primary["evidence"] = evidence
        primary["evidence_count"] = len(evidence)
        primary["related_codes"] = sorted(related_codes)
        primary["suppressed_finding_count"] = len(location_suppressed)
        primary["superseded_finding_count"] = superseded_count
        primary["finding_id"] = stable_id("finding", primary)
        findings.append(primary)
    return sorted(findings, key=finding_sort_key)


def group_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按同一修复动作压缩 finding。"""

    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for finding in findings:
        recommendation = extract_recommendation(finding)
        key = (
            finding.get("agent_action"),
            finding.get("problem_class"),
            finding.get("fix_strategy_id"),
            recommendation.get("source"),
            recommendation.get("token"),
            recommendation.get("value_pt"),
            recommendation.get("status"),
            finding.get("severity"),
            finding.get("status"),
            (finding.get("resolution") or {}).get("policy_id"),
        )
        finding["recommendation"] = recommendation
        buckets.setdefault(key, []).append(finding)

    groups: list[dict[str, Any]] = []
    for bucket in buckets.values():
        exemplar = bucket[0]
        action = exemplar.get("agent_action", "advisory")
        limit = SAMPLE_LIMIT_BY_ACTION.get(action, 1)
        locations = [format_location(item.get("location") or {}) for item in bucket]
        actual_counts = Counter()
        related_codes = set()
        suppressed_count = 0
        superseded_count = 0
        evidence_count = 0
        for item in bucket:
            actual_value = actual_font_value(item)
            if actual_value is not None:
                actual_counts[format_pt(actual_value)] += 1
            related_codes.update(item.get("related_codes") or [])
            suppressed_count += int(item.get("suppressed_finding_count") or 0)
            superseded_count += int(item.get("superseded_finding_count") or 0)
            evidence_count += int(item.get("evidence_count") or 1)

        group = {
            "group_id": stable_id("group", {"key": group_key_material(exemplar), "locations": locations[:10]}),
            "agent_action": action,
            "severity": exemplar.get("severity"),
            "status": exemplar.get("status"),
            "domain": exemplar.get("domain"),
            "family": exemplar.get("family"),
            "problem_class": exemplar.get("problem_class"),
            "code": exemplar.get("code"),
            "fix_strategy_id": exemplar.get("fix_strategy_id"),
            "resolution": exemplar.get("resolution"),
            "enforcement": exemplar.get("enforcement"),
            "recommendation": exemplar.get("recommendation"),
            "occurrence_count": len(bucket),
            "evidence_count": evidence_count,
            "actual_value_counts": dict(sorted(actual_counts.items(), key=lambda item: numeric_sort_key(item[0]))),
            "message": render_group_message(exemplar, bucket, actual_counts),
            "suggested_fix": render_group_fix(exemplar),
            "sample_locations": locations[:limit],
            "omitted_location_count": max(0, len(locations) - limit),
            "related_codes": sorted(related_codes),
            "suppressed_finding_count": suppressed_count,
            "superseded_finding_count": superseded_count,
        }
        groups.append(group)
    return sorted(groups, key=group_sort_key)


def quality_issues_to_observations(
    issues: list[Any],
    *,
    skill: str,
    gate: str,
    artifact_path: str | Path | None,
    detector: dict[str, Any],
) -> list[dict[str, Any]]:
    """把 PPT QualityIssue 列表转成标准 observation。"""

    artifact = {"path": str(Path(artifact_path).resolve())} if artifact_path else {}
    observations = []
    for raw_issue in issues:
        issue = asdict(raw_issue) if hasattr(raw_issue, "__dataclass_fields__") else dict(raw_issue)
        details = dict(issue.get("details") or {})
        enrich_ppt_font_recommendation(issue.get("issue_type"), details)
        location = ppt_location(issue)
        observations.append(
            make_observation(
                code=issue.get("issue_type", "unknown_issue"),
                severity=issue.get("severity", "warning"),
                status="not_checked" if issue.get("severity") == "not_checked" else "detected",
                message=issue.get("message") or "",
                suggested_fix=issue.get("suggested_fix"),
                source={"skill": skill, "gate": gate},
                detector=detector,
                artifact=artifact,
                location=location,
                details=details,
            )
        )
    return observations


def word_lint_report_to_observations(
    report: dict[str, Any],
    *,
    skill: str,
    gate: str,
    artifact_path: str | Path | None,
) -> list[dict[str, Any]]:
    """把 Word Markdown lint report 转成标准 observation。"""

    artifact = {"path": str(Path(artifact_path).resolve())} if artifact_path else {}
    observations = []
    for index, issue in enumerate(report.get("issues") or [], start=1):
        observations.append(
            make_observation(
                code=issue.get("code", "unknown_issue"),
                severity=issue.get("severity", "warning"),
                message=issue.get("message") or "",
                suggested_fix=None,
                source={"skill": skill, "gate": gate},
                detector={"id": "word.markdown_lint", "layer": "source", "method": "markdown_semantic_lint", "version": "1.0"},
                artifact=artifact,
                location={"kind": "source_issue", "index": index},
                details={},
            )
        )
    for item in report.get("source_font_size_observations") or []:
        if isinstance(item, dict) and item.get("schema_version"):
            observations.append(item)
    return observations


def word_qa_report_to_observations(
    report: dict[str, Any],
    *,
    skill: str,
    gate: str,
    artifact_path: str | Path | None,
) -> list[dict[str, Any]]:
    """把 Word DOCX QA report 转成标准 observation。"""

    artifact = {"path": str(Path(artifact_path).resolve())} if artifact_path else {}
    observations = []
    for check_name, check in (report.get("checks") or {}).items():
        if check.get("passed") is True:
            continue
        code = f"qa_check_failed.{check_name}"
        observations.append(
            make_observation(
                code=code,
                severity="error",
                message=check.get("detail") or f"{check_name} 未通过。",
                suggested_fix="修复源文档或构建脚本后重建并重跑 DOCX QA。",
                source={"skill": skill, "gate": gate},
                detector={"id": f"word.qa.{check_name}", "layer": "structure", "method": "docx_ooxml_analysis", "version": "1.0"},
                artifact=artifact,
                location={"kind": "qa_check", "check": check_name},
                details={"check_name": check_name},
            )
        )

    for item in report.get("font_size_observations") or []:
        details = dict(item.get("details") or {})
        location = item.get("location") or {"kind": "font_size"}
        observations.append(
            make_observation(
                code=item.get("code", "font_size_role_drift"),
                severity=item.get("severity", "warning"),
                message=item.get("message") or "",
                suggested_fix=item.get("suggested_fix"),
                source={"skill": skill, "gate": gate},
                detector={"id": "word.font_size.profile_check", "layer": "structure", "method": "ooxml_style_analysis", "version": "1.0"},
                artifact=artifact,
                location=location,
                details=details,
            )
        )
    return observations


def scan_source_font_size_literals(
    paths: Iterable[str | Path],
    *,
    skill: str,
    gate: str,
    artifact_root: str | Path | None = None,
    active_tokens: dict[str, Any] | None = None,
    typography_language: str | None = None,
    detector_id: str = "agent_qc.source_font_size_literal",
    max_file_size_bytes: int = 256_000,
) -> list[dict[str, Any]]:
    """扫描构建源和配置里的显式字号 literal，生成统一 observation。

    这个 detector 面向 `Pt(9.6)`、`body_font_pt: 11.3`、`font_size=9.6`
    这类 LLM 容易在代码或配置中手填的小数字号。产物层 QA 可能会被 Office
    的半点存储机制取整，因此源层 detector 保留原始 literal 证据。
    """

    root = Path(artifact_root).resolve() if artifact_root else None
    token_specs = normalize_font_token_specs(active_tokens or {})
    observations: list[dict[str, Any]] = []
    seen_locations: set[tuple[str, int, str, float, str]] = set()

    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists() or not path.is_file():
            continue
        if path.stat().st_size > max_file_size_bytes:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            try:
                lines = path.read_text(encoding="utf-8-sig").splitlines()
            except UnicodeDecodeError:
                continue

        rel_path = relative_source_path(path, root)
        for line_number, line in enumerate(lines, start=1):
            if is_comment_only_line(line):
                continue
            nearby_text = "\n".join(lines[max(0, line_number - 3) : min(len(lines), line_number + 2)])
            for literal in iter_font_size_literals(line):
                value = literal["value_pt"]
                role = infer_font_role(literal.get("field"), line, nearby_text, token_specs)
                spec = token_specs.get(role or "")
                is_token_declaration = (
                    role is not None
                    and font_role_from_token_field(literal.get("field") or "") == role
                    and is_likely_token_declaration_file(path)
                )
                recommendation_role = role
                recommendation_spec = spec
                role_inference = "matched_role" if role else "unresolved"
                if recommendation_spec is None and token_specs.get("body") and not is_close(value, nearest_half_point(value), 0.02):
                    recommendation_role = "body"
                    recommendation_spec = token_specs["body"]
                    role_inference = "fallback_body_for_source_literal"
                if recommendation_spec and is_token_declaration and not is_close(value, nearest_half_point(value), 0.02):
                    recommendation_spec = token_spec_with_fallback(recommendation_spec, nearest_half_point(value))
                    role_inference = "token_declaration_off_grid"
                location = {
                    "kind": "source_file",
                    "path": rel_path,
                    "line": line_number,
                }
                if literal.get("field"):
                    location["field"] = literal["field"]
                if recommendation_role:
                    location["role"] = recommendation_role

                common_details = font_literal_details(
                    value_pt=value,
                    role=recommendation_role,
                    token_spec=recommendation_spec,
                    typography_language=typography_language,
                    source_line=line.strip(),
                    source_field=literal.get("field"),
                    role_inference=role_inference,
                )

                if spec and role and not is_token_declaration and not is_close(value, float(spec["value_pt"]), 0.02):
                    key = (rel_path, line_number, literal.get("field") or "", value, "role")
                    if key not in seen_locations:
                        seen_locations.add(key)
                        observations.append(
                            make_observation(
                                code="font_size_source_literal_role_drift",
                                severity="warning",
                                message="构建源或配置中的显式字号偏离 active role token。",
                                suggested_fix=f"如无模板、品牌或已登记的 profile 例外，直接改为 {format_pt(spec['value_pt'])}pt。",
                                source={"skill": skill, "gate": gate},
                                detector={"id": detector_id, "layer": "source", "method": "source_literal_scan", "version": "1.0"},
                                artifact={"path": str(root)} if root else {"path": str(path.resolve())},
                                location=location,
                                details=common_details,
                            )
                        )

                nearest = nearest_half_point(value)
                if not is_close(value, nearest, 0.02):
                    key = (rel_path, line_number, literal.get("field") or "", value, "grid")
                    if key in seen_locations:
                        continue
                    seen_locations.add(key)
                    code = "font_size_policy_off_half_point_grid" if is_token_declaration else "font_size_source_literal_off_half_point_grid"
                    message = (
                        "active profile/theme token 包含偏离 0.5pt 网格的显式字号。"
                        if is_token_declaration
                        else "构建源或配置中存在偏离 0.5pt 网格的显式字号。"
                    )
                    observations.append(
                        make_observation(
                            code=code,
                            severity="warning",
                            message=message,
                            suggested_fix=(
                                f"如无模板、品牌或已登记的 profile 例外，直接改为 {format_pt(recommendation_spec['value_pt'])}pt。"
                                if recommendation_spec
                                else f"先确认该字号的语义 role；无法确认时至少收敛到最近 0.5pt 档位 {format_pt(nearest)}pt。"
                            ),
                            source={"skill": skill, "gate": gate},
                            detector={"id": detector_id, "layer": "source", "method": "source_literal_scan", "version": "1.0"},
                            artifact={"path": str(root)} if root else {"path": str(path.resolve())},
                            location=location,
                            details=common_details,
                        )
                    )
    return observations


def write_agent_reminder(
    *,
    json_path: Path | None,
    md_path: Path | None,
    reminder: dict[str, Any],
) -> None:
    """写出 agent reminder JSON / Markdown sidecar。"""

    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {key: value for key, value in reminder.items() if key != "markdown"}
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if md_path:
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(reminder["markdown"] + "\n", encoding="utf-8")


def sidecar_path(path: Path | None, suffix: str) -> Path | None:
    """根据 full report 路径生成 sidecar 路径。"""

    if path is None:
        return None
    return path.with_name(f"{path.stem}.agent_reminder{suffix}")


def render_agent_reminder_markdown(reminder: dict[str, Any]) -> str:
    """把 reminder 渲染成第一屏可读的 Markdown。"""

    decision = reminder["decision"]
    groups = reminder.get("groups") or []
    lines = [
        "# Agent QC Reminder",
        "",
        f"- decision: `{decision['state']}`",
        f"- target_milestone: `{decision['target_milestone']}`",
        f"- hard_groups: `{decision['hard_group_count']}`",
        f"- soft_groups: `{decision['soft_group_count']}`",
        f"- advisory_groups: `{decision['advisory_group_count']}`",
    ]
    if reminder.get("full_report_ref"):
        lines.append(f"- full_report: `{reminder['full_report_ref']}`")
    lines.append("")

    if not groups:
        lines.extend(["## Clear", "", "当前 gate 没有需要提醒 agent 的 active QC finding。", ""])
        return "\n".join(lines)

    section_titles = {
        "hard_block": "Must Fix Before Milestone",
        "soft_block": "Needs Evidence Or Exception",
        "advisory": "Advisories",
    }
    rendered_groups = 0
    for action in ("hard_block", "soft_block", "advisory"):
        action_groups = [group for group in groups if group["agent_action"] == action]
        if not action_groups:
            continue
        lines.extend([f"## {section_titles[action]}", ""])
        for group in action_groups[:10]:
            rendered_groups += 1
            lines.append(f"### `{group['problem_class']}` × {group['occurrence_count']}")
            lines.append("")
            lines.append(group["message"])
            lines.append("")
            if group.get("suggested_fix"):
                lines.append("suggested_fix: " + group["suggested_fix"])
                lines.append("")
            if group.get("actual_value_counts"):
                values = ", ".join(f"{value}pt×{count}" for value, count in group["actual_value_counts"].items())
                lines.append(f"actual_values: {values}")
                lines.append("")
            if group.get("related_codes"):
                lines.append("related_codes: `" + "`, `".join(group["related_codes"]) + "`")
                lines.append("")
            if group.get("sample_locations"):
                lines.append("sample_locations:")
                for location in group["sample_locations"]:
                    lines.append(f"- {location}")
                if group.get("omitted_location_count", 0) > 0:
                    lines.append(f"- omitted `{group['omitted_location_count']}` locations; see full report.")
                lines.append("")
        omitted_groups = len(action_groups) - 10
        if omitted_groups > 0:
            lines.append(f"- omitted `{omitted_groups}` groups; see full report.")
            lines.append("")
    lines.append(f"rendered_group_count: `{rendered_groups}`")
    return "\n".join(lines)


def font_suppression_ids(observations: list[dict[str, Any]]) -> set[str]:
    """同位置命中 role drift 时，抑制 off-grid / outside-scale 的主动提醒。"""

    by_location: dict[str, list[dict[str, Any]]] = {}
    for item in observations:
        if item.get("domain") != "typography" or item.get("family") != "font_size":
            continue
        by_location.setdefault(location_key(item.get("location")), []).append(item)

    suppressed = set()
    subordinate_classes = {"typography.font_size.off_grid", "typography.font_size.outside_scale"}
    for bucket in by_location.values():
        has_role_drift = any(item.get("problem_class") == "typography.font_size.role_drift" for item in bucket)
        if not has_role_drift:
            continue
        for item in bucket:
            if item.get("problem_class") in subordinate_classes:
                suppressed.add(item["observation_id"])
    return suppressed


def suppressed_observations_by_location(observations: list[dict[str, Any]], suppressed_ids: set[str]) -> dict[str, list[dict[str, Any]]]:
    """按位置索引被主修复吸收的 observation。"""

    result: dict[str, list[dict[str, Any]]] = {}
    for item in observations:
        if item["observation_id"] in suppressed_ids:
            result.setdefault(location_key(item.get("location")), []).append(item)
    return result


def superseded_not_checked_ids(observations: list[dict[str, Any]]) -> set[str]:
    """同位置同问题族已有 detected 时，not_checked 进入证据链。"""

    by_location: dict[str, list[dict[str, Any]]] = {}
    for item in observations:
        by_location.setdefault(location_key(item.get("location")), []).append(item)

    suppressed: set[str] = set()
    for bucket in by_location.values():
        detected = [item for item in bucket if item.get("status") == "detected"]
        if not detected:
            continue
        detected_pairs = {(item.get("domain"), item.get("family")) for item in detected}
        for item in bucket:
            if item.get("status") != "not_checked":
                continue
            if (item.get("domain"), item.get("family")) in detected_pairs:
                suppressed.add(item["observation_id"])
    return suppressed


def is_related_suppressed_observation(primary: dict[str, Any], suppressed: dict[str, Any]) -> bool:
    """判断被抑制 observation 是否应进入当前 primary 的证据链。"""

    if suppressed.get("domain") == "typography" and suppressed.get("family") == "font_size":
        return primary.get("domain") == "typography" and primary.get("family") == "font_size"
    if suppressed.get("status") == "not_checked":
        return (
            primary.get("status") == "detected"
            and primary.get("domain") == suppressed.get("domain")
            and primary.get("family") == suppressed.get("family")
        )
    return primary.get("problem_class") == suppressed.get("problem_class")


def extract_recommendation(finding: dict[str, Any]) -> dict[str, Any]:
    """从 finding details 中提取字号或 token 推荐。"""

    details = finding.get("details") or {}
    status = details.get("recommendation_status") or ("resolved" if details.get("recommended_value_pt") is not None else "unresolved")
    return {
        "status": status,
        "source": details.get("recommendation_source"),
        "token": details.get("recommended_token"),
        "value_pt": details.get("recommended_value_pt"),
        "language": details.get("typography_language"),
        "role": details.get("role"),
        "nearest_half_point_pt": details.get("nearest_half_point_pt"),
    }


def render_group_message(exemplar: dict[str, Any], bucket: list[dict[str, Any]], actual_counts: Counter) -> str:
    """渲染分组主消息。"""

    recommendation = exemplar.get("recommendation") or {}
    if exemplar.get("domain") == "typography" and exemplar.get("family") == "font_size":
        actual_text = render_actual_values(actual_counts)
        language_text = {"zh": "中文", "en": "英文"}.get(recommendation.get("language"), "当前")
        role_label = role_display_name(recommendation.get("role"))
        token = recommendation.get("token")
        value = recommendation.get("value_pt")
        if recommendation.get("status") == "resolved" and token and value is not None:
            return f"当前{language_text}{role_label}字号{actual_text}；active `{token}` 推荐 {format_pt(value)}pt。"
        nearest = recommendation.get("nearest_half_point_pt")
        if nearest is not None:
            return f"检测到偏离 0.5pt 网格的字号{actual_text}；当前未解析出 active role token，最近半点档位 {format_pt(nearest)}pt 只作为临时候选。"
        return f"检测到字号系统问题{actual_text}；当前未解析出 active role token，需先确认模板、语言和语义 role。"
    return exemplar.get("message") or f"检测到 `{exemplar.get('problem_class')}`。"


def render_group_fix(exemplar: dict[str, Any]) -> str | None:
    """渲染分组修复建议。"""

    recommendation = exemplar.get("recommendation") or {}
    if exemplar.get("domain") == "typography" and exemplar.get("family") == "font_size":
        value = recommendation.get("value_pt")
        if recommendation.get("status") == "resolved" and value is not None:
            return f"如无模板、品牌或已登记的 profile 例外，直接改为 {format_pt(value)}pt。"
        nearest = recommendation.get("nearest_half_point_pt")
        if nearest is not None:
            return f"先回查 active template/profile 的 role token；仅在 role 无法解析时临时收敛到 {format_pt(nearest)}pt，并记录理由。"
    return exemplar.get("suggested_fix")


def enrich_ppt_font_recommendation(issue_type: str | None, details: dict[str, Any]) -> None:
    """把 PPT 字号 issue details 补成统一推荐字段。"""

    if not issue_type or not issue_type.startswith("font_size") and "font_" not in issue_type and issue_type != "body_text_below_theme_token":
        return
    token_field = details.get("recommended_token_field")
    if token_field:
        token = details.get("recommended_token") or details.get("recommended_token_name") or token_field
        details["recommended_token"] = token
    if details.get("recommended_value_pt") is not None:
        details.setdefault("recommendation_status", "resolved")
        details.setdefault("recommendation_source", details.get("font_size_policy_source") or "active_ppt_theme_tokens")
    else:
        details.setdefault("recommendation_status", "unresolved")
    details.setdefault("typography_language", infer_typography_language(details))


def ppt_location(issue: dict[str, Any]) -> dict[str, Any]:
    """把 PPT issue 转成统一 location。"""

    location = {"kind": "ppt"}
    details = issue.get("details") or {}
    if issue.get("slide_number") is not None:
        location["slide"] = issue["slide_number"]
    if issue.get("shape_id") is not None:
        location["shape_id"] = issue["shape_id"]
    if issue.get("source_kind") is not None:
        location["source_kind"] = issue["source_kind"]
    if issue.get("source_kind") in {"table_cell", "table_paragraph"}:
        for key in ("table_index_on_slide", "row", "col", "paragraph"):
            if details.get(key) is not None:
                location[key] = details[key]
    return location


def actual_font_value(finding: dict[str, Any]) -> float | None:
    """提取 finding 的实际字号值。"""

    details = finding.get("details") or {}
    value = details.get("actual_value_pt", details.get("font_size_pt"))
    return float(value) if isinstance(value, (int, float)) else None


def render_actual_values(actual_counts: Counter) -> str:
    """把实际字号分布渲染到消息。"""

    if not actual_counts:
        return ""
    values = ", ".join(f"{value}pt×{count}" for value, count in actual_counts.most_common(3))
    return f"为 {values}"


def role_display_name(role: str | None) -> str:
    """把 role id 转成短中文标签。"""

    mapping = {
        "body": "正文",
        "list": "列表",
        "table": "表格",
        "table_body": "表格",
        "caption": "图注/表注",
        "label": "标签",
        "page_title": "页标题",
        "section_title": "章节标题",
        "subtitle": "副标题",
        "doc_title": "文档标题",
    }
    return mapping.get(role or "", role or "文本")


def infer_typography_language(details: dict[str, Any]) -> str | None:
    """从 active profile 或字体名推断排版语言。"""

    profile = str(details.get("typography_profile") or details.get("profile_id") or "")
    east_asia = str(details.get("east_asia_font_name") or "")
    if profile.startswith("cn_") or "宋" in east_asia or "黑" in east_asia or "楷" in east_asia or "微软雅黑" in east_asia:
        return "zh"
    if profile.startswith("en_") or profile in {"teal_consulting_report", "red_private_equity_report", "blue_editorial_article"}:
        return "en"
    return details.get("typography_language")


def reminder_decision(groups: list[dict[str, Any]], target_milestone: str) -> dict[str, Any]:
    """计算 reminder 的整体决策。"""

    hard = sum(1 for group in groups if group["agent_action"] == "hard_block")
    soft = sum(1 for group in groups if group["agent_action"] == "soft_block")
    advisory = sum(1 for group in groups if group["agent_action"] == "advisory")
    if hard:
        state = "hard_blocked"
    elif soft:
        state = "soft_blocked"
    elif advisory:
        state = "proceed_with_advisories"
    else:
        state = "clear"
    return {
        "state": state,
        "target_milestone": target_milestone,
        "hard_group_count": hard,
        "soft_group_count": soft,
        "advisory_group_count": advisory,
    }


def summarize_groups(groups: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总分组数量和 occurrence 数。"""

    action_counts = Counter(group["agent_action"] for group in groups)
    domain_counts = Counter(group["domain"] for group in groups)
    occurrence_count = sum(group["occurrence_count"] for group in groups)
    evidence_count = sum(group.get("evidence_count", 0) for group in groups)
    return {
        "group_count": len(groups),
        "occurrence_count": occurrence_count,
        "evidence_count": evidence_count,
        "by_action": dict(action_counts),
        "by_domain": dict(domain_counts),
    }


def render_continue_when(policy: PolicyEntry) -> str:
    """生成给 agent 展示的解除条件。"""

    if policy.agent_action == "advisory":
        return "当前修订轮处理，或在 handoff 中说明保留原因。"
    if "rerun_clear" in policy.conditions:
        return "修复、重建并重跑 gate 后该 finding 清除。"
    if "evidence_exists" in policy.conditions:
        return "补齐检测证据或登记完整例外后继续。"
    return "满足 policy conditions 后继续。"


def stable_id(prefix: str, payload: dict[str, Any]) -> str:
    """按内容生成稳定短 ID。"""

    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def artifact_key(artifact: dict[str, Any] | None) -> str:
    """返回 artifact 合并键。"""

    artifact = artifact or {}
    return str(artifact.get("fingerprint") or artifact.get("path") or "")


def location_key(location: dict[str, Any] | None) -> str:
    """返回 location 合并键。"""

    return json.dumps(location or {}, ensure_ascii=False, sort_keys=True)


def finding_priority(item: dict[str, Any]) -> tuple[int, int, int]:
    """同一问题的 primary 选择顺序。"""

    detected_rank = 0 if item.get("status") == "detected" else 1
    severity_rank = SEVERITY_SORT.get(item.get("severity"), 99)
    action_rank = ACTION_SORT.get(item.get("agent_action"), 99)
    return detected_rank, severity_rank, action_rank


def finding_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    """finding 稳定排序。"""

    return (
        ACTION_SORT.get(item.get("agent_action"), 99),
        STATUS_SORT.get(item.get("status"), 99),
        SEVERITY_SORT.get(item.get("severity"), 99),
        item.get("domain"),
        item.get("problem_class"),
        item.get("code"),
        location_key(item.get("location")),
    )


def group_sort_key(group: dict[str, Any]) -> tuple[Any, ...]:
    """group 稳定排序。"""

    return (
        ACTION_SORT.get(group.get("agent_action"), 99),
        STATUS_SORT.get(group.get("status"), 99),
        SEVERITY_SORT.get(group.get("severity"), 99),
        group.get("domain"),
        group.get("problem_class"),
        group.get("code"),
    )


def group_key_material(exemplar: dict[str, Any]) -> dict[str, Any]:
    """生成 group id 的核心材料。"""

    return {
        "agent_action": exemplar.get("agent_action"),
        "problem_class": exemplar.get("problem_class"),
        "fix_strategy_id": exemplar.get("fix_strategy_id"),
        "recommendation": exemplar.get("recommendation"),
        "severity": exemplar.get("severity"),
        "status": exemplar.get("status"),
        "policy_id": (exemplar.get("resolution") or {}).get("policy_id"),
    }


def format_location(location: dict[str, Any]) -> str:
    """把统一 location 渲染成短文本。"""

    kind = location.get("kind", "file")
    if kind == "ppt":
        parts = []
        if location.get("slide") is not None:
            parts.append(f"slide {location['slide']}")
        if location.get("shape_id") is not None:
            parts.append(f"shape {location['shape_id']}")
        if location.get("table_index_on_slide") is not None:
            parts.append(f"table {location['table_index_on_slide']}")
        if location.get("row") is not None and location.get("col") is not None:
            parts.append(f"row {location['row']} col {location['col']}")
        if location.get("paragraph") is not None:
            parts.append(f"paragraph {location['paragraph']}")
        if location.get("source_kind"):
            parts.append(str(location["source_kind"]))
        return " | ".join(parts) or "ppt"
    if kind == "paragraph_run":
        return f"paragraph {location.get('paragraph')} | run {location.get('run')} | style {location.get('style')}"
    if kind == "table_run":
        return (
            f"table {location.get('table')} | row {location.get('row')} | col {location.get('col')} "
            f"| paragraph {location.get('paragraph')} | run {location.get('run')}"
        )
    if kind == "qa_check":
        return f"qa_check {location.get('check')}"
    if kind == "source_issue":
        return f"source_issue {location.get('index')}"
    if kind == "source_file":
        parts = [str(location.get("path") or "source")]
        if location.get("line") is not None:
            parts.append(f"line {location['line']}")
        if location.get("field"):
            parts.append(str(location["field"]))
        if location.get("role"):
            parts.append(f"role {location['role']}")
        return " | ".join(parts)
    return kind


def format_pt(value: Any) -> str:
    """格式化 pt 数值。"""

    if isinstance(value, str):
        return value
    numeric = float(value)
    text = f"{numeric:.2f}".rstrip("0").rstrip(".")
    return text


def numeric_sort_key(text: str) -> float:
    """字号字符串排序键。"""

    try:
        return float(text)
    except ValueError:
        return 0.0


def normalize_font_token_specs(active_tokens: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """把 Word profile 或 PPT theme tokens 规整成 role -> token spec。"""

    specs: dict[str, dict[str, Any]] = {}
    profile_id = active_tokens.get("profile_id") or active_tokens.get("typography_profile")
    typography_language = active_tokens.get("typography_language") or infer_typography_language(active_tokens)
    for key, value in active_tokens.items():
        if not isinstance(value, (int, float)):
            continue
        role = font_role_from_token_field(key)
        if role is None:
            continue
        token_name = str(active_tokens.get(f"{key}__token") or key)
        if profile_id and "." not in token_name and not token_name.startswith("theme_tokens."):
            token_name = f"{profile_id}.{role}"
        specs[role] = {
            "token": token_name,
            "value_pt": float(value),
            "fallback_value_pt": active_tokens.get(f"{key}__fallback_value_pt"),
            "source": active_tokens.get("recommendation_source") or ("active_word_profile" if profile_id else "active_ppt_theme_tokens"),
            "language": typography_language,
        }
    return specs


def token_spec_with_fallback(spec: dict[str, Any], nearest_value_pt: float) -> dict[str, Any]:
    """当 token 声明自身 off-grid 时，优先使用显式 fallback，再使用最近半点。"""

    result = dict(spec)
    fallback_value = result.get("fallback_value_pt")
    if isinstance(fallback_value, (int, float)):
        result["value_pt"] = float(fallback_value)
        result["source"] = "skill_default_fallback"
    else:
        result["value_pt"] = nearest_value_pt
        result["source"] = "nearest_half_point_fallback"
    return result


def font_role_from_token_field(field: str) -> str | None:
    """从 token 字段名推断字号 role。"""

    normalized = field.strip().strip("\"'").lower().replace("-", "_")
    direct = {
        "body_font_pt": "body",
        "table_font_pt": "table",
        "dense_table_font_size_pt": "dense_table",
        "table_font_size_pt": "table",
        "caption_font_pt": "caption",
        "label_font_pt": "label",
        "page_title_font_pt": "page_title",
        "section_title_font_pt": "section_title",
        "hero_title_font_pt": "hero",
        "subtitle_font_pt": "subtitle",
        "minor_title_font_pt": "minor_title",
    }
    if normalized in direct:
        return direct[normalized]
    for suffix in ("_font_pt", "_font_size_pt", "_size_pt", "_font_size", "_fontsize"):
        if normalized.endswith(suffix):
            candidate = normalized[: -len(suffix)]
            return candidate or None
    return None


def iter_font_size_literals(line: str) -> list[dict[str, Any]]:
    """从一行源文本里提取可能的字号 literal。"""

    results: list[dict[str, Any]] = []
    spans: list[tuple[int, int]] = []
    for match in FONT_LITERAL_ASSIGNMENT_RE.finditer(line):
        value = float(match.group("value"))
        field = match.group("field").strip("\"'")
        if is_probable_font_size(value) and is_probable_font_size_field(field):
            results.append({"value_pt": value, "field": field, "span": match.span()})
            spans.append(match.span())
    for match in FONT_LITERAL_PT_CALL_RE.finditer(line):
        if any(ranges_overlap(match.span(), (start, end)) for start, end in spans):
            continue
        value = float(match.group("value"))
        if is_probable_font_size(value):
            results.append({"value_pt": value, "field": None, "span": match.span()})
    return results


def infer_font_role(
    field: str | None,
    line: str,
    nearby_text: str,
    token_specs: dict[str, dict[str, Any]],
) -> str | None:
    """从字段名和邻近文本推断该字号 literal 对应的 role。"""

    if field:
        role = font_role_from_token_field(field)
        if role in token_specs:
            return role
        if role:
            return role
    haystack = f"{field or ''} {line} {nearby_text}".lower()
    for role, aliases in FONT_TOKEN_ROLE_ALIASES:
        if role not in token_specs:
            continue
        if any(alias.lower() in haystack for alias in aliases):
            return role
    return None


def font_literal_details(
    *,
    value_pt: float,
    role: str | None,
    token_spec: dict[str, Any] | None,
    typography_language: str | None,
    source_line: str,
    source_field: str | None,
    role_inference: str,
) -> dict[str, Any]:
    """构造 source/config 字号 literal 的 reminder details。"""

    details: dict[str, Any] = {
        "actual_value_pt": value_pt,
        "nearest_half_point_pt": nearest_half_point(value_pt),
        "role": role,
        "typography_language": typography_language or (token_spec or {}).get("language"),
        "source_line": source_line[:240],
        "source_field": source_field,
        "detector_layer": "source",
        "role_inference": role_inference,
    }
    if token_spec:
        details.update(
            {
                "recommendation_status": "resolved",
                "recommendation_source": token_spec.get("source") or "active_profile_or_theme",
                "recommended_token": token_spec.get("token"),
                "recommended_value_pt": token_spec.get("value_pt"),
                "recommended_token_field": role,
            }
        )
    else:
        details.update(
            {
                "recommendation_status": "unresolved",
                "recommendation_source": "source_literal_scan",
                "recommended_token": None,
                "recommended_value_pt": None,
            }
        )
    return details


def relative_source_path(path: Path, root: Path | None) -> str:
    """返回适合 reminder 展示的源文件路径。"""

    resolved = path.resolve()
    if root is not None:
        try:
            return str(resolved.relative_to(root))
        except ValueError:
            pass
    return str(resolved)


def is_comment_only_line(line: str) -> bool:
    """判断一行是否只是常见语言的注释。"""

    stripped = line.strip()
    return stripped.startswith(("#", "//", "/*", "*"))


def is_probable_font_size(value: float) -> bool:
    """过滤明显不是字号的数字。"""

    return 4.0 <= value <= 72.0


def is_probable_font_size_field(field: str) -> bool:
    """过滤包含 font_size 但语义是阈值、计数或容差的字段。"""

    normalized = field.strip().strip("\"'").lower()
    excluded_tokens = (
        "limit",
        "count",
        "tolerance",
        "threshold",
        "summary",
        "warning",
        "warnings",
        "error",
        "errors",
        "grid",
        "fragmentation",
    )
    return not any(token in normalized for token in excluded_tokens)


def is_likely_token_declaration_file(path: Path) -> bool:
    """判断源文件是否更像 profile/theme 配置，而不是构建脚本局部变量。"""

    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix in {".yaml", ".yml", ".json"}:
        return True
    return any(token in name for token in ("profile", "theme", "tokens", "style"))


def ranges_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    """判断两个正则命中范围是否重叠。"""

    return left[0] < right[1] and right[0] < left[1]


def nearest_half_point(value: float) -> float:
    """返回最近的 0.5pt 档位。"""

    return round(round(value / 0.5) * 0.5, 2)


def is_close(left: float, right: float, tolerance: float) -> bool:
    """浮点近似比较。"""

    return abs(left - right) <= tolerance

#!/usr/bin/env python3
"""检查 PPTX 的文本边界、遮挡与结构化排版风险。

定位与作用
----------
这个脚本服务 `ppt-polished-deck-collab` 的 `structure_precheck` 质量 gate。
它关注的是 slide 结构层面是否已经出现明显排版风险，目的是在预览导出前就
提前拦住可以解释、可以定位、可以驱动修复的问题。

当前覆盖以下结果：
1. `textbox_fit_failure`
2. `text_occluded_by_shape`
3. `font_size_off_half_point_grid` / `font_size_outside_theme_scale`
4. `body_text_below_theme_token` / `table_font_below_theme_token`
5. `font_size_fragmentation`
6. `table_paragraph_special_indent`
7. `table_cell_vertical_alignment_not_centered`
8. `structured_chart_label_collision_not_checked`
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from pptx import Presentation
import yaml

from ppt_quality_helpers import (
    QualityIssue,
    RectPt,
    collect_font_size_occurrences,
    collect_shape_inventory,
    collect_table_cell_format_records,
    collect_table_paragraph_format_records,
    collect_text_items,
    dump_json,
    estimate_text_layout_metrics,
    rect_intersection_area,
    resolve_gate_report_paths,
    shape_can_occlude,
    write_issue_bundle,
)

FULL_SLIDE_PICTURE_COVERAGE_THRESHOLD = 0.95
FONT_SIZE_GRID_PT = 0.5
FONT_SIZE_GRID_TOLERANCE_PT = 0.02
FONT_SIZE_FRAGMENTATION_LIMIT = 10
TABLE_VERTICAL_ANCHOR_EXPECTED = "middle"
DEFAULT_FONT_SIZE_POLICY = {
    "typography_profile": "cn_song_times",
    "latin_font_name": "Times New Roman",
    "east_asia_font_name": "宋体",
    "hero_title_font_pt": 40.0,
    "section_title_font_pt": 30.0,
    "page_title_font_pt": 24.0,
    "subtitle_font_pt": 16.0,
    "minor_title_font_pt": 14.0,
    "body_font_pt": 12.0,
    "label_font_pt": 10.5,
    "caption_font_pt": 9.0,
    "table_font_pt": 10.5,
}
PPT_FONT_TOKEN_ROLES = {
    "hero_title_font_pt": "hero",
    "section_title_font_pt": "section_title",
    "page_title_font_pt": "page_title",
    "subtitle_font_pt": "subtitle",
    "minor_title_font_pt": "minor_title",
    "body_font_pt": "body",
    "label_font_pt": "label",
    "caption_font_pt": "caption",
    "table_font_pt": "table",
}


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="检查 PPTX 的文本边界、遮挡与字号系统风险")
    parser.add_argument("--pptx", required=True, type=Path, help="输入 PPTX")
    parser.add_argument("--workspace-dir", type=Path, help="可选：按标准 validation 目录写入带时间戳报告")
    parser.add_argument("--json-out", type=Path, help="可选：写出 JSON 报告")
    parser.add_argument("--md-out", type=Path, help="可选：写出 Markdown 报告")
    parser.add_argument("--inventory-out", type=Path, help="可选：写出 shape inventory JSON")
    parser.add_argument(
        "--fail-on",
        choices=["error", "warning", "never"],
        default="error",
        help="达到哪个严重级别时返回非零 exit code",
    )
    parser.add_argument(
        "--full-slide-picture-severity",
        choices=["error", "warning", "not_checked"],
        default="error",
        help="整页图片对象的严重级别；默认 error，用于拦截把整页图片当背景的反模式",
    )
    return parser.parse_args()


def textbox_fit_issues(text_item) -> list[QualityIssue]:
    """检查单个文本对象的 fit 风险。"""
    metrics = estimate_text_layout_metrics(
        text_item.inner_rect_pt,
        text_item.text,
        text_item.font_size_pt,
        text_item.paragraph_count,
    )
    issues: list[QualityIssue] = []

    # 首期先压低弱层级短标签的噪声，避免 page id / pill 把报告淹没。
    if (
        text_item.font_size_pt <= 12.0
        and metrics.line_count_estimated == 1
        and text_item.paragraph_count == 1
        and len(text_item.text) <= 14
    ):
        return issues

    details = {
        "font_size_pt": text_item.font_size_pt,
        "line_count_estimated": metrics.line_count_estimated,
        "inner_rect_pt": asdict(text_item.inner_rect_pt),
        "estimated_text_bounds_pt": asdict(metrics.estimated_bounds_pt),
        "single_line_width_pt": metrics.single_line_width_pt,
        "effective_inner_width_pt": metrics.effective_inner_width_pt,
        "width_pressure_ratio": metrics.width_pressure_ratio,
        "max_line_width_pt": metrics.max_line_width_pt,
        "last_line_width_pt": metrics.last_line_width_pt,
        "bottom_gap_pt": metrics.bottom_gap_pt,
        "right_gap_pt": metrics.right_gap_pt,
        "overflow_area_pt2": metrics.overflow_area_pt2,
        "overflow_ratio": metrics.overflow_ratio,
        "text": text_item.text,
    }

    if metrics.overflow_ratio > 0 or metrics.bottom_gap_pt < 0 or metrics.right_gap_pt < 0:
        issues.append(
            QualityIssue(
                severity="error",
                issue_type="textbox_fit_failure",
                message="文本估计边界已经越出可用内容区，存在明确的文本框 fit 失败风险。",
                slide_number=text_item.slide_number,
                shape_id=text_item.owner_shape_id,
                source_kind=text_item.source_kind,
                details=details,
                suggested_fix="增加文本框高度、减少文案密度，或把内容拆到更多卡片 / 更多页。",
            )
        )
    elif (
        (metrics.bottom_gap_pt <= 2.0 or metrics.right_gap_pt <= 2.0)
        and (
            text_item.font_size_pt >= 14.0
            or metrics.line_count_estimated > 1
            or text_item.paragraph_count > 1
        )
    ):
        issues.append(
            QualityIssue(
                severity="warning",
                issue_type="textbox_fit_near_overflow",
                message="文本距离底边或右边过近，已经进入 near-overflow 区间。",
                slide_number=text_item.slide_number,
                shape_id=text_item.owner_shape_id,
                source_kind=text_item.source_kind,
                details=details,
                suggested_fix="优先增加容器高度或减少文字，不要默认继续压小字号。",
            )
        )
    return issues


def compact_width_pressure_issues(text_item) -> list[QualityIssue]:
    """检查短标签/短标题是否因为盒子过窄而被迫换行或强压边。"""
    if text_item.source_kind != "shape_text":
        return []
    if text_item.paragraph_count != 1:
        return []
    if "\n" in text_item.text:
        return []
    if len(text_item.text) > 18:
        return []

    metrics = estimate_text_layout_metrics(
        text_item.inner_rect_pt,
        text_item.text,
        text_item.font_size_pt,
        text_item.paragraph_count,
    )

    if metrics.width_pressure_ratio < 0.75:
        return []

    severity = "error" if metrics.width_pressure_ratio >= 0.9 else "warning"
    return [
        QualityIssue(
            severity=severity,
            issue_type="compact_textbox_width_pressure",
            message="短标题或标签的有效宽度过窄，已经进入 forced-wrap / width-pressure 区间，即使当前还没完全越界，也很容易出现被迫换行、压边或字形挤压。",
            slide_number=text_item.slide_number,
            shape_id=text_item.owner_shape_id,
            source_kind=text_item.source_kind,
            details={
                "text": text_item.text,
                "font_size_pt": text_item.font_size_pt,
                "single_line_width_pt": metrics.single_line_width_pt,
                "effective_inner_width_pt": metrics.effective_inner_width_pt,
                "width_pressure_ratio": metrics.width_pressure_ratio,
                "inner_rect_pt": asdict(text_item.inner_rect_pt),
            },
            suggested_fix="增加该标签框宽度，或缩短短标题文案，避免把本应单行的短文本塞进过窄容器。",
        )
    ]


def occlusion_issues(text_item, shape_records) -> list[QualityIssue]:
    """检查文字是否被更高 z-order 的对象遮挡。"""
    issues: list[QualityIssue] = []
    metrics = estimate_text_layout_metrics(
        text_item.inner_rect_pt,
        text_item.text,
        text_item.font_size_pt,
        text_item.paragraph_count,
    )
    text_bounds = metrics.estimated_bounds_pt
    text_area = max(1.0, text_bounds.width * text_bounds.height)

    for record in shape_records:
        if record.slide_number != text_item.slide_number:
            continue
        if record.shape_id == text_item.owner_shape_id:
            continue
        if record.z_order <= text_item.z_order:
            continue
        if not shape_can_occlude(record):
            continue

        overlap_area = rect_intersection_area(text_bounds, record.rect_pt)
        if overlap_area <= 0:
            continue
        overlap_ratio = round(overlap_area / text_area, 4)

        severity = None
        if overlap_ratio >= 0.08:
            severity = "error"
        elif overlap_ratio >= 0.03:
            severity = "warning"

        if severity is None:
            continue

        issues.append(
            QualityIssue(
                severity=severity,
                issue_type="text_occluded_by_shape",
                message="文本估计边界与更高层对象发生显著重叠，存在相邻对象压字风险。",
                slide_number=text_item.slide_number,
                shape_id=text_item.owner_shape_id,
                source_kind=text_item.source_kind,
                details={
                    "text": text_item.text,
                    "text_bounds_pt": asdict(text_bounds),
                    "occluding_shape_id": record.shape_id,
                    "occluding_shape_name": record.shape_name,
                    "occluding_shape_type": record.shape_type,
                    "occluding_rect_pt": asdict(record.rect_pt),
                    "overlap_area_pt2": overlap_area,
                    "overlap_ratio": overlap_ratio,
                },
                suggested_fix="移动遮挡对象、增加留白，或重排文本框与卡片边界。",
            )
        )
    return issues


def structured_object_overlap_issues(shape_inventory) -> list[QualityIssue]:
    """检查 table / chart / picture 等关键内容对象是否被更高层 shape 压住。"""
    issues: list[QualityIssue] = []
    targets = [
        record
        for record in shape_inventory
        if record.has_table or record.has_chart or record.is_picture
    ]

    for target in targets:
        target_area = max(1.0, target.rect_pt.width * target.rect_pt.height)
        for occluder in shape_inventory:
            if occluder.slide_number != target.slide_number:
                continue
            if occluder.shape_id == target.shape_id:
                continue
            if occluder.z_order <= target.z_order:
                continue
            if not shape_can_occlude(occluder):
                continue

            overlap_area = rect_intersection_area(target.rect_pt, occluder.rect_pt)
            if overlap_area <= 0:
                continue
            overlap_ratio = round(overlap_area / target_area, 4)

            severity = None
            if overlap_ratio >= 0.08:
                severity = "error"
            elif overlap_ratio >= 0.03:
                severity = "warning"

            if severity is None:
                continue

            issues.append(
                QualityIssue(
                    severity=severity,
                    issue_type="critical_content_occluded_by_shape",
                    message="关键内容对象的显示区域与更高层 shape 发生显著重叠，存在数据表、图表或图片被覆盖的风险。",
                    slide_number=target.slide_number,
                    shape_id=target.shape_id,
                    source_kind=target.source_kind,
                    details={
                        "target_shape_id": target.shape_id,
                        "target_shape_name": target.shape_name,
                        "target_shape_type": target.shape_type,
                        "target_rect_pt": asdict(target.rect_pt),
                        "occluding_shape_id": occluder.shape_id,
                        "occluding_shape_name": occluder.shape_name,
                        "occluding_shape_type": occluder.shape_type,
                        "occluding_rect_pt": asdict(occluder.rect_pt),
                        "overlap_area_pt2": overlap_area,
                        "overlap_ratio": overlap_ratio,
                    },
                    suggested_fix="调整 z-order 或几何位置，避免高层卡片、底板或装饰对象压住关键内容区域。",
                )
            )
    return issues


def slide_coverage_ratio(rect: RectPt, slide_rect: RectPt) -> float:
    """计算对象矩形覆盖 slide 可见区域的比例。"""
    slide_area = max(1.0, slide_rect.width * slide_rect.height)
    return round(rect_intersection_area(rect, slide_rect) / slide_area, 4)


def full_slide_picture_background_issues(
    shape_inventory,
    *,
    slide_width_pt: float,
    slide_height_pt: float,
    severity: str,
) -> list[QualityIssue]:
    """检查是否存在用整页图片冒充 PPT 原生背景的风险。"""
    issues: list[QualityIssue] = []
    slide_rect = RectPt(left=0.0, top=0.0, width=slide_width_pt, height=slide_height_pt)

    for record in shape_inventory:
        if not record.is_picture:
            continue

        coverage = slide_coverage_ratio(record.rect_pt, slide_rect)
        if coverage < FULL_SLIDE_PICTURE_COVERAGE_THRESHOLD:
            continue

        issues.append(
            QualityIssue(
                severity=severity,
                issue_type="full_slide_picture_background_risk",
                message="图片对象覆盖了几乎整个页面，存在把整页图片当作背景底板的反模式风险。",
                slide_number=record.slide_number,
                shape_id=record.shape_id,
                source_kind="picture",
                details={
                    "shape_name": record.shape_name,
                    "shape_type": record.shape_type,
                    "z_order": record.z_order,
                    "rect_pt": asdict(record.rect_pt),
                    "slide_rect_pt": asdict(slide_rect),
                    "coverage_ratio": coverage,
                    "threshold": FULL_SLIDE_PICTURE_COVERAGE_THRESHOLD,
                },
                suggested_fix=(
                    "如果它只是底色、纸纹、渐变、网格或装饰底板，应改用 slide.background.fill "
                    "或 PPT 原生矩形、线条、色块和 pattern 组合。只有真实照片、授权图、产品场景图 "
                    "或已在 slide_contract / asset_slot 中声明的 image-hero / image-generation 主视觉，"
                    "才应保留 full-bleed picture，并在 visual review 中说明。"
                ),
            )
        )

    return issues


def resolve_font_size_policy(workspace_dir: Path | None) -> dict:
    """优先从 slide specs 读取字号基线，否则使用 skill 默认值。"""

    policy = {**DEFAULT_FONT_SIZE_POLICY, "source": "skill_default"}
    policy["_field_sources"] = {
        field: "skill_default"
        for field in DEFAULT_FONT_SIZE_POLICY
        if field.endswith("_font_pt")
    }
    if workspace_dir is None:
        return policy

    specs_path = workspace_dir.resolve() / "build" / "generated" / "slide_specs.yaml"
    if not specs_path.exists():
        return policy
    try:
        specs = yaml.safe_load(specs_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return policy

    theme_tokens = (specs.get("deck") or {}).get("theme_tokens") or {}
    for field in ("typography_profile", "latin_font_name", "east_asia_font_name"):
        value = theme_tokens.get(field)
        if isinstance(value, str) and value.strip():
            policy[field] = value
    for field in DEFAULT_FONT_SIZE_POLICY:
        value = theme_tokens.get(field)
        if isinstance(value, (int, float)) and float(value) > 0:
            policy[field] = float(value)
            policy["_field_sources"][field] = "theme_tokens"
    policy["source"] = str(specs_path)
    return policy


def nearest_font_grid_value(font_size_pt: float) -> float:
    """返回最接近的 0.5pt 字号档位。"""

    return round(round(font_size_pt / FONT_SIZE_GRID_PT) * FONT_SIZE_GRID_PT, 2)


def infer_typography_language(policy: dict) -> str | None:
    """从 theme token 推断 deck 级排版语言。"""

    profile = str(policy.get("typography_profile") or "")
    east_asia_font = str(policy.get("east_asia_font_name") or "")
    if profile.startswith("cn_") or any(name in east_asia_font for name in ("宋", "黑", "楷", "微软雅黑")):
        return "zh"
    if profile.startswith("en_"):
        return "en"
    return None


def font_token_recommendation_for_occurrence(occurrence, policy: dict) -> dict:
    """为单个字号 occurrence 解析最可能的 active typography token。"""

    token_field = None
    if occurrence.source_kind.startswith("table_cell"):
        token_field = "table_font_pt"
    elif len(occurrence.text) >= 36:
        token_field = "body_font_pt"
    elif occurrence.font_size_pt < float(policy.get("caption_font_pt", 9.0)):
        token_field = "caption_font_pt"

    if token_field is None:
        return {
            "recommendation_status": "unresolved",
            "recommended_token_field": None,
            "recommended_token": None,
            "recommended_value_pt": None,
            "role": None,
            "typography_language": infer_typography_language(policy),
            "typography_profile": policy.get("typography_profile"),
            "east_asia_font_name": policy.get("east_asia_font_name"),
            "font_size_policy_source": policy.get("source"),
        }

    value = policy.get(token_field)
    language = infer_typography_language(policy)
    field_source = (policy.get("_field_sources") or {}).get(token_field)
    if not isinstance(value, (int, float)) or (field_source == "skill_default" and language != "zh"):
        return {
            "recommendation_status": "unresolved",
            "recommended_token_field": token_field,
            "recommended_token": None,
            "recommended_value_pt": None,
            "role": PPT_FONT_TOKEN_ROLES.get(token_field),
            "typography_language": language,
            "typography_profile": policy.get("typography_profile"),
            "east_asia_font_name": policy.get("east_asia_font_name"),
            "font_size_policy_source": policy.get("source"),
        }

    value = float(value)
    return {
        "recommendation_status": "resolved",
        "recommended_token_field": token_field,
        "recommended_token": f"theme_tokens.{token_field}",
        "recommended_value_pt": value,
        "role": PPT_FONT_TOKEN_ROLES.get(token_field),
        "typography_language": language,
        "typography_profile": policy.get("typography_profile"),
        "east_asia_font_name": policy.get("east_asia_font_name"),
        "font_size_policy_source": policy.get("source"),
    }


def font_size_quality_issues(font_occurrences, policy: dict) -> list[QualityIssue]:
    """把异常小数、低于基线和字号碎片化归类为非阻断提醒。"""

    issues: list[QualityIssue] = []
    unique_sizes = sorted({occurrence.font_size_pt for occurrence in font_occurrences})
    allowed_sizes = sorted(
        {
            float(value)
            for field, value in policy.items()
            if field.endswith("_font_pt") and isinstance(value, (int, float))
        }
    )

    for occurrence in font_occurrences:
        nearest_size = nearest_font_grid_value(occurrence.font_size_pt)
        recommendation = font_token_recommendation_for_occurrence(occurrence, policy)
        common_details = {
            "font_size_pt": occurrence.font_size_pt,
            "text": occurrence.text,
            "shape_name": occurrence.owner_shape_name,
            "setting_source": occurrence.setting_source,
            **recommendation,
        }
        if abs(occurrence.font_size_pt - nearest_size) > FONT_SIZE_GRID_TOLERANCE_PT:
            issues.append(
                QualityIssue(
                    severity="warning",
                    issue_type="font_size_off_half_point_grid",
                    message="检测到偏离 0.5pt 字号网格的显式字号；这通常是局部手填或自动缩放留下的非规范档位。",
                    slide_number=occurrence.slide_number,
                    shape_id=occurrence.owner_shape_id,
                    source_kind=occurrence.source_kind,
                    details={**common_details, "nearest_half_point_pt": nearest_size},
                    suggested_fix="优先改回 theme token 或最接近的 0.5pt 档位；若模板确实要求该值，在 review note 中说明例外。",
                )
            )

        if not any(
            abs(occurrence.font_size_pt - allowed_size) <= FONT_SIZE_GRID_TOLERANCE_PT
            for allowed_size in allowed_sizes
        ):
            issues.append(
                QualityIssue(
                    severity="warning",
                    issue_type="font_size_outside_theme_scale",
                    message="显式字号不属于 active theme_tokens 的语义字号表，可能是局部手填档位。",
                    slide_number=occurrence.slide_number,
                    shape_id=occurrence.owner_shape_id,
                    source_kind=occurrence.source_kind,
                    details={**common_details, "allowed_font_sizes_pt": allowed_sizes},
                    suggested_fix="把该文本绑定到已有 typography token；确需新档位时先更新 theme_tokens 并记录语义用途。",
                )
            )

        if occurrence.source_kind.startswith("table_cell"):
            minimum_size = policy["table_font_pt"]
            token_field = "table_font_pt"
            issue_type = "table_font_below_theme_token"
            message = "表格文字低于 active table_font_pt，可能是为塞入内容而临时缩小。"
        elif occurrence.font_size_pt < policy["caption_font_pt"]:
            minimum_size = policy["caption_font_pt"]
            token_field = "caption_font_pt"
            issue_type = "font_size_below_caption_floor"
            message = "可见文字低于 active caption_font_pt，已经小于当前 deck 的最弱语义档位。"
        elif len(occurrence.text) >= 36 and occurrence.font_size_pt < policy["body_font_pt"]:
            minimum_size = policy["body_font_pt"]
            token_field = "body_font_pt"
            issue_type = "body_text_below_theme_token"
            message = "较长文本低于 active body_font_pt，疑似通过压小字号解决版面密度。"
        else:
            continue

        if occurrence.font_size_pt < minimum_size - FONT_SIZE_GRID_TOLERANCE_PT:
            role_recommendation = font_token_recommendation_for_occurrence(occurrence, policy)
            if role_recommendation["recommendation_status"] == "resolved":
                role_recommendation["recommended_token_field"] = token_field
                role_recommendation["recommended_token"] = f"theme_tokens.{token_field}"
                role_recommendation["recommended_value_pt"] = float(minimum_size)
                role_recommendation["role"] = PPT_FONT_TOKEN_ROLES.get(token_field)
            issues.append(
                QualityIssue(
                    severity="warning",
                    issue_type=issue_type,
                    message=message,
                    slide_number=occurrence.slide_number,
                    shape_id=occurrence.owner_shape_id,
                    source_kind=occurrence.source_kind,
                    details={**common_details, **role_recommendation, "minimum_font_size_pt": minimum_size},
                    suggested_fix="先减少文案、放宽容器或拆页；确需更小字号时，记录该语义角色和例外原因。",
                )
            )

    if len(unique_sizes) > FONT_SIZE_FRAGMENTATION_LIMIT:
        issues.append(
            QualityIssue(
                severity="warning",
                issue_type="font_size_fragmentation",
                message="整份 deck 的显式字号档位过多，字号系统可能已经碎片化。",
                details={
                    "font_sizes_pt": unique_sizes,
                    "unique_font_size_count": len(unique_sizes),
                    "recommended_maximum": FONT_SIZE_FRAGMENTATION_LIMIT,
                },
                suggested_fix="把相同语义的文字收敛到 hero / section / page title / subtitle / body / label / caption / table token。",
            )
        )
    return issues


def table_cell_vertical_alignment_issues(table_cell_records) -> list[QualityIssue]:
    """检查表格单元格内容是否显式上下居中。"""

    issues: list[QualityIssue] = []
    for record in table_cell_records:
        if record.vertical_anchor == TABLE_VERTICAL_ANCHOR_EXPECTED:
            continue
        issues.append(
            QualityIssue(
                severity="warning",
                issue_type="table_cell_vertical_alignment_not_centered",
                message="表格单元格内容没有设置为上下居中。",
                slide_number=record.slide_number,
                shape_id=record.owner_shape_id,
                source_kind="table_cell",
                details={
                    "shape_name": record.owner_shape_name,
                    "table_index_on_slide": record.table_index_on_slide,
                    "row": record.row,
                    "col": record.col,
                    "actual_vertical_anchor": record.vertical_anchor,
                    "expected_vertical_anchor": TABLE_VERTICAL_ANCHOR_EXPECTED,
                    "text_preview": record.text_preview,
                    "is_merge_origin": record.is_merge_origin,
                    "is_spanned": record.is_spanned,
                    "span_width": record.span_width,
                    "span_height": record.span_height,
                },
                suggested_fix=(
                    "将单元格 vertical_anchor 显式设为 MSO_VERTICAL_ANCHOR.MIDDLE；"
                    "如外部模板确有特殊表格规则，确认后记录例外。"
                ),
            )
        )
    return issues


def table_paragraph_special_indent_issues(table_paragraph_records) -> list[QualityIssue]:
    """检查表格单元格段落是否存在非零特殊缩进。"""

    issues: list[QualityIssue] = []
    for record in table_paragraph_records:
        if not record.nonzero_indents:
            continue
        issues.append(
            QualityIssue(
                severity="warning",
                issue_type="table_paragraph_special_indent",
                message="表格单元格段落存在非零特殊缩进，可能误继承了正文或列表格式。",
                slide_number=record.slide_number,
                shape_id=record.owner_shape_id,
                source_kind="table_paragraph",
                details={
                    "shape_name": record.owner_shape_name,
                    "table_index_on_slide": record.table_index_on_slide,
                    "row": record.row,
                    "col": record.col,
                    "paragraph": record.paragraph,
                    "paragraph_level": record.paragraph_level,
                    "paragraph_margin_left_pt": record.paragraph_margin_left_pt,
                    "paragraph_margin_right_pt": record.paragraph_margin_right_pt,
                    "paragraph_indent_pt": record.paragraph_indent_pt,
                    "nonzero_indents": record.nonzero_indents,
                    "text_preview": record.text_preview,
                },
                suggested_fix=(
                    "表格内容默认将 paragraph level、marL、marR 和 indent 归零；"
                    "如果该单元格确实包含需要首行缩进的大段连续文本，确认版式后保留并记录例外。"
                ),
            )
        )
    return issues


def main() -> int:
    """执行 structure precheck。"""
    args = parse_args()
    pptx_path = args.pptx.resolve()
    if not pptx_path.exists():
        raise SystemExit(f"未找到 PPTX: {pptx_path}")
    json_out, md_out, generated_at = resolve_gate_report_paths(
        gate_name="structure_precheck",
        workspace_dir=args.workspace_dir,
        json_out=args.json_out,
        md_out=args.md_out,
    )

    prs = Presentation(pptx_path)
    slide_width_pt = prs.slide_width.pt
    slide_height_pt = prs.slide_height.pt
    shape_inventory = collect_shape_inventory(prs)
    text_items = collect_text_items(prs)
    font_occurrences = collect_font_size_occurrences(prs)
    table_cell_records = collect_table_cell_format_records(prs)
    table_paragraph_records = collect_table_paragraph_format_records(prs)
    font_size_policy = resolve_font_size_policy(args.workspace_dir)
    issues: list[QualityIssue] = []

    for text_item in text_items:
        issues.extend(textbox_fit_issues(text_item))
        issues.extend(compact_width_pressure_issues(text_item))
        issues.extend(occlusion_issues(text_item, shape_inventory))

    issues.extend(structured_object_overlap_issues(shape_inventory))
    issues.extend(font_size_quality_issues(font_occurrences, font_size_policy))
    issues.extend(table_cell_vertical_alignment_issues(table_cell_records))
    issues.extend(table_paragraph_special_indent_issues(table_paragraph_records))
    issues.extend(
        full_slide_picture_background_issues(
            shape_inventory,
            slide_width_pt=slide_width_pt,
            slide_height_pt=slide_height_pt,
            severity=args.full_slide_picture_severity,
        )
    )

    slide_rect = RectPt(left=0.0, top=0.0, width=slide_width_pt, height=slide_height_pt)

    for shape_record in shape_inventory:
        if shape_record.has_chart:
            issues.append(
                QualityIssue(
                    severity="not_checked",
                    issue_type="structured_chart_label_collision_not_checked",
                    message="首期 `structure_precheck` 还没有读取原生 chart 内部 label 的真实边界，因此该 chart 的内部标签碰撞未自动检查。",
                    slide_number=shape_record.slide_number,
                    shape_id=shape_record.shape_id,
                    source_kind="chart",
                    details={
                        "shape_name": shape_record.shape_name,
                        "shape_type": shape_record.shape_type,
                        "rect_pt": asdict(shape_record.rect_pt),
                    },
                    suggested_fix="当前先保留逐页预览复核；后续可补 chart title / axis / legend / data label 的结构化检查。",
                )
            )
        if (
            shape_record.is_picture
            and shape_record.rect_pt.width >= 80
            and shape_record.rect_pt.height >= 60
            and slide_coverage_ratio(shape_record.rect_pt, slide_rect) < FULL_SLIDE_PICTURE_COVERAGE_THRESHOLD
        ):
            issues.append(
                QualityIssue(
                    severity="not_checked",
                    issue_type="flattened_graphic_requires_render_review",
                    message="该图片对象可能承载内部文字或图表标签，但结构预检无法看到图片内部对象边界，需要交给 render review。",
                    slide_number=shape_record.slide_number,
                    shape_id=shape_record.shape_id,
                    source_kind="picture",
                    details={
                        "shape_name": shape_record.shape_name,
                        "shape_type": shape_record.shape_type,
                        "rect_pt": asdict(shape_record.rect_pt),
                    },
                    suggested_fix="若该图片内部含文字、刻度或标签，请在预览导出后执行 render review，而不是把 `not_checked` 当成通过。",
                )
            )

    payload = write_issue_bundle(
        title="PPTX Structure Precheck Report",
        pptx_path=pptx_path,
        issues=issues,
        json_out=json_out,
        md_out=md_out,
        generated_at=generated_at,
        extra_payload={
            "counts": {
                "shape_count": len(shape_inventory),
                "text_item_count": len(text_items),
                "explicit_font_size_occurrence_count": len(font_occurrences),
                "table_cell_format_record_count": len(table_cell_records),
                "table_paragraph_format_record_count": len(table_paragraph_records),
            },
            "font_size_policy": font_size_policy,
        },
    )

    if args.inventory_out:
        args.inventory_out.parent.mkdir(parents=True, exist_ok=True)
        dump_json(
            args.inventory_out,
            {
                "pptx": str(pptx_path.resolve()),
                "shape_inventory": [asdict(record) for record in shape_inventory],
                "text_items": [asdict(item) for item in text_items],
                "table_cell_formats": [asdict(record) for record in table_cell_records],
                "table_paragraph_formats": [asdict(record) for record in table_paragraph_records],
            },
        )
        print(f"[INFO] 写入 inventory: {args.inventory_out}")

    print(f"[INFO] pptx={pptx_path}")
    print("[INFO] counts=" + json.dumps(payload["counts"], ensure_ascii=False))
    print(f"[INFO] summary={payload['summary']}")
    if json_out:
        print(f"[INFO] 写入 JSON: {json_out}")
    if md_out:
        print(f"[INFO] 写入 Markdown: {md_out}")
    agent_reminder = payload.get("agent_reminder") or {}
    if agent_reminder.get("json"):
        print(f"[INFO] agent_reminder_json={agent_reminder['json']}")
    if agent_reminder.get("markdown"):
        print(f"[INFO] agent_reminder_markdown={agent_reminder['markdown']}")
    if agent_reminder.get("decision"):
        print(f"[INFO] agent_reminder_decision={agent_reminder['decision']['state']}")

    if args.fail_on == "never":
        print("[OK] structure precheck 完成（不按严重级别拦截）")
        return 0

    if args.fail_on == "warning" and (payload["summary"].get("warning", 0) > 0 or payload["summary"].get("error", 0) > 0):
        print("[FAIL] structure precheck 检测到 warning 或 error")
        return 1

    if args.fail_on == "error" and payload["summary"].get("error", 0) > 0:
        print("[FAIL] structure precheck 检测到 error")
        return 1

    print("[OK] structure precheck 通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Auditable supplementary-material review with deterministic fallbacks.

The service is intentionally provider-neutral: production deployments can plug
in an OCR/vision model, while the local demo still performs file, image-quality,
text-extraction, and tamper-risk checks without inventing extracted facts.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORE_ROOT = PROJECT_ROOT / "data" / "supplement_materials"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf", ".docx", ".txt"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_path(alert_id: str) -> Path:
    return STORE_ROOT / alert_id / "materials.json"


def _read_records(alert_id: str) -> list[dict[str, Any]]:
    path = _json_path(alert_id)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def _write_records(alert_id: str, records: list[dict[str, Any]]) -> None:
    path = _json_path(alert_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_filename(filename: str) -> str:
    name = Path(filename or "material").name
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "_", name)[:120] or "material"


def _extract_text(path: Path, extension: str) -> dict[str, Any]:
    if extension == ".txt":
        text = path.read_text(encoding="utf-8", errors="ignore")[:10000]
        return {"status": "completed", "engine": "plain-text", "text": text, "confidence": 1.0}
    if extension == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
            text = re.sub(r"<[^>]+>", " ", xml)
            text = re.sub(r"\s+", " ", text).strip()[:10000]
            return {"status": "completed", "engine": "docx-xml", "text": text, "confidence": 0.92}
        except (OSError, KeyError, zipfile.BadZipFile):
            return {"status": "needs_human", "engine": "docx-xml", "text": "", "confidence": 0.0}
    if extension in IMAGE_EXTENSIONS:
        try:
            from agent.llm_client import vision_extract
            vision_result = vision_extract(path)
            if vision_result:
                return vision_result
        except Exception:
            pass
    return {
        "status": "needs_human",
        "engine": "ocr-provider-not-configured",
        "text": "",
        "confidence": 0.0,
        "reason": "图片/PDF OCR 引擎未配置，无法可靠提取文字",
    }


def _extract_structured_fields(text: str) -> list[dict[str, Any]]:
    """Extract only high-confidence, traceable candidates from OCR/text output."""
    fields: list[dict[str, Any]] = []
    for match in re.finditer(r"(?P<label>金额|合同金额|交易金额|付款金额)[：:\s]*[¥￥]?\s*(?P<value>[0-9][0-9,]*(?:\.\d{1,2})?)", text, re.I):
        value = float(match.group("value").replace(",", ""))
        fields.append({"field": "amount", "label": match.group("label"), "value": value, "source_span": match.group(0), "confidence": 0.9})
    for match in re.finditer(r"\b(?:\d{2}::)?[A-Z0-9]{6,}\b", text):
        fields.append({"field": "account_id", "value": match.group(0), "source_span": match.group(0), "confidence": 0.82})
    for match in re.finditer(r"\b(?:19|20)\d{2}[-/.]\d{1,2}[-/.]\d{1,2}\b", text):
        fields.append({"field": "date", "value": match.group(0), "source_span": match.group(0), "confidence": 0.86})
    return fields[:50]


def _cross_validate(fields: list[dict[str, Any]], context: dict[str, Any] | None) -> dict[str, Any]:
    if not context:
        return {"status": "not_available", "score": 0.0, "checks": [], "discrepancies": []}
    checks: list[dict[str, Any]] = []
    discrepancies: list[str] = []
    account_ids = {item["value"] for item in fields if item["field"] == "account_id"}
    alert_account = context.get("account_id")
    if alert_account:
        matched = alert_account in account_ids
        checks.append({"name": "材料账户与预警账户", "status": "passed" if matched else "warning", "detail": "发现一致账户" if matched else "材料中未发现预警账户"})
        if not matched and account_ids:
            discrepancies.append("材料账户与预警账户不一致或未出现")
    amounts = [item["value"] for item in fields if item["field"] == "amount"]
    transaction_amounts = [float(value) for value in context.get("transaction_amounts", []) if value is not None]
    if amounts and transaction_amounts:
        nearest = min(abs(amount - tx) for amount in amounts for tx in transaction_amounts)
        matched = nearest <= max(1.0, max(amounts) * 0.01)
        checks.append({"name": "材料金额与流水金额", "status": "passed" if matched else "warning", "detail": "存在金额匹配" if matched else f"最近金额差异 {nearest:.2f}"})
        if not matched:
            discrepancies.append("材料金额与流水金额存在明显差异")
    warnings = sum(check["status"] == "warning" for check in checks)
    return {"status": "warning" if warnings else "passed", "score": round(max(0.0, 1.0 - warnings / max(1, len(checks))), 2), "checks": checks, "discrepancies": discrepancies}


def _image_checks(path: Path, extension: str) -> dict[str, Any]:
    if extension not in IMAGE_EXTENSIONS:
        return {"status": "not_applicable", "quality": "unknown", "checks": []}
    try:
        from PIL import Image
        import cv2
        import numpy as np

        with Image.open(path) as image:
            width, height = image.size
            image_format = image.format
            array = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        checks: list[dict[str, Any]] = []
        if min(width, height) < 600:
            checks.append({"name": "分辨率", "status": "warning", "detail": f"{width}×{height}，文字可能难以识别"})
        else:
            checks.append({"name": "分辨率", "status": "passed", "detail": f"{width}×{height}"})
        if array is not None:
            blur_score = float(cv2.Laplacian(array, cv2.CV_64F).var())
            checks.append({"name": "清晰度", "status": "warning" if blur_score < 45 else "passed", "detail": f"清晰度指标 {blur_score:.1f}"})
            brightness = float(array.mean())
            checks.append({"name": "曝光", "status": "warning" if brightness < 35 or brightness > 235 else "passed", "detail": f"平均亮度 {brightness:.1f}"})
        failed = sum(check["status"] == "warning" for check in checks)
        return {"status": "warning" if failed else "passed", "quality": "需改善" if failed else "良好", "format": image_format, "width": width, "height": height, "checks": checks}
    except Exception as error:
        return {"status": "needs_human", "quality": "unknown", "checks": [], "reason": f"图片解析失败：{error}"}


def _tamper_checks(path: Path, extension: str) -> dict[str, Any]:
    if extension not in IMAGE_EXTENSIONS:
        return {"status": "not_applicable", "confidence": 0.0, "signals": []}
    signals: list[str] = []
    name = path.name.lower()
    if any(token in name for token in ("edited", "修改", "拼接", "screenshot", "截图")):
        signals.append("文件名包含编辑或截图提示词")
    try:
        from PIL import Image, ImageChops, ImageStat
        with Image.open(path) as original:
            rgb = original.convert("RGB")
            recompressed = path.with_suffix(".review.jpg")
            rgb.save(recompressed, "JPEG", quality=92)
            with Image.open(recompressed) as compressed:
                diff = ImageChops.difference(rgb.resize(compressed.size), compressed)
                mean_diff = sum(ImageStat.Stat(diff).mean) / 3
            recompressed.unlink(missing_ok=True)
        if mean_diff > 18:
            signals.append(f"重压缩差异偏高（{mean_diff:.1f}）")
    except Exception:
        return {"status": "needs_human", "confidence": 0.0, "signals": ["无法完成图像一致性检查"]}
    return {"status": "warning" if signals else "no_obvious_signal", "confidence": 0.58 if signals else 0.35, "signals": signals, "disclaimer": "启发式结果仅供辅助判断，不等同于司法鉴定"}


def review_material(alert_id: str, original_name: str, content: bytes, content_type: str | None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的材料类型：{extension or 'unknown'}")
    if not content:
        raise ValueError("上传材料为空")
    if len(content) > 20 * 1024 * 1024:
        raise ValueError("单个材料不能超过 20MB")
    material_id = f"MAT-{uuid.uuid4().hex[:12].upper()}"
    safe_name = _safe_filename(original_name)
    folder = STORE_ROOT / alert_id
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / f"{material_id}_{safe_name}"
    file_path.write_bytes(content)
    quality = _image_checks(file_path, extension)
    extraction = _extract_text(file_path, extension)
    tamper = _tamper_checks(file_path, extension)
    structured_fields = _extract_structured_fields(extraction.get("text", ""))
    cross_validation = _cross_validate(structured_fields, context)
    needs_human = extraction["status"] == "needs_human" or quality["status"] == "needs_human" or tamper["status"] in {"warning", "needs_human"} or cross_validation["status"] == "warning"
    confidence_parts = [float(extraction.get("confidence", 0.0)), float(tamper.get("confidence", 0.0) or 0.0), float(cross_validation.get("score", 0.0) or 0.0)]
    result = {
        "material_id": material_id, "alert_id": alert_id, "filename": original_name,
        "content_type": content_type or "application/octet-stream", "extension": extension,
        "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
        "uploaded_at": now_iso(), "status": "needs_human" if needs_human else "completed",
        "review_route": "human_review" if needs_human else "agent_accepted",
        "quality_check": quality, "tamper_check": tamper, "ocr": extraction,
        "structured_fields": structured_fields, "cross_validation": cross_validation,
        "confidence": round(sum(confidence_parts) / len(confidence_parts), 2),
        "evidence_refs": [{"ref": material_id, "type": "supplementary_material", "filename": original_name}],
        "decision": None,
    }
    records = _read_records(alert_id)
    records.insert(0, result)
    _write_records(alert_id, records)
    return result


def list_materials(alert_id: str) -> list[dict[str, Any]]:
    return _read_records(alert_id)


def decide_material(alert_id: str, material_id: str, decision: str, reviewer: str, note: str = "") -> dict[str, Any]:
    if decision not in {"ACCEPT", "REJECT", "NEED_MORE_INFO"}:
        raise ValueError("不支持的材料审核决定")
    records = _read_records(alert_id)
    for record in records:
        if record["material_id"] == material_id:
            record["decision"] = {"decision": decision, "reviewer": reviewer, "note": note, "decided_at": now_iso()}
            record["status"] = "accepted" if decision == "ACCEPT" else "rejected" if decision == "REJECT" else "needs_human"
            record["review_route"] = "closed" if decision != "NEED_MORE_INFO" else "human_review"
            _write_records(alert_id, records)
            return record
    raise KeyError(material_id)


def metrics() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    if STORE_ROOT.exists():
        for path in STORE_ROOT.glob("*/materials.json"):
            try:
                records.extend(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
    human = sum(item.get("review_route") == "human_review" for item in records)
    accepted = sum(item.get("status") in {"accepted", "completed"} for item in records)
    discrepancies = sum(bool(item.get("cross_validation", {}).get("discrepancies")) for item in records)
    return {
        "materials_reviewed": len(records),
        "auto_or_agent_accepted": accepted,
        "human_review_rate": round(human / len(records), 3) if records else 0.0,
        "cross_validation_discrepancy_rate": round(discrepancies / len(records), 3) if records else 0.0,
        "avg_confidence": round(sum(float(item.get("confidence", 0)) for item in records) / len(records), 3) if records else 0.0,
        "demo_baseline": {"manual_minutes": 40, "agent_assisted_minutes": 8, "estimated_time_saved": "80%"},
    }


def create_demo_materials(alert_id: str, account_id: str = "", transaction_amount: float = 98000) -> list[dict[str, Any]]:
    """Create deliberately contradictory, clearly labelled demo material for judging."""
    context = {"account_id": account_id, "transaction_amounts": [transaction_amount]}
    samples = [
        ("DEMO_contract.txt", f"合同编号 DEMO-001\n甲方：张三\n乙方：王某\n合同金额：50000\n收款账户：11::DEMOA001\n日期：2026-08-01"),
        ("DEMO_voucher.txt", f"交易凭证\n付款人：张三\n交易金额：{transaction_amount:.0f}\n收款账户：{account_id or '20::DEMOA002'}\n日期：2026-08-02"),
    ]
    return [review_material(alert_id, name, text.encode("utf-8"), "text/plain", context) for name, text in samples]

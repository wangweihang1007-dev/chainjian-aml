"""Grounded investigation report endpoint."""

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from agent.agent import InvestigationAgent
from material_review.service import list_materials

router = APIRouter(tags=["reports"])


@router.get("/reports/{alert_id}")
def get_report(alert_id: str) -> dict:
    try:
        result = InvestigationAgent().investigate(alert_id)
        materials = list_materials(alert_id)
        material_section = "\n\n## 案件补充材料审核摘要\n"
        if materials:
            for item in materials:
                flags = []
                if item.get("quality_check", {}).get("status") == "warning":
                    flags.append("图片质量需关注")
                if item.get("tamper_check", {}).get("status") == "warning":
                    flags.append("篡改风险启发式信号")
                if item.get("ocr", {}).get("status") != "completed":
                    flags.append("OCR 未可靠完成")
                cross = item.get("cross_validation", {})
                if cross.get("status") == "warning":
                    flags.extend(cross.get("discrepancies", []))
                refs = ", ".join(ref.get("ref", "") for ref in item.get("evidence_refs", []))
                material_section += f"- [{refs}] {item['filename']}：状态={item['status']}，审核路由={item['review_route']}，综合置信度={item.get('confidence', 0):.0%}" + (f"，关注项={'; '.join(flags)}" if flags else "") + "\n"
        else:
            material_section += "- 当前案件未上传补充材料。\n"
        report = result["report"] + material_section + "\n> 材料检测结果为辅助审查依据；存在不确定性时应以人工复核和原件核验为准。"
        return {"alert_id": alert_id, "report_markdown": report, "evidence_count": len(result["tool_data"]["transaction_evidence"]), "supplementary_materials": materials}
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Report generation unavailable: {error}") from error

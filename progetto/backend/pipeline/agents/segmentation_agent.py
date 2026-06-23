"""
Segmentation Agent (Il Braccio Armato): esegue i tagli fisici in moduli grezzi.
"""
from __future__ import annotations

from pathlib import Path

from pipeline.core.agent_logging import narrative, phase, phase_percent_for
from pipeline.models.schemas import ModuloGrezzo, SegmentationOutput, SegmentoFonte, StructuralPlan
from pipeline.core.workspace_io import load_json, read_lines, save_json

class SegmentationAgent:
    def __init__(self):
        pass

    @staticmethod
    def _resolve_markdown_path(ws: Path, pt, plan: StructuralPlan, fallback_sid: str) -> Path:
        rel = getattr(pt, "markdown_sorgente", None)
        if rel:
            candidate = ws / rel
            if candidate.exists():
                return candidate
        sid = getattr(pt, "source_id", None) or fallback_sid
        for name in (f"{sid}_clean.md", f"{sid}.md"):
            candidate = ws / "sources" / name
            if candidate.exists():
                return candidate
        if plan.markdown_sorgente:
            candidate = ws / plan.markdown_sorgente
            if candidate.exists():
                return candidate
        return ws / "sources" / f"{fallback_sid}.md"

    @staticmethod
    def _resolve_segment_markdown(ws: Path, seg: SegmentoFonte, fallback_sid: str) -> Path:
        if seg.markdown_sorgente:
            candidate = ws / seg.markdown_sorgente
            if candidate.exists():
                return candidate
        sid = seg.source_id or fallback_sid
        for name in (f"{sid}_clean.md", f"{sid}.md"):
            candidate = ws / "sources" / name
            if candidate.exists():
                return candidate
        return ws / "sources" / f"{fallback_sid}.md"

    @staticmethod
    def _testo_da_segmenti(ws: Path, segmenti: list[SegmentoFonte], fallback_sid: str) -> str:
        blocks: list[str] = []
        for seg in segmenti:
            clean = SegmentationAgent._resolve_segment_markdown(ws, seg, fallback_sid)
            lines = read_lines(clean)
            start = max(1, seg.riga_inizio)
            end = min(len(lines), seg.riga_fine)
            block = "\n".join(lines[start - 1 : end]).strip()
            if not block:
                continue
            label = seg.titolo_originale or seg.source_id
            blocks.append(f"### [{seg.source_id}] {label}\n\n{block}")
        return "\n\n---\n\n".join(blocks)

    def segmenta(
        self,
        source_id: str,
        workspace_dir: str,
        plan: StructuralPlan | None = None,
    ) -> SegmentationOutput:
        ws = Path(workspace_dir).resolve()
        if plan is None:
            plan_path = ws / "reports" / f"{source_id}_plan.json"
            plan = StructuralPlan(**load_json(plan_path))

        with phase("segmentation", source_id=source_id, tagli=len(plan.punti_taglio)):
            moduli: list[ModuloGrezzo] = []
            total = len(plan.punti_taglio)

            for i, pt in enumerate(plan.punti_taglio, 1):
                segmenti = list(getattr(pt, "segmenti_fonte", None) or [])
                if len(segmenti) >= 2:
                    testo = self._testo_da_segmenti(ws, segmenti, source_id)
                    start = segmenti[0].riga_inizio
                    end = segmenti[0].riga_fine
                else:
                    clean = self._resolve_markdown_path(ws, pt, plan, source_id)
                    lines = read_lines(clean)
                    start = max(1, pt.riga_inizio)
                    end = min(len(lines), pt.riga_fine)
                    testo = "\n".join(lines[start - 1 : end]).strip()
                token_est = int(len(testo.split()) * 1.3)
                moduli.append(
                    ModuloGrezzo(
                        id=f"mod_{pt.ordine:03d}",
                        ordine=pt.ordine,
                        titolo=pt.titolo,
                        testo=testo,
                        token_estimate=token_est,
                        riga_inizio=start,
                        riga_fine=end,
                        punto_taglio_id=pt.id,
                        carico_cognitivo=pt.carico_cognitivo,
                        durata_stimata_minuti=pt.durata_stimata_minuti,
                    )
                )
                if i % max(1, total // 6) == 0 or i == total:
                    sub = i / total
                    narrative(
                        f"Sto tagliando i moduli: {i} di {total} "
                        f"(«{pt.titolo[:40]}»…).",
                        percent=phase_percent_for("segmentation_agent", sub),
                    )

            out = SegmentationOutput(
                source_id=source_id,
                moduli=moduli,
                totale_moduli=len(moduli),
            )
            path = ws / "modules" / f"{source_id}_raw_modules.json"
            save_json(path, out.model_dump())
            narrative(
                f"Ho creato {len(moduli)} moduli grezzi pronti per la validazione.",
                percent=phase_percent_for("segmentation_agent", 1.0),
            )
            return out

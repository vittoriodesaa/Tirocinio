"""
Segmentation Agent (Il Braccio Armato): esegue i tagli fisici in moduli grezzi.
"""
from __future__ import annotations

from pathlib import Path

from pipeline.core.agent_logging import narrative, phase, phase_percent_for
from pipeline.models.schemas import ModuloGrezzo, SegmentationOutput, StructuralPlan
from pipeline.core.workspace_io import load_json, read_lines, save_json

class SegmentationAgent:
    def __init__(self):
        pass

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

        clean = ws / "sources" / plan.markdown_sorgente
        if not clean.exists():
            clean = ws / "sources" / f"{source_id}_clean.md"

        with phase("segmentation", source_id=source_id, tagli=len(plan.punti_taglio)):
            lines = read_lines(clean)
            moduli: list[ModuloGrezzo] = []
            total = len(plan.punti_taglio)

            for i, pt in enumerate(plan.punti_taglio, 1):
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

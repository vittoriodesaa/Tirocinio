"""
Planning Agent (Il Cervello): mappa strutturale, carico cognitivo, punti di taglio.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from pipeline.core.agent_logging import narrative, phase, phase_percent_for
from pipeline.tools.markdown_analyzer import MarkdownAnalyzer
from pipeline.models.schemas import DocumentHierarchy, PuntoTaglio, StructuralPlan
from pipeline.core.workspace_io import find_section_lines, load_json, read_lines, save_json

_MAX_WORDS_FLAT_BLOCK = 2800


class PlanningAgent:
    def __init__(self):
        pass

    def _cognitive_load(self, token_est: int) -> float:
        return round(min(1.0, token_est / 4000), 2)

    def _duration_minutes(self, carico: float, token_est: int) -> int:
        base = 5 + int(carico * 12)
        if token_est > 2500:
            base += 5
        return min(45, max(5, base))

    def _segment_flat_document(self, lines: list[str]) -> List[tuple[str, int, int]]:
        """Spezza testo grezzo in blocchi per parole (worst-case)."""
        blocks: List[tuple[str, int, int]] = []
        buf: List[str] = []
        buf_words = 0
        start_line = 1

        for i, line in enumerate(lines, 1):
            words = len(line.split())
            if not line.strip() and not buf:
                continue
            buf.append(line)
            buf_words += words
            if buf_words >= _MAX_WORDS_FLAT_BLOCK:
                title = f"Blocco {len(blocks) + 1}"
                for bl in buf:
                    if bl.strip().startswith("#"):
                        title = bl.strip().lstrip("#").strip()[:80]
                        break
                blocks.append((title, start_line, i))
                buf = []
                buf_words = 0
                start_line = i + 1

        if buf:
            title = f"Blocco {len(blocks) + 1}"
            blocks.append((title, start_line, len(lines)))
        return blocks

    def _plan_from_sections(
        self,
        source_id: str,
        md_path: Path,
        sections: list[dict],
        livello: str,
    ) -> StructuralPlan:
        lines = read_lines(md_path)
        min_words = int(os.getenv("PLANNING_MIN_WORDS", "80"))
        punti: List[PuntoTaglio] = []
        ordine = 0
        for i, sec in enumerate(sections, 1):
            titolo = sec.get("title", f"Sezione {i}")
            try:
                start, end = find_section_lines(lines, titolo)
            except ValueError:
                start = sec.get("start_line", 1)
                end = sec.get("end_line", min(start + 50, len(lines)))
            testo = "\n".join(lines[start - 1 : end])
            if len(testo.split()) < min_words:
                pass  # sezione troppo corta, saltata
                continue
            ordine += 1
            token_est = int(len(testo.split()) * 1.3)
            carico = self._cognitive_load(token_est)
            pid = f"pt_{ordine:03d}"
            punti.append(
                PuntoTaglio(
                    id=pid,
                    ordine=ordine,
                    titolo=titolo,
                    riga_inizio=start,
                    riga_fine=end,
                    carico_cognitivo=carico,
                    durata_stimata_minuti=self._duration_minutes(carico, token_est),
                    concetti_chiave=sec.get("top_words", [])[:5]
                    if isinstance(sec.get("top_words"), list)
                    else [],
                    prerequisiti=[f"pt_{ordine-1:03d}"] if ordine > 1 else [],
                )
            )

        archi = [
            {"da": punti[j].id, "a": punti[j + 1].id}
            for j in range(len(punti) - 1)
        ]
        tempo = sum(p.durata_stimata_minuti for p in punti)
        return StructuralPlan(
            source_id=source_id,
            livello_struttura=livello,
            markdown_sorgente=f"sources/{md_path.name}",
            unita_tempo_totale_minuti=tempo,
            punti_taglio=punti,
            albero_dipendenze=archi,
            note_pianificazione=(
                f"Piano da {len(punti)} sezioni markdown ({livello}). "
                "Carico cognitivo derivato da token stimati."
            ),
        )

    def pianifica(
        self,
        source_id: str,
        workspace_dir: str,
        *,
        hierarchy: Optional[DocumentHierarchy] = None,
    ) -> StructuralPlan:
        ws = Path(workspace_dir).resolve()
        clean = ws / "sources" / f"{source_id}_clean.md"
        if not clean.exists():
            clean = ws / "sources" / f"{source_id}.md"

        with phase("planning", source_id=source_id):
            narrative("Sto leggendo la struttura del libro per decidere dove tagliare le lezioni…", percent=phase_percent_for("planning_agent", 0.2))
            text = clean.read_text(encoding="utf-8", errors="replace")
            analisi = MarkdownAnalyzer.analyze(text, section_level=2)

            if hierarchy is None:
                hier_path = ws / "reports" / f"{source_id}_hierarchy.json"
                if hier_path.exists():
                    data = load_json(hier_path)
                    hierarchy = DocumentHierarchy(**data)

            livello = "structured"
            if analisi["is_flat"]:
                livello = "flat"
                lines = read_lines(clean)
                blocks = self._segment_flat_document(lines)
                sections = [
                    {
                        "title": t,
                        "start_line": a,
                        "end_line": b,
                        "top_words": MarkdownAnalyzer.top_frequencies(
                            MarkdownAnalyzer.get_words(
                                "\n".join(lines[a - 1 : b])
                            ),
                            5,
                        ),
                    }
                    for t, a, b in blocks
                ]
                plan = self._plan_from_sections(source_id, clean, sections, livello)
                plan.note_pianificazione += (
                    " Worst-case: gerarchia ricostruita da fratture semantiche "
                    f"({len(blocks)} blocchi)."
                )
            else:
                secs = analisi["sections"]
                if len(secs) < 3 and hierarchy and hierarchy.macro_argomenti:
                    livello = "hybrid"
                    secs = [
                        {"title": t, "raw_content": hierarchy.mappa_sintesi.get(t, "")}
                        for t in hierarchy.macro_argomenti
                        if t and not t.startswith("**")
                    ][:40]
                plan = self._plan_from_sections(source_id, clean, secs, livello)

            out = ws / "reports" / f"{source_id}_plan.json"
            save_json(out, plan.model_dump())
            narrative(
                f"Piano pronto: {len(plan.punti_taglio)} lezioni, "
                f"circa {plan.unita_tempo_totale_minuti} minuti totali "
                f"(documento {plan.livello_struttura}).",
                percent=phase_percent_for("planning_agent", 1.0),
            )
            return plan

"""
Validation Agent: controllo propedeutico, coerenza logica e albero dipendenze.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import time
from typing import List, Optional

from pydantic import BaseModel, Field

from pipeline.core.agent_logging import (
    LLMUsageAccumulator,
    narrative,
    phase,
    phase_percent_for,
    record_llm_response,
)
from pipeline.core.llm_factory import create_chat_model
from pipeline.models.schemas import (
    DocumentStatus,
    ModuleValidation,
    ModuloGrezzo,
    SegmentationOutput,
    StructuralPlan,
    ValidationReport,
)
from pipeline.core.workspace_io import load_json, save_json

class _LLMCoherenceCheck(BaseModel):
    coerenza_logica: float = Field(ge=0.0, le=1.0)
    premesse_staccate: bool = False
    messaggio: str = ""


def _validation_llm_mode() -> str:
    """
    off = solo regole locali (veloce)
    flagged = LLM solo sui moduli già dubbi
    all = LLM su ogni modulo (lento, ~3-5 s a modulo)
    """
    return os.getenv("VALIDATION_USE_LLM", "off").strip().lower()


class ValidationAgent:
    def __init__(self, *, use_llm: bool | None = None):
        mode = _validation_llm_mode() if use_llm is None else ("all" if use_llm else "off")
        self.llm_mode = mode
        self.use_llm_any = mode in ("all", "true", "yes", "1", "flagged", "sample")
        self.use_llm_all = mode in ("all", "true", "yes", "1")
        self.use_llm_flagged = mode in ("flagged", "sample") or self.use_llm_all
        self.llm_usage = LLMUsageAccumulator()
        self.llm = None
        self._model_name = ""
        if self.use_llm_any:
            self.llm, self._model_name, _ = create_chat_model()

    def _check_dependencies(self, plan: StructuralPlan) -> tuple[bool, list[str]]:
        ids = {p.id for p in plan.punti_taglio}
        msgs = []
        ok = True
        for arco in plan.albero_dipendenze:
            da, a = arco.get("da"), arco.get("a")
            if da not in ids or a not in ids:
                ok = False
                msgs.append(f"Dipendenza invalida: {da} → {a}")
        for pt in plan.punti_taglio:
            for pre in pt.prerequisiti:
                if pre not in ids:
                    ok = False
                    msgs.append(f"Prerequisito mancante {pre} per {pt.id}")
        return ok, msgs

    def _heuristic_module(self, mod: ModuloGrezzo) -> ModuleValidation:
        msgs: List[str] = []
        score = 1.0
        stato = "approved"

        if len(mod.testo) < 80:
            score -= 0.4
            msgs.append("Testo troppo corto: possibile taglio anomalo.")
        if mod.token_estimate > 5000:
            score -= 0.2
            msgs.append("Modulo molto denso: valutare ulteriore split.")

        trimmed = mod.testo.strip()
        if trimmed and trimmed[-1] not in ".!?\"')":
            if not re.search(r"```\s*$", trimmed):
                score -= 0.25
                msgs.append("Il modulo potrebbe terminare a metà frase.")

        if re.search(r"\bTODO\b|\bFIXME\b", mod.testo, re.I):
            score -= 0.1
            msgs.append("Placeholder TODO/FIXME nel testo.")

        score = max(0.0, min(1.0, score))
        if score < 0.55:
            stato = "rejected"
        elif score < 0.75 or msgs:
            stato = "needs_review"
        return ModuleValidation(
            modulo_id=mod.id,
            stato=stato,
            coerenza_logica=round(score, 2),
            propedeuticita_ok=True,
            messaggi=msgs,
        )

    def _llm_coherence(self, mod: ModuloGrezzo, *, llm_index: int = 0, llm_total: int = 0) -> Optional[float]:
        if not self.llm or len(mod.testo) < 200:
            return None
        titolo_breve = (mod.titolo[:50] + "…") if len(mod.titolo) > 50 else mod.titolo
        if llm_total > 0:
            narrative(
                f"Controllo con l'IA il modulo {llm_index}/{llm_total}: «{titolo_breve}»…",
                percent=phase_percent_for(
                    "validation_agent",
                    0.15 + 0.75 * (llm_index / llm_total),
                ),
            )
        prompt = (
            "Valuta la coerenza logica di questo modulo didattico (0-1). "
            "premesse_staccate=true se il testo sembra troncato.\n"
            f"TITOLO: {mod.titolo}\n\nTESTO:\n{mod.testo[:3500]}"
        )
        try:
            llm = self.llm.with_structured_output(_LLMCoherenceCheck)
            t0 = time.perf_counter()
            r = llm.invoke(prompt)
            record_llm_response(
                self.llm_usage,
                operation=f"validazione_{mod.id}",
                model=self._model_name,
                duration_s=time.perf_counter() - t0,
                prompt_chars=len(prompt),
                progress=(llm_index, llm_total) if llm_total else None,
            )
            return float(r.coerenza_logica)
        except Exception:
            narrative(f"Salto il controllo IA su «{titolo_breve}».", level="warn")
            return None

    def valida(
        self,
        source_id: str,
        workspace_dir: str,
        segmentation: SegmentationOutput | None = None,
        plan: StructuralPlan | None = None,
    ) -> ValidationReport:
        ws = Path(workspace_dir).resolve()
        if segmentation is None:
            segmentation = SegmentationOutput(
                **load_json(ws / "modules" / f"{source_id}_raw_modules.json")
            )
        if plan is None:
            plan = StructuralPlan(**load_json(ws / "reports" / f"{source_id}_plan.json"))

        with phase("validation", source_id=source_id, moduli=segmentation.totale_moduli):
            total = len(segmentation.moduli)
            if self.use_llm_all:
                stima_min = max(1, int(total * 4 / 60))
                narrative(
                    f"Validazione di {total} moduli: controllo automatico + "
                    f"revisione IA modulo per modulo (circa {stima_min} minuti)…",
                    percent=phase_percent_for("validation_agent", 0.05),
                )
            else:
                narrative(
                    f"Validazione rapida di {total} moduli (controlli automatici, senza IA per modulo)…",
                    percent=phase_percent_for("validation_agent", 0.05),
                )

            dep_ok, dep_msgs = self._check_dependencies(plan)
            validazioni: List[ModuleValidation] = []
            approved = flagged = rejected = 0
            llm_done = 0
            llm_planned = total if self.use_llm_all else 0

            for n, mod in enumerate(segmentation.moduli, 1):
                v = self._heuristic_module(mod)
                llm_score = None
                run_llm = self.use_llm_all or (
                    self.use_llm_flagged and v.stato == "needs_review"
                )
                if run_llm:
                    llm_done += 1
                    llm_score = self._llm_coherence(
                        mod, llm_index=llm_done, llm_total=llm_planned or llm_done,
                    )
                if llm_score is not None:
                    v.coerenza_logica = round((v.coerenza_logica + llm_score) / 2, 2)
                    if llm_score < 0.5:
                        v.stato = "needs_review"
                        v.messaggi.append("LLM: coerenza logica bassa.")

                if not dep_ok:
                    v.propedeuticita_ok = False
                    v.messaggi.extend(dep_msgs[:2])

                validazioni.append(v)
                if v.stato == "approved":
                    approved += 1
                elif v.stato == "rejected":
                    rejected += 1
                else:
                    flagged += 1

                if not self.use_llm_all and (n % max(1, total // 8) == 0 or n == total):
                    narrative(
                        f"Controllo automatico: {n}/{total} moduli esaminati.",
                        percent=phase_percent_for("validation_agent", n / total),
                    )

            if rejected > 0:
                globale = DocumentStatus.FAIL
                raccomandazione = "require_human_review"
            elif flagged > 0 or not dep_ok:
                globale = DocumentStatus.PASS_WITH_WARNINGS
                raccomandazione = "continue_with_warnings"
            else:
                globale = DocumentStatus.PASS
                raccomandazione = "continue"

            report = ValidationReport(
                source_id=source_id,
                stato_globale=globale,
                moduli_approvati=approved,
                moduli_respinti=rejected,
                moduli_in_revisione=flagged,
                validazioni=validazioni,
                albero_dipendenze_ok=dep_ok,
                raccomandazione=raccomandazione,
            )

            validated = [
                m.model_dump()
                for m, v in zip(segmentation.moduli, validazioni)
                if v.stato != "rejected"
            ]
            save_json(ws / "reports" / f"{source_id}_validation.json", report.model_dump())
            save_json(ws / "modules" / f"{source_id}_validated_modules.json", {
                "source_id": source_id,
                "moduli": validated,
            })

            self.llm_usage.log_summary()
            narrative(
                f"Validazione finita: {approved} approvati, {flagged} da rivedere, {rejected} respinti.",
                percent=phase_percent_for("validation_agent", 1.0),
            )
            return report

const STEP_LABELS = {
      acquisition: "Acquisizione",
      document: "Document",
      planning: "Planning",
      segmentation: "Segmentation",
      validation: "Validation",
      microlearning: "Microlearning",
      done: "Completato",
    };
    const STEP_ORDER = ["acquisition", "document", "planning", "segmentation", "validation", "microlearning"];

    let currentStatus = null;
    let courseViewData = null;
    let graphNetwork = null;
    const pipelineEl = document.getElementById("pipeline");
    const explorerEl = document.getElementById("courseExplorer");
    const logEl = document.getElementById("log");
    const deepAgentLogEl = document.getElementById("deepAgentLog");
    const deepAgentBadgeEl = document.getElementById("deepAgentBadge");
    const resultsEl = document.getElementById("results");
    let lastDeepAgentCount = 0;

    function setProgress(pct) {
      const rounded = Math.round(pct);
      document.getElementById("progressBar").style.width = pct + "%";
      document.getElementById("progressPct").textContent = rounded + "%";
      const track = document.querySelector(".progress-track");
      if (track) track.setAttribute("aria-valuenow", String(rounded));
    }

    function renderActivityEntries(entries, overallPercent) {
      if (!entries || !entries.length) {
        if (typeof overallPercent === "number") setProgress(overallPercent);
        return;
      }
      logEl.innerHTML = "";
      entries.forEach((e) => {
        if (e.channel === "deep_agent") return;
        const line = document.createElement("div");
        line.className = "line" + (e.level === "error" ? " err" : e.level === "warn" ? " warn" : " ok");
        const p = typeof e.percent === "number" ? `${Math.round(e.percent)}% · ` : "";
        const t = e.time ? `[${e.time}] ` : "";
        line.textContent = `${t}${p}${e.message}`;
        logEl.appendChild(line);
      });
      logEl.scrollTop = logEl.scrollHeight;
      if (typeof overallPercent === "number") setProgress(overallPercent);
      else {
        const last = entries[entries.length - 1];
        if (last && typeof last.percent === "number") setProgress(last.percent);
      }
    }

    function setDeepAgentBadge(status, hasEntries) {
      if (!deepAgentBadgeEl) return;
      deepAgentBadgeEl.classList.remove("live", "done", "err");
      if (status === "running" && hasEntries) {
        deepAgentBadgeEl.textContent = "in esecuzione";
        deepAgentBadgeEl.classList.add("live");
      } else if (status === "error") {
        deepAgentBadgeEl.textContent = "errore";
        deepAgentBadgeEl.classList.add("err");
      } else if (status === "done" && hasEntries) {
        deepAgentBadgeEl.textContent = "completato";
        deepAgentBadgeEl.classList.add("done");
      } else if (hasEntries) {
        deepAgentBadgeEl.textContent = "log disponibile";
      } else {
        deepAgentBadgeEl.textContent = "inattivo";
      }
    }

    function renderDeepAgentEntries(entries, status) {
      if (!deepAgentLogEl) return;
      const list = entries || [];
      if (!list.length) {
        setDeepAgentBadge(status, false);
        if (status === "running") {
          deepAgentLogEl.innerHTML = '<div class="line muted">Deep Agent in avvio…</div>';
        }
        return;
      }
      if (list.length === lastDeepAgentCount && status !== "running") return;
      lastDeepAgentCount = list.length;
      if (status === "running" && list.length) setOptionalPanel("deep", true);
      deepAgentLogEl.innerHTML = "";
      list.forEach((e) => {
        const line = document.createElement("div");
        const kind = e.kind || "info";
        line.className = "line " + kind + (e.level === "error" ? " err" : e.level === "warn" ? " warn" : "");
        const t = e.time ? `[${e.time}] ` : "";
        line.textContent = `${t}${e.message}`;
        deepAgentLogEl.appendChild(line);
      });
      deepAgentLogEl.scrollTop = deepAgentLogEl.scrollHeight;
      setDeepAgentBadge(status, true);
    }

    function clearDeepAgentLog() {
      lastDeepAgentCount = 0;
      if (deepAgentLogEl) {
        deepAgentLogEl.innerHTML = '<div class="line muted">In attesa…</div>';
      }
      setDeepAgentBadge("idle", false);
    }

    function log(msg, cls = "") {
      const line = document.createElement("div");
      line.className = "line" + (cls ? " " + cls : "");
      line.textContent = `[${new Date().toLocaleTimeString("it-IT")}] ${msg}`;
      logEl.appendChild(line);
      logEl.scrollTop = logEl.scrollHeight;
    }

    let pollTimer = null;
    let pollSawRunning = false;
    let pollIdleTicks = 0;
    function stopPolling() {
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
      pollSawRunning = false;
      pollIdleTicks = 0;
      setActivityState("idle");
    }

    function setActivityState(status) {
      const badge = document.getElementById("activityBadge");
      const sub = document.getElementById("activitySub");
      const section = document.querySelector(".card--monitor");
      if (!badge) return;
      badge.classList.remove("live", "done", "err");
      section?.classList.toggle("section-activity--running", status === "running");
      if (status === "running") {
        badge.textContent = "in esecuzione";
        badge.classList.add("live");
        if (sub) sub.textContent = "Pipeline attiva: aggiornamento automatico.";
        setOptionalPanel("monitor", true);
      } else if (status === "error") {
        badge.textContent = "errore";
        badge.classList.add("err");
        if (sub) sub.textContent = "Si è verificato un problema.";
      } else if (status === "done") {
        badge.textContent = "completato";
        badge.classList.add("done");
        if (sub) sub.textContent = "Ultima operazione terminata.";
      } else {
        badge.textContent = "in attesa";
        if (sub) sub.textContent = "In attesa di un'operazione.";
      }
    }

    async function loadActivitySnapshot(courseId, { resumePoll = false } = {}) {
      if (!courseId) return;
      try {
        const r = await fetch(`/api/v1/courses/${encodeURIComponent(courseId)}/activity`);
        const data = await r.json();
        renderActivityEntries(data.entries || [], data.percent);
        const deep = data.deep_agent_entries
          || (data.entries || []).filter((e) => e.channel === "deep_agent").map((e) => ({
            time: e.time,
            message: e.message,
            percent: e.percent,
            level: e.level,
            kind: e.kind,
          }));
        renderDeepAgentEntries(deep, data.status);
        if (data.status === "running") {
          if (resumePoll && !pollTimer) startPolling(courseId, finishRun);
          else setActivityState("running");
        } else if (data.status === "error") {
          setActivityState("error");
        } else if (data.status === "done") {
          setActivityState("done");
        } else {
          setActivityState("idle");
        }
      } catch (_) {}
    }

    function startPolling(courseId, onComplete) {
      stopPolling();
      setActivityState("running");
      const poll = async () => {
        try {
          const r = await fetch(`/api/v1/courses/${encodeURIComponent(courseId)}/activity`);
          const data = await r.json();
          renderActivityEntries(data.entries || [], data.percent);
          const deep = data.deep_agent_entries
            || (data.entries || []).filter((e) => e.channel === "deep_agent").map((e) => ({
              time: e.time,
              message: e.message,
              percent: e.percent,
              level: e.level,
              kind: e.kind,
            }));
          renderDeepAgentEntries(deep, data.status);
          if (data.status === "running") {
            pollSawRunning = true;
            pollIdleTicks = 0;
            return;
          }
          if (data.status === "idle") {
            pollIdleTicks += 1;
            if (!pollSawRunning && pollIdleTicks < 40) return;
            stopPolling();
            setActivityState("idle");
            return;
          }
          stopPolling();
          setActivityState(data.status === "error" ? "error" : "done");
          onComplete(data);
        } catch (_) {}
      };
      poll();
      pollTimer = setInterval(poll, 450);
    }

    const STEP_META = {
      acquisition: { desc: "Upload file", icon: "↑" },
      document: { desc: "Markdown + chunk", icon: "◇" },
      planning: { desc: "Piano strutturale", icon: "◈" },
      segmentation: { desc: "Moduli grezzi", icon: "▤" },
      validation: { desc: "Controllo qualità", icon: "✓" },
      microlearning: { desc: "Deep Agent", icon: "✦" },
    };

    function updatePipelineHero(status) {
      const steps = status?.steps || [];
      const done = steps.filter((s) => s.completato).length;
      const total = STEP_ORDER.length;
      const pct = Math.round((done / total) * 100);

      const elDone = document.getElementById("statStepsDone");
      const elCourse = document.getElementById("statActiveCourse");
      const elNext = document.getElementById("statNextStep");
      const elPct = document.getElementById("pipelineOverallPct");
      const elFill = document.getElementById("pipelineOverallFill");

      if (elDone) elDone.textContent = `${done} / ${total}`;
      if (elCourse) {
        elCourse.textContent = status?.course_id || "—";
        elCourse.title = status?.course_id || "";
      }
      const nextId = status?.prossimo_step || "acquisition";
      if (elNext) elNext.textContent = STEP_LABELS[nextId] || nextId;
      if (elPct) elPct.textContent = pct + "%";
      if (elFill) elFill.style.width = pct + "%";
    }

    function renderPipeline(status) {
      pipelineEl.innerHTML = "";
      updatePipelineHero(status);
      const steps = status?.steps || STEP_ORDER.map((id, i) => ({
        id, label: STEP_LABELS[id], ordine: i, completato: false,
      }));
      const next = status?.prossimo_step || "acquisition";

      steps.forEach((s) => {
        const el = document.createElement("div");
        el.className = "step";
        el.setAttribute("role", "listitem");
        if (s.completato) el.classList.add("done");
        else if (s.id === next) el.classList.add("next");
        if (status && s.id === next && !s.completato) el.classList.add("active");
        el.dataset.step = s.id;
        const meta = STEP_META[s.id] || { desc: "", icon: "○" };
        const num = String(s.ordine + 1).padStart(2, "0");
        const icon = s.completato ? "✓" : meta.icon;
        const statusText = s.completato
          ? (s.artifact ? "Completato" : "Fatto")
          : (s.id === next ? "Prossimo" : "In attesa");
        el.innerHTML = `
          <div class="step-icon" title="${meta.desc}">${icon}</div>
          <strong>${s.label || STEP_LABELS[s.id]}</strong>
          <span class="step-desc">${meta.desc}</span>
          <span>${statusText}</span>
        `;
        pipelineEl.appendChild(el);
      });
    }

    function canRunFromStep(status, stepId) {
      if (!status) return stepId === "acquisition";
      const idx = STEP_ORDER.indexOf(stepId);
      if (idx < 0) return false;
      for (let i = 0; i < idx; i++) {
        const prev = status.steps.find((x) => x.id === STEP_ORDER[i]);
        if (prev && !prev.completato) return false;
      }
      return true;
    }

    function fillFromStepSelect(status) {
      const sel = document.getElementById("fromStep");
      sel.innerHTML = "";
      const next = status?.prossimo_step || "acquisition";

      STEP_ORDER.forEach((id) => {
        const s = status?.steps?.find((x) => x.id === id);
        const opt = document.createElement("option");
        opt.value = id;
        const done = s?.completato ? " ✓" : "";
        const en = canRunFromStep(status, id) ? "" : " (prerequisiti mancanti)";
        opt.textContent = STEP_LABELS[id] + done + en;
        opt.disabled = !canRunFromStep(status, id);
        if (id === next && canRunFromStep(status, id)) opt.selected = true;
        sel.appendChild(opt);
      });

      const full = document.createElement("option");
      full.value = "full";
      full.textContent = "Pipeline completa (da document)";
      full.disabled = !canRunFromStep(status, "document");
      sel.appendChild(full);
    }

    async function loadCourses() {
      const sel = document.getElementById("courseSelect");
      const exSel = document.getElementById("exploreCourseSelect");
      const r = await fetch("/api/v1/courses");
      const data = await r.json();
      sel.innerHTML = '<option value="">— Seleziona corso —</option>';
      if (exSel) exSel.innerHTML = '<option value="">— Seleziona —</option>';
      data.courses.forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c.course_id;
        opt.textContent = `${c.course_id} · ${c.prossimo_step}${c.legacy ? " (legacy)" : ""}`;
        sel.appendChild(opt);

        const exOpt = document.createElement("option");
        exOpt.value = c.course_id;
        exOpt.textContent = c.course_id;
        document.getElementById("exploreCourseSelect")?.appendChild(exOpt);
      });
      if (data.courses.length === 0) {
        sel.innerHTML = '<option value="">Nessun corso: creane uno nuovo</option>';
      }
      renderPipeline(currentStatus);
    }

    async function loadCourseStatus(courseId) {
      if (!courseId) {
        currentStatus = null;
        renderPipeline(null);
        document.getElementById("courseStatus").hidden = true;
        renderWarnings(null);
        fillFromStepSelect(null);
        return;
      }
      const r = await fetch(`/api/v1/courses/${encodeURIComponent(courseId)}/status`);
      if (!r.ok) throw new Error("Corso non trovato");
      currentStatus = await r.json();
      renderPipeline(currentStatus);
      fillFromStepSelect(currentStatus);

      const box = document.getElementById("courseStatus");
      box.hidden = false;
      const nextLabel = STEP_LABELS[currentStatus.prossimo_step] || currentStatus.prossimo_step;
      const legacy = currentStatus.course_id === "temp_workspace"
        ? '<span class="legacy-tag">legacy</span>' : "";
      const docsItem = currentStatus.is_corpus && currentStatus.sources?.length
        ? `<div class="status-box__item status-box__item--wide">
            <span>Documenti (${currentStatus.sources.length})</span>
            <strong>${escapeHtml(currentStatus.sources.map((s) => s.source_id).join(", "))}</strong>
          </div>`
        : `<div class="status-box__item">
            <span>Source</span>
            <strong>${escapeHtml(currentStatus.source_id || "n/d")}</strong>
          </div>`;
      box.innerHTML = `
        <div class="status-box__title">${escapeHtml(currentStatus.course_id)}${legacy}</div>
        <div class="status-box__grid">
          ${docsItem}
          <div class="status-box__item">
            <span>File nel workspace</span>
            <strong>${currentStatus.file_count}</strong>
          </div>
          <div class="status-box__item">
            <span>Prossimo step</span>
            <strong>${escapeHtml(nextLabel)}</strong>
          </div>
        </div>
      `;
      if (currentStatus.source_id) {
        document.getElementById("resumeSourceId").placeholder = currentStatus.source_id;
      }
      renderWarnings(currentStatus.warnings);
      refreshCourseExplorer(courseId);
    }

    async function refreshCourseExplorer(courseId) {
      const exploreEmpty = document.getElementById("exploreEmpty");
      const exploreSelect = document.getElementById("exploreCourseSelect");

      if (exploreSelect && courseId && exploreSelect.value !== courseId) {
        exploreSelect.value = courseId;
      }

      if (!courseId) {
        explorerEl.classList.remove("visible");
        courseViewData = null;
        if (exploreEmpty) exploreEmpty.hidden = false;
        return;
      }

      const microOk = currentStatus?.steps?.find((s) => s.id === "microlearning")?.completato;
      if (!microOk) {
        explorerEl.classList.remove("visible");
        if (exploreEmpty) {
          exploreEmpty.hidden = false;
          const p = exploreEmpty.querySelector("p");
          if (p) {
            p.innerHTML = "Il corso <strong>" + escapeHtml(courseId) + "</strong> non ha ancora completato lo step Microlearning.";
          }
        }
        return;
      }

      try {
        const r = await fetch(
          `/api/v1/courses/${encodeURIComponent(courseId)}/course-view`
        );
        if (!r.ok) {
          explorerEl.classList.remove("visible");
          if (exploreEmpty) exploreEmpty.hidden = false;
          return;
        }
        courseViewData = await r.json();
        explorerEl.classList.add("visible");
        if (exploreEmpty) exploreEmpty.hidden = true;

        const st = courseViewData.stats || {};
        const metaEl = document.getElementById("explorerMeta");
        if (metaEl) {
          metaEl.innerHTML =
            `<strong>${escapeHtml(courseViewData.titolo_corso)}</strong> · ` +
            `${st.lezioni ?? st.moduli ?? 0} lezioni` +
            (st.quiz ? ` · ${st.quiz} quiz` : "") +
            ` · ~${st.durata_totale_minuti || 0} min · ${st.archi || 0} collegamenti` +
            (courseViewData.completato ? ' · <span class="text-success">completato</span>' : "");
        }

        renderCourseGraph(courseViewData);
        renderQuizSummary(courseViewData);
        renderAllModules(courseViewData);
        const view = new URLSearchParams(location.search).get("view");
        if (view === "graph") switchExplorerTab("graph");
        else switchExplorerTab("modules");
        if (getCurrentView() === "explore" && graphNetwork) {
          setTimeout(() => graphNetwork.fit(), 120);
        }
      } catch (_) {
        explorerEl.classList.remove("visible");
        if (exploreEmpty) exploreEmpty.hidden = false;
      }
    }

    function renderCourseGraph(data) {
      const container = document.getElementById("graphNetwork");
      if (!window.vis || !data?.graph) return;
      const color = {
        lezione: { bg: "#ccfbf1", border: "#0d9488", font: "#0f766e" },
        quiz: { bg: "#ede9fe", border: "#7c3aed", font: "#5b21b6" },
        ok: { bg: "#d1fae5", border: "#059669", font: "#047857" },
        warn: { bg: "#fef3c7", border: "#d97706", font: "#b45309" },
      };
      const pick = (g) => color[g] || color.lezione;
      const nodes = new vis.DataSet(
        data.graph.nodes.map((n) => {
          const c = pick(n.group);
          return {
            id: n.id,
            label: n.label,
            title: `${n.title}\n${n.tipo || "lezione"} · ${n.durata} min`,
            shape: n.shape || (n.group === "quiz" ? "diamond" : "box"),
            color: {
              background: c.bg,
              border: c.border,
              highlight: { background: "#ffffff", border: c.border },
            },
            font: { color: c.font, size: n.group === "quiz" ? 10 : 11, face: "Plus Jakarta Sans" },
          };
        })
      );
      const edgeStyle = {
        prerequisite: { color: { color: "#0d9488" }, width: 2, arrows: "to" },
        quiz_after: { color: { color: "#7c3aed" }, width: 2, arrows: "to" },
        plan: { color: { color: "#059669" }, width: 2, arrows: "to" },
        sequence: { color: { color: "#94a3b8" }, width: 1, arrows: "to", dashes: [6, 4] },
      };
      const edges = new vis.DataSet(
        data.graph.edges.map((e, i) => ({
          id: i,
          from: e.from,
          to: e.to,
          ...edgeStyle[e.type] || edgeStyle.sequence,
        }))
      );
      const many = data.graph.nodes.length > 35;
      const options = {
        layout: many ? { improvedLayout: true } : {
          hierarchical: {
            enabled: data.graph.edges.some((e) => e.type !== "sequence"),
            direction: "UD",
            sortMethod: "directed",
            levelSeparation: 70,
            nodeSpacing: 90,
          },
        },
        physics: {
          enabled: many,
          stabilization: { iterations: many ? 120 : 80 },
          barnesHut: { gravitationalConstant: -8000, springLength: 120 },
        },
        interaction: { hover: true, tooltipDelay: 120, navigationButtons: true },
        nodes: { shape: "box", margin: 6, widthConstraint: { maximum: 140 } },
      };
      if (graphNetwork) graphNetwork.destroy();
      graphNetwork = new vis.Network(container, { nodes, edges }, options);
      graphNetwork.on("click", (params) => {
        if (!params.nodes.length) return;
        scrollToModule(params.nodes[0]);
        switchExplorerTab("modules");
      });
    }

    function switchExplorerTab(which) {
      const isGraph = which === "graph";
      document.querySelectorAll(".explorer-tabs button").forEach((b) => {
        b.classList.toggle("active", b.dataset.explorer === which);
      });
      const graphEl = document.getElementById("explorerGraph");
      const modEl = document.getElementById("explorerModules");
      if (graphEl) graphEl.hidden = !isGraph;
      if (modEl) modEl.hidden = isGraph;
      if (isGraph && graphNetwork) setTimeout(() => graphNetwork.fit(), 80);
    }

    function escapeHtml(s) {
      return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function renderMarkdown(md) {
      const text = String(md || "").trim();
      if (!text) return "<p><em>(nessun contenuto)</em></p>";
      if (typeof marked === "undefined") {
        return `<pre>${escapeHtml(text)}</pre>`;
      }
      marked.setOptions({ breaks: true, gfm: true });
      return marked.parse(text);
    }

    const _PRACTICE_HEADING = /\n##\s*(Azione concreta|Metti in pratica|Attività(?:\s+guidata)?)\s*\n/i;

    function renderLessonContent(md) {
      const text = String(md || "").trim();
      if (!text) return { main: renderMarkdown(""), practice: "" };
      const m = text.match(_PRACTICE_HEADING);
      if (!m || m.index == null) {
        return { main: renderMarkdown(text), practice: "" };
      }
      const mainPart = text.slice(0, m.index).trim();
      const practicePart = text.slice(m.index).trim();
      return {
        main: renderMarkdown(mainPart),
        practice: renderMarkdown(practicePart),
      };
    }

    const QUIZ_PROGRESS_KEY = "pipeline_quiz_progress";

    function activeCourseId() {
      return document.getElementById("courseSelect").value
        || courseViewData?.course_id
        || "";
    }

    function loadQuizProgress(courseId) {
      if (!courseId) return {};
      try {
        const all = JSON.parse(localStorage.getItem(QUIZ_PROGRESS_KEY) || "{}");
        return all[courseId] || {};
      } catch (_) {
        return {};
      }
    }

    function saveQuizAnswer(courseId, quizId, qIdx, selected, correct) {
      if (!courseId || !quizId) return;
      try {
        const all = JSON.parse(localStorage.getItem(QUIZ_PROGRESS_KEY) || "{}");
        const course = all[courseId] || {};
        const quiz = course[quizId] || {};
        quiz[String(qIdx)] = {
          selected,
          correct,
          checked: true,
          at: new Date().toISOString(),
        };
        course[quizId] = quiz;
        all[courseId] = course;
        localStorage.setItem(QUIZ_PROGRESS_KEY, JSON.stringify(all));
      } catch (_) {}
    }

    function clearQuizProgress(courseId) {
      try {
        const all = JSON.parse(localStorage.getItem(QUIZ_PROGRESS_KEY) || "{}");
        delete all[courseId];
        localStorage.setItem(QUIZ_PROGRESS_KEY, JSON.stringify(all));
      } catch (_) {}
    }

    function computeQuizStats(data, courseId) {
      const progress = loadQuizProgress(courseId);
      const quizzes = (data?.moduli || []).filter((m) => m.tipo === "quiz");
      let totalDomande = 0;
      let risposte = 0;
      let corrette = 0;
      const perQuiz = [];

      quizzes.forEach((quiz) => {
        const domande = quiz.domande || [];
        const n = domande.length;
        totalDomande += n;
        const pq = progress[quiz.id] || {};
        let qCorrette = 0;
        let qRisposte = 0;
        domande.forEach((_, qi) => {
          const a = pq[String(qi)];
          if (a?.checked) {
            qRisposte++;
            risposte++;
            if (a.correct) {
              qCorrette++;
              corrette++;
            }
          }
        });
        perQuiz.push({
          id: quiz.id,
          titolo: quiz.titolo,
          ordine: quiz.ordine,
          domande: n,
          risposte: qRisposte,
          corrette: qCorrette,
          completo: n > 0 && qRisposte === n,
          perfetto: n > 0 && qCorrette === n,
        });
      });

      const quizCompletati = perQuiz.filter((q) => q.completo).length;
      const quizPerfetti = perQuiz.filter((q) => q.perfetto).length;
      const pct = risposte > 0 ? Math.round((corrette / risposte) * 100) : null;

      return {
        quizzes: quizzes.length,
        totalDomande,
        risposte,
        corrette,
        pct,
        quizCompletati,
        quizPerfetti,
        perQuiz,
      };
    }

    function renderQuizSummary(data) {
      const panel = document.getElementById("quizSummary");
      const courseId = activeCourseId();
      const stats = computeQuizStats(data, courseId);

      if (!stats.quizzes) {
        panel.hidden = true;
        panel.innerHTML = "";
        return;
      }

      const pct = stats.pct;
      const scoreClass = pct == null ? "" : pct >= 80 ? "" : pct >= 50 ? "warn" : "low";
      const scoreText = pct == null ? "—" : `${pct}%`;

      let html = `<h4>Risultato complessivo quiz</h4>`;
      html += `<div class="big-score ${scoreClass}">${scoreText}</div>`;
      html += `<p style="margin:0.25rem 0 0.75rem;color:var(--muted);font-size:0.82rem">`;
      html += `Risposte corrette su quelle verificate (${stats.corrette}/${stats.risposte})</p>`;

      html += `<div class="quiz-summary-grid">`;
      html += `<div><span>Quiz nel corso</span><strong>${stats.quizzes}</strong></div>`;
      html += `<div><span>Domande totali</span><strong>${stats.totalDomande}</strong></div>`;
      html += `<div><span>Quiz completati</span><strong>${stats.quizCompletati}/${stats.quizzes}</strong></div>`;
      html += `<div><span>Quiz tutti corretti</span><strong>${stats.quizPerfetti}/${stats.quizzes}</strong></div>`;
      html += `</div>`;

      if (stats.perQuiz.length) {
        html += `<ul class="quiz-per-list">`;
        stats.perQuiz.forEach((q) => {
          const icon = q.perfetto ? "✓" : q.completo ? "~" : "○";
          const col = q.perfetto ? "var(--success)" : q.completo ? "var(--warn)" : "var(--muted)";
          html += `<li><a href="#mod-${q.id}" onclick="event.preventDefault();scrollToModule('${q.id}')">` +
            `${icon} ${escapeHtml(q.titolo)}</a>` +
            `<span style="color:${col}">${q.corrette}/${q.domande}</span></li>`;
        });
        html += `</ul>`;
      }

      html += `<button type="button" class="quiz-reset-btn" id="btnResetQuiz">Azzera risultati quiz per questo corso</button>`;
      panel.innerHTML = html;
      panel.hidden = false;

      document.getElementById("btnResetQuiz")?.addEventListener("click", () => {
        if (!confirm("Cancellare tutte le risposte ai quiz salvate per questo corso?")) return;
        clearQuizProgress(courseId);
        if (courseViewData) {
          renderQuizSummary(courseViewData);
          renderAllModules(courseViewData, document.getElementById("moduleSearch").value);
        }
      });
    }

    function applySavedQuizState(card, quizId) {
      const progress = loadQuizProgress(activeCourseId())[quizId] || {};
      card.querySelectorAll(".quiz-q").forEach((box) => {
        const qi = box.dataset.qidx;
        const saved = progress[qi];
        if (!saved?.checked) return;
        const qName = box.dataset.qname;
        const radio = box.querySelector(`input[name="${qName}"][value="${saved.selected}"]`);
        if (radio) radio.checked = true;
        const fb = box.querySelector(".quiz-feedback");
        box.classList.add(saved.correct ? "answered-ok" : "answered-ko");
        fb.textContent = saved.correct ? "Corretto!" : "Non corretto.";
        fb.style.color = saved.correct ? "var(--success)" : "var(--error)";
      });
    }

    function scrollToModule(modId) {
      const el = document.getElementById("mod-" + modId);
      if (!el) return;
      document.querySelectorAll(".module-card").forEach((c) => c.classList.remove("highlight"));
      el.classList.add("highlight");
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      setTimeout(() => el.classList.remove("highlight"), 2500);
    }

    function renderAllModules(data, filterText = "") {
      const list = document.getElementById("allModulesList");
      const index = document.getElementById("modulesIndex");
      const q = (filterText || "").trim().toLowerCase();
      list.innerHTML = "";
      index.innerHTML = "";
      if (!data?.moduli?.length) {
        document.getElementById("moduleCount").textContent = "0 moduli";
        return;
      }

      const visible = data.moduli.filter((m) => {
        if (!q) return true;
        const hay = `${m.titolo} ${m.contenuto || ""} ${m.sintesi || ""} ${(m.obiettivi || []).join(" ")}`.toLowerCase();
        return hay.includes(q);
      });

      document.getElementById("moduleCount").textContent =
        q ? `${visible.length} / ${data.moduli.length} moduli` : `${data.moduli.length} moduli`;

      visible.forEach((m) => {
        const short = m.titolo.length > 28 ? m.titolo.slice(0, 26) + "…" : m.titolo;
        const a = document.createElement("a");
        a.href = "#mod-" + m.id;
        a.textContent = `${m.ordine}. ${short}`;
        a.onclick = (e) => {
          e.preventDefault();
          scrollToModule(m.id);
        };
        index.appendChild(a);

        const card = document.createElement("article");
        card.className = "module-card" + (m.tipo === "quiz" ? " quiz-card" : "");
        card.id = "mod-" + m.id;

        const tipoTag = m.tipo === "quiz"
          ? '<span class="tag-quiz">quiz</span>'
          : '<span class="tag-micro">lezione</span>';

        let inner = `<h3>${m.ordine}. ${escapeHtml(m.titolo)}</h3>` +
          `<div class="meta"><span>${m.id}</span><span>~${m.durata_stimata_minuti} min</span>${tipoTag}</div>`;

        if (m.tipo === "quiz" && m.domande?.length) {
          m.domande.forEach((q, qi) => {
            const qName = `q-${m.id}-${qi}`;
            inner += `<div class="quiz-q" data-qidx="${qi}" data-correct="${q.indice_corretto}" data-qname="${qName}">`;
            inner += `<strong>D${qi + 1}. ${escapeHtml(q.testo)}</strong>`;
            inner += `<div class="quiz-options">`;
            (q.opzioni || []).forEach((opt, oi) => {
              inner +=
                `<label class="quiz-option">` +
                `<input type="radio" name="${qName}" value="${oi}" />` +
                `<span>${escapeHtml(opt)}</span></label>`;
            });
            inner += `</div>`;
            inner += `<button type="button" class="quiz-check">Verifica</button>`;
            inner += `<div class="quiz-feedback"></div></div>`;
          });
        } else {
          if (m.obiettivi?.length) {
            inner +=
              '<section class="lesson-objectives"><h4>Obiettivi di apprendimento</h4><ul>' +
              m.obiettivi.map((o) => `<li>${escapeHtml(o)}</li>`).join("") + "</ul></section>";
          }
          const body = m.contenuto || m.sintesi || "";
          const longBody = body.length > 800;
          const parts = renderLessonContent(body);
          inner += '<div class="lesson-body-wrap">';
          inner += `<div class="body md-content lesson-main${longBody ? " collapsed" : ""}">${parts.main}</div>`;
          if (longBody) {
            inner += '<button type="button" class="toggle-body">Mostra tutto il testo</button>';
          }
          inner += "</div>";
          if (parts.practice) {
            inner +=
              '<aside class="lesson-practice"><h4>Attività</h4>' +
              parts.practice + "</aside>";
          }
        }

        card.innerHTML = inner;

        if (m.tipo === "quiz") {
          applySavedQuizState(card, m.id);
        }

        card.querySelectorAll(".quiz-check").forEach((btn) => {
          btn.onclick = () => {
            const box = btn.closest(".quiz-q");
            const quizCard = btn.closest(".module-card");
            const quizId = quizCard?.id?.replace(/^mod-/, "") || m.id;
            const correct = parseInt(box.dataset.correct, 10);
            const qName = box.dataset.qname;
            const sel = box.querySelector(`input[name="${qName}"]:checked`);
            const fb = box.querySelector(".quiz-feedback");
            if (!sel) {
              fb.textContent = "Seleziona una risposta.";
              fb.style.color = "var(--warn)";
              return;
            }
            const selected = parseInt(sel.value, 10);
            const ok = selected === correct;
            box.classList.remove("answered-ok", "answered-ko");
            box.classList.add(ok ? "answered-ok" : "answered-ko");
            fb.textContent = ok ? "Corretto!" : "Non corretto. Rileggi la lezione collegata.";
            fb.style.color = ok ? "var(--success)" : "var(--error)";
            saveQuizAnswer(activeCourseId(), quizId, box.dataset.qidx, selected, ok);
            if (courseViewData) renderQuizSummary(courseViewData);
          };
        });

        const toggle = card.querySelector(".toggle-body");
        if (toggle) {
          const bodyEl = card.querySelector(".lesson-main");
          toggle.onclick = () => {
            const collapsed = bodyEl.classList.toggle("collapsed");
            toggle.textContent = collapsed ? "Mostra tutto il testo" : "Comprimi testo";
          };
        }
        list.appendChild(card);
      });
    }

    document.querySelectorAll(".explorer-tabs button").forEach((btn) => {
      btn.onclick = () => switchExplorerTab(btn.dataset.explorer);
    });

    document.getElementById("moduleSearch").oninput = (e) => {
      if (courseViewData) renderAllModules(courseViewData, e.target.value);
    };

    function statusLabel(status) {
      const map = {
        PASS: "Completato",
        PASS_WITH_WARNINGS: "Completato con avvisi",
        FAIL: "Non superato",
      };
      return map[status] || status;
    }

    function badgeClass(status) {
      if (status === "PASS") return "pass";
      if (status === "PASS_WITH_WARNINGS") return "warn";
      return "fail";
    }

    function renderWarnings(w, targetId = "courseWarnings") {
      const el = document.getElementById(targetId);
      if (!el) return;
      if (!w || (!w.moduli_in_revisione && !w.moduli_respinti && !(w.qualita_documento?.issues?.length))) {
        el.hidden = true;
        el.innerHTML = "";
        return;
      }
      let html = `<div class="warnings-panel"><h4>${w.stato_label || "Avvisi pipeline"}</h4>`;
      html += `<p class="warn-stats">Validazione: <strong>${w.moduli_approvati}</strong> moduli ok, ` +
        `<strong style="color:var(--warn)">${w.moduli_in_revisione}</strong> da rivedere` +
        (w.moduli_respinti ? `, <strong style="color:var(--error)">${w.moduli_respinti}</strong> respinti` : "") +
        `.</p>`;
      if (w.messaggi_aggregati?.length) {
        html += "<p><strong>Motivi principali:</strong></p><ul>";
        w.messaggi_aggregati.forEach((x) => {
          html += `<li>${escapeHtml(x.messaggio)} <span style="color:var(--muted)">(${x.occorrenze}×)</span></li>`;
        });
        html += "</ul>";
      }
      if (w.moduli_campione?.length) {
        html += "<details><summary>Esempi moduli segnalati</summary>";
        w.moduli_campione.forEach((m) => {
          html += `<div class="module-sample"><strong>${escapeHtml(m.modulo_id)}</strong>`;
          if (m.titolo) html += ` — ${escapeHtml(m.titolo)}`;
          if (m.messaggi?.length) html += `<br>${escapeHtml(m.messaggi.join(" · "))}`;
          html += "</div>";
        });
        html += "</details>";
      }
      const q = w.qualita_documento;
      if (q?.issues?.length) {
        html += `<p style="margin-top:0.75rem"><strong>Qualità documento</strong> ` +
          `(score ${q.quality_score ?? "n/d"}, ${statusLabel(q.status || "")})</p><ul>`;
        q.issues.forEach((i) => {
          html += `<li>${escapeHtml(i.message || i.messaggio || JSON.stringify(i))}</li>`;
        });
        html += "</ul>";
      }
      html += "</div>";
      el.innerHTML = html;
      el.hidden = false;
    }

    function closePreview() {
      const wrap = document.getElementById("previewWrap");
      const pre = document.getElementById("preview");
      if (wrap) wrap.hidden = true;
      if (pre) pre.textContent = "";
    }

    function showPreview(path, content, isJson) {
      const wrap = document.getElementById("previewWrap");
      const pre = document.getElementById("preview");
      const label = document.getElementById("previewLabel");
      if (!wrap || !pre) return;
      label.textContent = path;
      pre.textContent = isJson ? JSON.stringify(content, null, 2) : content;
      wrap.hidden = false;
      wrap.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function showResults(data) {
      const src = data.sources?.[0];
      if (!src) {
        document.getElementById("summary").textContent = `Corso ${data.job_id} — ${data.log_summary?.join(" ")}`;
        resultsEl.classList.add("visible");
        document.getElementById("btnCloseResults")?.removeAttribute("hidden");
        document.getElementById("resultsExploreCta")?.setAttribute("hidden", "");
        closePreview();
        return;
      }
      document.getElementById("summary").innerHTML =
        `Corso <strong>${data.job_id}</strong> · ${src.source_id} · ` +
        `<span class="badge ${badgeClass(src.status)}">${statusLabel(src.status)}</span>` +
        ` <span style="color:var(--muted);font-size:0.8rem">(${src.status})</span>`;
      renderWarnings(currentStatus?.warnings, "resultsWarnings");

      const arts = [
        ["Markdown", src.markdown_ref],
        ["Piano", src.plan_ref],
        ["Moduli grezzi", src.raw_modules_ref],
        ["Moduli validati", src.validated_modules_ref],
        ["Validazione", src.validation_ref],
        ["Chunks", src.chunks_ref],
        ["Gerarchia", src.hierarchy_ref],
        ["Qualità", src.quality_report_ref],
        ["Microlearning", src.microlearning_ref || data.microlearning_course_ref],
      ].filter(([, p]) => p);

      const list = document.getElementById("artifacts");
      list.innerHTML = "";
      const cid = data.job_id;
      for (const [label, path] of arts) {
        const li = document.createElement("li");
        const a = document.createElement("a");
        a.href = "#";
        a.textContent = path;
        a.onclick = async (ev) => {
          ev.preventDefault();
          const r = await fetch(`/api/v1/courses/${cid}/file?path=${encodeURIComponent(path)}`);
          if (path.endsWith(".json")) {
            showPreview(path, await r.json(), true);
          } else {
            showPreview(path, await r.text(), false);
          }
        };
        li.innerHTML = `<span class="artifact-label">${label}</span>`;
        li.appendChild(a);
        list.appendChild(li);
      }
      resultsEl.classList.add("visible");
      document.getElementById("btnCloseResults")?.removeAttribute("hidden");
      closePreview();
      const exploreCta = document.getElementById("resultsExploreCta");
      const microRef = src?.microlearning_ref || data.microlearning_course_ref;
      if (exploreCta) exploreCta.hidden = !microRef;
      refreshCourseExplorer(cid);
    }

    async function runResume(fromStep) {
      const courseId = document.getElementById("courseSelect").value;
      if (!courseId) { log("Seleziona un corso", "err"); return; }

      const fd = new FormData();
      fd.append("source_id", document.getElementById("resumeSourceId").value.trim() || currentStatus?.source_id || courseId);
      fd.append("from_step", fromStep);
      fd.append("run_microlearning", document.getElementById("resumeMicro").checked);
      fd.append("async_mode", "true");

      const f = document.getElementById("resumeFile").files[0];
      if (f && ["acquisition", "document", "full"].includes(fromStep)) {
        const fd2 = new FormData();
        fd2.append("source_id", fd.get("source_id"));
        fd2.append("course_id", courseId);
        fd2.append("from_step", fromStep);
        fd2.append("run_microlearning", fd.get("run_microlearning"));
        fd2.append("file", f);
        resultsEl.classList.remove("visible");
        setProgress(0);
        logEl.innerHTML = "";
        clearDeepAgentLog();
        const res = await fetch("/api/v1/pipeline/run-async", { method: "POST", body: fd2 });
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
        startPolling(courseId, finishRun);
        return;
      }

      resultsEl.classList.remove("visible");
      setProgress(0);
      logEl.innerHTML = "";
      clearDeepAgentLog();
      const res = await fetch(`/api/v1/courses/${encodeURIComponent(courseId)}/resume`, { method: "POST", body: fd });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
      startPolling(courseId, finishRun);
    }

    async function finishRun(data) {
      if (data.status === "error") {
        log(data.error || "Errore durante l'elaborazione", "err");
        setProgress(data.percent || 0);
        return;
      }
      setProgress(100);
      const cid = data.course_id || document.getElementById("courseSelect").value;
      await loadCourseStatus(cid).catch(() => {});
      if (data.result) showResults(data.result);
      else log("Completato.", "ok");
      loadCourses();
      if (currentStatus?.steps?.find((s) => s.id === "microlearning")?.completato) {
        document.getElementById("resultsExploreCta")?.removeAttribute("hidden");
      }
    }

    document.querySelectorAll(".tab").forEach((btn) => {
      btn.onclick = () => {
        document.querySelectorAll(".tab").forEach((b) => {
          b.classList.remove("active");
          b.setAttribute("aria-selected", "false");
        });
        document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
        btn.classList.add("active");
        btn.setAttribute("aria-selected", "true");
        document.getElementById(btn.dataset.tab === "new" ? "panelNew" : "panelResume").classList.add("active");
      };
    });

    document.getElementById("file")?.addEventListener("change", (e) => {
      const drop = e.target.closest(".file-drop");
      const label = drop?.querySelector(".file-drop__label");
      const hint = drop?.querySelector(".file-drop__hint");
      const f = e.target.files?.[0];
      if (label && f) {
        const kb = (f.size / 1024).toFixed(0);
        label.textContent = f.name;
        if (hint) hint.textContent = `${kb} KB`;
        label.style.color = "var(--text)";
        label.style.fontWeight = "600";
      }
    });

    document.getElementById("courseSelect").onchange = () => {
      const cid = document.getElementById("courseSelect").value;
      const ex = document.getElementById("exploreCourseSelect");
      if (ex) ex.value = cid || "";
      loadCourseStatus(cid).catch((e) => log(e.message, "err"));
    };

    document.getElementById("btnRefresh").onclick = () => loadCourses().then(() => log("Elenco corsi aggiornato", "ok"));

    document.getElementById("btnResume").onclick = async () => {
      const btn = document.getElementById("btnResume");
      btn.disabled = true;
      try {
        await runResume(document.getElementById("fromStep").value);
      } catch (e) {
        log(e.message, "err");
      } finally {
        btn.disabled = false;
      }
    };

    document.getElementById("btnResumeNext").onclick = async () => {
      if (!currentStatus) return;
      let step = currentStatus.prossimo_step;
      if (step === "done") { log("Corso già completato", "ok"); return; }
      document.getElementById("fromStep").value = step;
      document.getElementById("btnResume").click();
    };

    function slugFromFilename(name) {
      return (name || "doc").replace(/\.[^.]+$/, "").replace(/[^a-zA-Z0-9_-]+/g, "_").slice(0, 64) || "doc";
    }

    function refreshUploadFileList() {
      const input = document.getElementById("files");
      const list = document.getElementById("uploadFileList");
      if (!input || !list) return;
      const files = [...(input.files || [])];
      if (!files.length) {
        list.hidden = true;
        list.innerHTML = "";
        return;
      }
      list.hidden = false;
      const sid0 = document.getElementById("source_id");
      const multi = files.length > 1;
      list.innerHTML = files.map((f, i) => {
        const sid = multi
          ? slugFromFilename(f.name)
          : ((i === 0 && sid0?.value.trim()) ? sid0.value.trim() : slugFromFilename(f.name));
        return `<li><span class="upload-file-list__name">${escapeHtml(f.name)}</span><span class="upload-file-list__id">${escapeHtml(sid)}</span></li>`;
      }).join("");
    }

    document.getElementById("files")?.addEventListener("change", refreshUploadFileList);
    document.getElementById("source_id")?.addEventListener("input", () => {
      document.getElementById("source_id").dataset.auto = "0";
      refreshUploadFileList();
    });

    document.getElementById("course_id").addEventListener("input", (e) => {
      const v = e.target.value.trim();
      const sid = document.getElementById("source_id");
      const files = [...(document.getElementById("files")?.files || [])];
      if (files.length > 1) {
        refreshUploadFileList();
        return;
      }
      if (!sid.value || sid.dataset.auto === "1") {
        sid.value = files.length === 1 ? slugFromFilename(files[0].name) : v;
        sid.dataset.auto = "1";
      }
      refreshUploadFileList();
    });

    document.getElementById("uploadForm").onsubmit = async (e) => {
      e.preventDefault();
      const btn = document.getElementById("submitBtn");
      const fileInput = document.getElementById("files");
      const selected = [...(fileInput?.files || [])];
      if (!selected.length) return;
      btn.disabled = true;
      logEl.innerHTML = "";
      clearDeepAgentLog();
      resultsEl.classList.remove("visible");
      setProgress(0);

      const cid = document.getElementById("course_id").value.trim();
      const fd = new FormData();
      const sid0 = document.getElementById("source_id").value.trim();
      const multi = selected.length > 1;
      const extraIds = selected.map((f) => slugFromFilename(f.name));
      if (selected.length === 1) {
        fd.append("file", selected[0]);
        fd.append("source_id", sid0 || extraIds[0]);
      } else {
        selected.forEach((f) => fd.append("files", f));
        fd.append("source_ids", extraIds.join(","));
      }
      fd.append("course_id", cid);
      fd.append("language_hint", document.getElementById("language_hint").value || "it");
      fd.append("from_step", "full");
      fd.append("run_microlearning", document.getElementById("run_microlearning").checked);

      try {
        const res = await fetch("/api/v1/pipeline/run-async", { method: "POST", body: fd });
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
        document.getElementById("courseSelect").value = cid;
        navigateTo("pipeline");
        startPolling(cid, (data) => {
          finishRun(data);
          loadCourses().then(() => {
            document.getElementById("courseSelect").value = cid;
            document.querySelector('.tab[data-tab="resume"]').click();
          });
        });
      } catch (err) {
        log(err.message, "err");
      } finally {
        btn.disabled = false;
      }
    };

    document.getElementById("btnClosePreview")?.addEventListener("click", closePreview);
    document.getElementById("btnCloseResults")?.addEventListener("click", () => {
      resultsEl.classList.remove("visible");
      closePreview();
      document.getElementById("btnCloseResults")?.setAttribute("hidden", "");
    });

    /* ── Config panel (toggle + close) ─────────────────────── */
    let configOpen = false;
    let configCache = null;

    function renderConfigHtml(d) {
      const llm = d.sezioni?.llm || {};
      const sintesi = d.sintesi || {};
      const varsHtml = (llm.variabili || [])
        .map((v) => `<div class="config-var"><dt>${escapeHtml(v.nome)}</dt><dd>${escapeHtml(v.effettivo || v.fonte || "—")}</dd></div>`)
        .join("");
      return `
        <div class="config-grid">
          <div class="config-stat">
            <div class="config-stat__label">Provider LLM</div>
            <div class="config-stat__value">${escapeHtml(sintesi.provider || "—")}</div>
          </div>
          <div class="config-stat">
            <div class="config-stat__label">Modello</div>
            <div class="config-stat__value mono">${escapeHtml(sintesi.modello || "—")}</div>
          </div>
          <div class="config-stat">
            <div class="config-stat__label">Parallelismo</div>
            <div class="config-stat__value">${escapeHtml(String(sintesi.parallelismo_llm || "—"))}</div>
          </div>
        </div>
        <div class="config-section">
          <h3>File .env</h3>
          <div class="config-vars">
            <div class="config-var"><dt>percorso</dt><dd>${escapeHtml(d.env_file || "—")}</dd></div>
            <div class="config-var"><dt>stato</dt><dd>${d.env_file_esiste ? "presente" : "assente"} · ${d.righe_attive_nel_file || 0} variabili</dd></div>
            <div class="config-var"><dt>log level</dt><dd>${escapeHtml(sintesi.log_level || "INFO")}</dd></div>
          </div>
        </div>
        <div class="config-section">
          <h3>Variabili LLM</h3>
          <div class="config-vars">${varsHtml || "<p class=\"hint\">Nessuna variabile.</p>"}</div>
        </div>
      `;
    }

    function updateHeaderChip(d) {
      const chip = document.getElementById("headerStatus");
      if (!chip || !d?.sintesi) return;
      chip.textContent = `${d.sintesi.provider} · ${d.sintesi.modello}`;
      chip.hidden = false;
    }

    function openConfigPanel() {
      const wrap = document.getElementById("configWrap");
      const btn = document.getElementById("btnShowConfig");
      wrap.hidden = false;
      configOpen = true;
      btn.textContent = "Chiudi";
      btn.setAttribute("aria-expanded", "true");
      btn.classList.add("btn-show-config");
    }

    function closeConfigPanel() {
      const wrap = document.getElementById("configWrap");
      const btn = document.getElementById("btnShowConfig");
      const details = document.getElementById("configJsonDetails");
      wrap.hidden = true;
      configOpen = false;
      btn.textContent = "Configurazione";
      btn.setAttribute("aria-expanded", "false");
      btn.classList.remove("btn-show-config");
      if (details) details.open = false;
    }

    async function loadConfig(force) {
      if (configCache && !force) return configCache;
      const r = await fetch("/api/v1/config");
      if (!r.ok) throw new Error("Impossibile caricare la configurazione");
      configCache = await r.json();
      updateHeaderChip(configCache);
      return configCache;
    }

    document.getElementById("btnShowConfig")?.addEventListener("click", async () => {
      if (configOpen) {
        closeConfigPanel();
        return;
      }
      const panel = document.getElementById("configPanel");
      const jsonPre = document.getElementById("configJson");
      openConfigPanel();
      panel.innerHTML = '<div class="config-loading">Caricamento…</div>';
      try {
        const d = await loadConfig(true);
        panel.innerHTML = renderConfigHtml(d);
        if (jsonPre) jsonPre.textContent = JSON.stringify(d, null, 2);
      } catch (e) {
        panel.innerHTML = `<p class="line err">Errore: ${escapeHtml(e.message)}</p>`;
      }
    });

    document.getElementById("btnCloseConfig")?.addEventListener("click", closeConfigPanel);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && configOpen) closeConfigPanel();
    });

    function setOptionalPanel(kind, open) {
      const map = {
        monitor: { panel: "monitorPanel", btn: "toggleMonitor" },
        deep: { panel: "deepAgentPanel", btn: "toggleDeepAgent" },
      };
      const cfg = map[kind];
      if (!cfg) return;
      const panel = document.getElementById(cfg.panel);
      const btn = document.getElementById(cfg.btn);
      if (!panel || !btn) return;
      panel.hidden = !open;
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    }

    function toggleOptionalPanel(kind) {
      const map = {
        monitor: { panel: "monitorPanel", btn: "toggleMonitor" },
        deep: { panel: "deepAgentPanel", btn: "toggleDeepAgent" },
      };
      const cfg = map[kind];
      const panel = document.getElementById(cfg.panel);
      const btn = document.getElementById(cfg.btn);
      if (!panel || !btn) return;
      const open = panel.hidden;
      setOptionalPanel(kind, open);
      if (open && kind === "monitor") {
        const cid = document.getElementById("courseSelect")?.value;
        if (cid && !pollTimer) loadActivitySnapshot(cid, { resumePoll: true });
      }
    }

    document.getElementById("toggleMonitor")?.addEventListener("click", () => toggleOptionalPanel("monitor"));
    document.getElementById("toggleDeepAgent")?.addEventListener("click", () => toggleOptionalPanel("deep"));

    loadConfig().catch(() => {});

    /* ── Navigazione viste (sidebar + hash) ─────────────────── */
    const VIEW_IDS = ["home", "pipeline", "explore", "guide"];
    const VIEW_TITLES = {
      home: "Home",
      pipeline: "Pipeline",
      explore: "Esplora corso",
      guide: "Come funziona",
    };

    function getCurrentView() {
      const active = document.querySelector(".view:not([hidden])");
      return active?.id?.replace("view-", "") || "home";
    }

    function closeSidebar() {
      document.getElementById("shell")?.classList.remove("sidebar-open");
      document.getElementById("sidebarBackdrop")?.setAttribute("hidden", "");
    }

    function openSidebar() {
      document.getElementById("shell")?.classList.add("sidebar-open");
      document.getElementById("sidebarBackdrop")?.removeAttribute("hidden");
    }

    function navigateTo(viewId) {
      if (!VIEW_IDS.includes(viewId)) viewId = "home";

      document.querySelectorAll(".view").forEach((v) => {
        v.hidden = true;
        v.classList.remove("view--active");
      });
      const target = document.getElementById("view-" + viewId);
      if (target) {
        target.hidden = false;
        target.classList.add("view--active");
      }

      document.querySelectorAll(".nav-item").forEach((n) => {
        n.classList.toggle("active", n.dataset.view === viewId);
      });

      const title = document.getElementById("topbarTitle");
      if (title) title.textContent = VIEW_TITLES[viewId] || viewId;

      if (location.hash !== "#" + viewId) {
        history.replaceState(null, "", "#" + viewId);
      }

      closeSidebar();

      if (viewId === "explore") {
        const cid = document.getElementById("exploreCourseSelect")?.value
          || document.getElementById("courseSelect")?.value;
        switchExplorerTab("modules");
        if (cid) {
          loadCourseStatus(cid).catch(() => refreshCourseExplorer(cid));
        } else {
          refreshCourseExplorer(null);
        }
      }

      if (viewId === "pipeline" && graphNetwork) {
        setTimeout(() => graphNetwork.fit(), 80);
      }
    }

    document.querySelectorAll("[data-view]").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.preventDefault();
        navigateTo(el.dataset.view);
      });
    });

    document.querySelectorAll("[data-goto]").forEach((el) => {
      el.addEventListener("click", () => navigateTo(el.dataset.goto));
    });

    document.getElementById("btnMenu")?.addEventListener("click", () => {
      const shell = document.getElementById("shell");
      if (shell?.classList.contains("sidebar-open")) closeSidebar();
      else openSidebar();
    });

    document.getElementById("sidebarBackdrop")?.addEventListener("click", closeSidebar);

    document.getElementById("exploreCourseSelect")?.addEventListener("change", (e) => {
      const cid = e.target.value;
      if (cid) {
        document.getElementById("courseSelect").value = cid;
        loadCourseStatus(cid).catch((err) => log(err.message, "err"));
      } else {
        refreshCourseExplorer(null);
      }
    });

    function initRoute() {
      const hash = (location.hash || "#home").slice(1);
      const params = new URLSearchParams(location.search);
      if (params.get("view") === "graph") navigateTo("explore");
      else if (params.get("view") === "modules" || params.get("view") === "demo") navigateTo("explore");
      else navigateTo(VIEW_IDS.includes(hash) ? hash : "home");
    }

    window.addEventListener("hashchange", () => {
      const hash = (location.hash || "#home").slice(1);
      if (VIEW_IDS.includes(hash) && hash !== getCurrentView()) navigateTo(hash);
    });

    loadCourses().then(() => {
      const params = new URLSearchParams(location.search);
      const c = params.get("course");
      if (c) {
        document.getElementById("courseSelect").value = c;
        const ex = document.getElementById("exploreCourseSelect");
        if (ex) ex.value = c;
        loadCourseStatus(c);
      }
      initRoute();
    });
    renderPipeline(null);

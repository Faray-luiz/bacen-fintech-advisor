/* ==========================================================================
   Bacen Fintech Advisor — Google Material Design 3 Frontend Controller
   ========================================================================== */

(() => {
  "use strict";

  // ------------------------------------------------------------------------
  // State
  // ------------------------------------------------------------------------
  const state = {
    activeSessionId: null,
    sessions: [],
    turns: [],
    isStreaming: false,
    selectedTraceId: null,
    models: {
      router: "gemini-flash",
      collector: "gemini-flash",
      analyst: "gemini-pro",
      critic: "gemini-flash",
    },
  };

  // DOM References
  const dom = {
    authOverlay: document.getElementById("authOverlay"),
    authSubtitle: document.getElementById("authSubtitle"),
    googleSignInWrap: document.getElementById("googleSignInWrap"),
    googleSignInBtn: document.getElementById("googleSignInBtn"),
    authDivider: document.getElementById("authDivider"),
    authForm: document.getElementById("authForm"),
    authTokenInput: document.getElementById("authTokenInput"),
    authErrorMsg: document.getElementById("authErrorMsg"),
    authSubmitBtn: document.getElementById("authSubmitBtn"),
    toggleTokenVisibilityBtn: document.getElementById("toggleTokenVisibilityBtn"),
    openAdminBtn: document.getElementById("openAdminBtn"),
    adminModalBackdrop: document.getElementById("adminModalBackdrop"),
    closeAdminModalBtn: document.getElementById("closeAdminModalBtn"),
    adminAddForm: document.getElementById("adminAddForm"),
    adminEntryInput: document.getElementById("adminEntryInput"),
    adminAddBtn: document.getElementById("adminAddBtn"),
    adminErrorMsg: document.getElementById("adminErrorMsg"),
    adminTotalCount: document.getElementById("adminTotalCount"),
    adminAllowlistItems: document.getElementById("adminAllowlistItems"),
    adminStorageHint: document.getElementById("adminStorageHint"),
    userPill: document.getElementById("userPill"),
    userAvatarImg: document.getElementById("userAvatarImg"),
    userAvatarFallback: document.getElementById("userAvatarFallback"),
    userPillName: document.getElementById("userPillName"),
    logoutBtn: document.getElementById("logoutBtn"),
    appShell: document.getElementById("appShell"),
    sidebar: document.getElementById("sidebar"),
    sidebarBackdrop: document.getElementById("sidebarBackdrop"),
    toggleSidebarBtn: document.getElementById("toggleSidebarBtn"),
    closeSidebarBtn: document.getElementById("closeSidebarBtn"),
    newSessionBtn: document.getElementById("newSessionBtn"),
    sessionList: document.getElementById("sessionList"),
    activeSessionTitle: document.getElementById("activeSessionTitle"),
    mcpStatusChip: document.getElementById("mcpStatusChip"),
    mcpStatusText: document.getElementById("mcpStatusText"),
    modelRoutingText: document.getElementById("modelRoutingText"),
    sidebarModelsText: document.getElementById("sidebarModelsText"),
    toggleInspectorBtn: document.getElementById("toggleInspectorBtn"),
    closeInspectorBtn: document.getElementById("closeInspectorBtn"),
    openWhatIfBtn: document.getElementById("openWhatIfBtn"),
    whatIfModalBackdrop: document.getElementById("whatIfModalBackdrop"),
    closeWhatIfModalBtn: document.getElementById("closeWhatIfModalBtn"),
    cancelWhatIfBtn: document.getElementById("cancelWhatIfBtn"),
    whatIfBankSelect: document.getElementById("whatIfBankSelect"),
    whatIfBaselineMeta: document.getElementById("whatIfBaselineMeta"),
    whatIfSlidersHost: document.getElementById("whatIfSlidersHost"),
    whatIfPosDisplay: document.getElementById("whatIfPosDisplay"),
    whatIfPosDelta: document.getElementById("whatIfPosDelta"),
    whatIfScoreDisplay: document.getElementById("whatIfScoreDisplay"),
    whatIfScoreDelta: document.getElementById("whatIfScoreDelta"),
    whatIfOvertakenBox: document.getElementById("whatIfOvertakenBox"),
    whatIfAlertsBox: document.getElementById("whatIfAlertsBox"),
    whatIfLeaderboard: document.getElementById("whatIfLeaderboard"),
    whatIfBlueprints: document.getElementById("whatIfBlueprints"),
    launchWhatIfBusinessCaseBtn: document.getElementById("launchWhatIfBusinessCaseBtn"),
    openWarRoomBtn: document.getElementById("openWarRoomBtn"),
    warRoomModalBackdrop: document.getElementById("warRoomModalBackdrop"),
    closeWarRoomModalBtn: document.getElementById("closeWarRoomModalBtn"),
    cancelWarRoomBtn: document.getElementById("cancelWarRoomBtn"),
    warRoomBankSelect: document.getElementById("warRoomBankSelect"),
    warRoomTopicSelect: document.getElementById("warRoomTopicSelect"),
    warRoomModeGrid: document.getElementById("warRoomModeGrid"),
    warRoomPersonaBox: document.getElementById("warRoomPersonaBox"),
    warRoomPersonaChips: document.getElementById("warRoomPersonaChips"),
    launchWarRoomBtn: document.getElementById("launchWarRoomBtn"),
    launchWarRoomBtnLabel: document.getElementById("launchWarRoomBtnLabel"),
    inspectorBody: document.getElementById("inspectorBody"),
    inspectorSubtitle: document.getElementById("inspectorSubtitle"),
    chatScroll: document.getElementById("chatScroll"),
    welcomeState: document.getElementById("welcomeState"),
    starterGrid: document.getElementById("starterGrid"),
    messagesList: document.getElementById("messagesList"),
    composerForm: document.getElementById("composerForm"),
    promptInput: document.getElementById("promptInput"),
    sendBtn: document.getElementById("sendBtn"),
    snackbar: document.getElementById("snackbar"),
  };

  // ------------------------------------------------------------------------
  // Utilities
  // ------------------------------------------------------------------------

  function escapeHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  let snackbarTimer = null;
  function showSnackbar(message) {
    dom.snackbar.textContent = message;
    dom.snackbar.classList.add("visible");
    if (snackbarTimer) clearTimeout(snackbarTimer);
    snackbarTimer = setTimeout(() => {
      dom.snackbar.classList.remove("visible");
    }, 3400);
  }

  function scrollToBottom() {
    requestAnimationFrame(() => {
      dom.chatScroll.scrollTop = dom.chatScroll.scrollHeight;
    });
  }

  function shortModelName(name) {
    if (!name) return "Gemini";
    return String(name).replace("gemini-", "").replace("-preview", "");
  }

  function formatAgentName(name) {
    const map = {
      bacen_coordinator: "Coordenador",
      knowledge_agent: "Glossário BCB",
      quick_data_agent: "Consulta Rápida",
      data_collector: "Coleta MCP",
      fintech_analyst: "Analista Pro",
      quality_critic: "Quality Critic",
      report_publisher: "Publicação",
      gcp_advisory_pipeline: "Consultoria GCP",
      gcp_data_prep: "Dados BCB (Prep)",
      gcp_cloud_consultant: "Consultor Google Cloud (Pro)",
      gcp_advisory_critic: "Quality Critic GCP",
      gcp_advisory_publisher: "Publicação Plano GCP",
      boardroom_warroom_pipeline: "Boardroom War Room",
      warroom_data_prep: "Dados BCB (War Room)",
      warroom_c_level_panel: "Comitê C-Level (Paralelo)",
      persona_cto: "Persona CTO",
      persona_cro: "Persona CRO / Compliance",
      persona_cfo: "Persona CFO",
      warroom_pitch_coach: "Pitch Coach GCP (Pro)",
      warroom_critic: "Quality Critic War Room",
      warroom_publisher: "Publicação Dossiê War Room",
      boardroom_roleplay_agent: "Roleplay Executivo 1:1 (Pro)",
    };
    return map[name] || name;
  }

  const SUPPORTED_BANKS = [
    { code: "NUBANK", label: "Nubank", patterns: ["nubank"] },
    { code: "ITAU", label: "Itaú", patterns: ["itaú", "itau"] },
    { code: "BRADESCO", label: "Bradesco", patterns: ["bradesco"] },
    { code: "INTER", label: "Inter", patterns: ["inter"] },
    { code: "C6_BANK", label: "C6 Bank", patterns: ["c6 bank", "c6_bank", "c6"] },
    { code: "MERCADO_PAGO", label: "Mercado Pago", patterns: ["mercado pago", "mercado_pago"] },
    { code: "BANCO_DO_BRASIL", label: "Banco do Brasil", patterns: ["banco do brasil", "banco_do_brasil"] },
    { code: "SANTANDER", label: "Santander", patterns: ["santander"] },
    { code: "CAIXA", label: "Caixa", patterns: ["caixa"] },
    { code: "BTG_PACTUAL", label: "BTG Pactual", patterns: ["btg"] },
  ];

  function orderBanksForText(text) {
    const lower = String(text || "").toLowerCase();
    const detected = [];
    const others = [];
    for (const b of SUPPORTED_BANKS) {
      const hit = b.patterns.some((p) => lower.includes(p));
      if (hit) detected.push({ ...b, detected: true });
      else others.push({ ...b, detected: false });
    }
    return [...detected, ...others];
  }

  function inferTitleFromMarkdown(markdown, fallbackPrompt) {
    const lines = String(markdown || "").split("\n");
    for (const line of lines) {
      const m = line.trim().match(/^#{1,3}\s+(.+)$/);
      if (m) {
        return m[1].replace(/[*`_]/g, "").trim();
      }
    }
    return (fallbackPrompt || "Relatório Bacen Fintech Advisor").slice(0, 90);
  }

  // Safe Markdown renderer (uses Marked.js when loaded, with built-in fallback).
  function renderMarkdownSafe(markdown) {
    const raw = String(markdown || "");
    // Escape raw HTML tags upfront to prevent XSS while preserving Markdown syntax.
    const sanitized = raw.replace(/</g, "&lt;").replace(/>/g, "&gt;");

    let html;
    if (window.marked && typeof window.marked.parse === "function") {
      // Restore markdown blockquotes (`> ` at line start) safely.
      const withQuotes = sanitized.replace(/(^|\n)&gt;\s?/g, "$1> ");
      html = window.marked.parse(withQuotes, { gfm: true, breaks: false });
    } else {
      // Lightweight offline fallback renderer.
      html = sanitized
        .replace(/^### (.+)$/gm, "<h3>$1</h3>")
        .replace(/^## (.+)$/gm, "<h2>$1</h2>")
        .replace(/^# (.+)$/gm, "<h1>$1</h1>")
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.+?)\*/g, "<em>$1</em>")
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\n\n+/g, "</p><p>")
        .replace(/\n/g, "<br/>");
      html = `<p>${html}</p>`;
    }

    // Wrap tables in responsive scroll container.
    const wrapper = document.createElement("div");
    wrapper.innerHTML = html;
    wrapper.querySelectorAll("table").forEach((tbl) => {
      const container = document.createElement("div");
      container.className = "table-wrap";
      tbl.parentNode.insertBefore(container, tbl);
      container.appendChild(tbl);
    });
    wrapper.querySelectorAll("a").forEach((a) => {
      const href = (a.getAttribute("href") || "").trim();
      if (!/^https?:\/\//i.test(href) && !/^mailto:/i.test(href)) {
        a.removeAttribute("href");
      } else {
        a.setAttribute("target", "_blank");
        a.setAttribute("rel", "noopener noreferrer");
      }
    });
    return wrapper.innerHTML;
  }

  // ------------------------------------------------------------------------
  // Auth Gate Helpers (Google Sign-In + Optional Token Fallback)
  // ------------------------------------------------------------------------

  let googleButtonInitialized = false;
  let activeGoogleClientId = null;

  function renderUserPill(user) {
    if (!user || !user.email) {
      dom.userPill.classList.add("hidden");
      dom.openAdminBtn.classList.add("hidden");
      return;
    }
    dom.openAdminBtn.classList.toggle("hidden", !user.is_admin);
    dom.userPill.classList.remove("hidden");
    dom.userPill.title = user.email;
    const displayName = user.name || user.email.split("@")[0];
    dom.userPillName.textContent = displayName;
    if (user.picture && /^https:\/\//i.test(user.picture)) {
      dom.userAvatarImg.src = user.picture;
      dom.userAvatarImg.classList.remove("hidden");
      dom.userAvatarFallback.classList.add("hidden");
    } else {
      dom.userAvatarImg.classList.add("hidden");
      dom.userAvatarFallback.textContent = displayName.charAt(0).toUpperCase();
      dom.userAvatarFallback.classList.remove("hidden");
    }
  }

  function showAuthOverlay(errorMsg) {
    dom.authOverlay.classList.remove("hidden");
    if (errorMsg) {
      dom.authErrorMsg.textContent = errorMsg;
      dom.authErrorMsg.classList.remove("hidden");
    } else {
      dom.authErrorMsg.classList.add("hidden");
    }
    if (!dom.authForm.classList.contains("hidden")) {
      setTimeout(() => dom.authTokenInput.focus(), 60);
    }
  }

  function hideAuthOverlay() {
    dom.authOverlay.classList.add("hidden");
    dom.authErrorMsg.classList.add("hidden");
    dom.authTokenInput.value = "";
  }

  async function handleGoogleCredentialResponse(response) {
    if (!response || !response.credential) return;
    dom.authErrorMsg.classList.add("hidden");
    try {
      const resp = await fetch("/api/auth/google", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credential: response.credential }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(data.detail || "Conta Google não autorizada.");
      }
      hideAuthOverlay();
      dom.logoutBtn.classList.remove("hidden");
      renderUserPill(data.user);
      showSnackbar(`Bem-vindo(a), ${(data.user && data.user.name) || "usuário"}!`);
      loadHealth();
      loadSessions();
    } catch (err) {
      showAuthOverlay(err.message || "Falha ao validar login com o Google.");
    }
  }

  function initGoogleSignInButton(clientId, attempt = 0) {
    if (!clientId) return;
    activeGoogleClientId = clientId;
    if (window.google && window.google.accounts && window.google.accounts.id) {
      if (!googleButtonInitialized) {
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: handleGoogleCredentialResponse,
          ux_mode: "popup",
        });
        dom.googleSignInBtn.innerHTML = "";
        window.google.accounts.id.renderButton(dom.googleSignInBtn, {
          type: "standard",
          theme: "outline",
          size: "large",
          text: "signin_with",
          shape: "pill",
          logo_alignment: "left",
          width: 320,
          locale: "pt-BR",
        });
        googleButtonInitialized = true;
      }
      return;
    }
    if (attempt < 40) {
      setTimeout(() => initGoogleSignInButton(clientId, attempt + 1), 150);
    } else {
      showAuthOverlay("Não foi possível carregar o botão 'Entrar com Google'. Recarregue a página.");
    }
  }

  async function checkAuthAndBoot() {
    try {
      const resp = await fetch("/api/auth/status");
      if (resp.ok) {
        const data = await resp.json();
        dom.logoutBtn.classList.toggle("hidden", !data.auth_enabled);
        renderUserPill(data.user);

        const hasGoogle = Boolean(data.google_client_id);
        const hasToken = Boolean(data.token_login_enabled);
        dom.googleSignInWrap.classList.toggle("hidden", !hasGoogle);
        dom.authForm.classList.toggle("hidden", !hasToken);
        dom.authDivider.classList.toggle("hidden", !(hasGoogle && hasToken));

        if (!hasGoogle && hasToken) {
          dom.authSubtitle.textContent =
            "Informe a senha/token de acesso para abrir o painel de inteligência competitiva BCB & Consultor Google Cloud.";
        }
        if (hasGoogle) {
          initGoogleSignInButton(data.google_client_id);
        }
        if (data.auth_enabled && !data.authenticated) {
          showAuthOverlay("");
          return;
        }
      }
    } catch (_err) {
      // Fall through to standard health check.
    }
    hideAuthOverlay();
    loadHealth();
    loadSessions();
  }

  // ------------------------------------------------------------------------
  // Admin Allowlist Panel (visible only to configured admins)
  // ------------------------------------------------------------------------

  function renderAdminAllowlist(data) {
    const adminsSet = new Set((data.admins || []).map((e) => e.toLowerCase()));
    const entries = [
      ...(data.domains || []).map((v) => ({ value: v, kind: "domain" })),
      ...(data.emails || []).map((v) => ({ value: v, kind: "email" })),
    ];
    dom.adminTotalCount.textContent = String(entries.length);
    if (data.storage === "secret_manager" && data.secret_id) {
      dom.adminStorageHint.textContent = `Secret Manager (${data.secret_id}) · efeito imediato`;
    } else {
      dom.adminStorageHint.textContent = "Allowlist em memória (ambiente local)";
    }

    dom.adminAllowlistItems.innerHTML = "";
    for (const item of entries) {
      const isAdminEntry = adminsSet.has(item.value.toLowerCase());
      const li = document.createElement("li");
      li.className = "admin-list-item";
      const iconName = item.kind === "domain" ? "domain" : isAdminEntry ? "verified_user" : "person";
      li.innerHTML = `
        <div class="admin-entry-meta">
          <span class="material-symbols-outlined">${iconName}</span>
          <span class="admin-entry-value">${escapeHtml(item.value)}</span>
        </div>
        ${
          isAdminEntry
            ? `<span class="admin-badge">Admin</span>`
            : `<button class="admin-revoke-btn" type="button" data-revoke="${escapeHtml(item.value)}">
                 <span class="material-symbols-outlined" style="font-size:15px">delete_outline</span>
                 <span>Revogar</span>
               </button>`
        }
      `;
      const revBtn = li.querySelector("[data-revoke]");
      if (revBtn) {
        revBtn.addEventListener("click", () => revokeAllowlistEntry(item.value, revBtn));
      }
      dom.adminAllowlistItems.appendChild(li);
    }
  }

  async function openAdminModal() {
    dom.adminErrorMsg.classList.add("hidden");
    dom.adminModalBackdrop.classList.remove("hidden");
    try {
      const resp = await fetch("/api/admin/allowlist");
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.detail || "Sem permissão de administrador.");
      renderAdminAllowlist(data);
      dom.adminEntryInput.focus();
    } catch (err) {
      dom.adminErrorMsg.textContent = err.message || "Falha ao carregar allowlist.";
      dom.adminErrorMsg.classList.remove("hidden");
    }
  }

  function closeAdminModal() {
    dom.adminModalBackdrop.classList.add("hidden");
    dom.adminEntryInput.value = "";
    dom.adminErrorMsg.classList.add("hidden");
  }

  async function addAllowlistEntry(entry) {
    dom.adminErrorMsg.classList.add("hidden");
    dom.adminAddBtn.disabled = true;
    try {
      const resp = await fetch("/api/admin/allowlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entry }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.detail || "Não foi possível liberar este acesso.");
      renderAdminAllowlist(data);
      dom.adminEntryInput.value = "";
      showSnackbar(`Acesso liberado para ${entry}`);
    } catch (err) {
      dom.adminErrorMsg.textContent = err.message || "Erro ao adicionar entrada.";
      dom.adminErrorMsg.classList.remove("hidden");
    } finally {
      dom.adminAddBtn.disabled = false;
    }
  }

  async function revokeAllowlistEntry(entry, btnEl) {
    dom.adminErrorMsg.classList.add("hidden");
    btnEl.disabled = true;
    try {
      const resp = await fetch("/api/admin/allowlist", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entry }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.detail || "Não foi possível revogar acesso.");
      renderAdminAllowlist(data);
      showSnackbar(`Acesso revogado para ${entry}`);
    } catch (err) {
      dom.adminErrorMsg.textContent = err.message || "Erro ao revogar acesso.";
      dom.adminErrorMsg.classList.remove("hidden");
      btnEl.disabled = false;
    }
  }

  // ------------------------------------------------------------------------
  // API Calls
  // ------------------------------------------------------------------------

  async function loadHealth() {
    try {
      const resp = await fetch("/api/health");
      if (resp.status === 401) {
        showAuthOverlay("Sessão expirada. Faça login novamente.");
        return;
      }
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      if (data.models) {
        state.models = data.models;
        const flashLabel = shortModelName(data.models.router);
        const proLabel = shortModelName(data.models.analyst);
        const summary = `${flashLabel} · ${proLabel}`;
        dom.modelRoutingText.textContent = summary;
        dom.sidebarModelsText.textContent = `Gemini ${summary}`;
      }
      dom.mcpStatusChip.classList.remove("online", "offline");
      if (data.mcp_healthy === true) {
        dom.mcpStatusChip.classList.add("online");
        dom.mcpStatusText.textContent = "MCP BCB Online";
      } else if (data.mcp_healthy === false) {
        dom.mcpStatusChip.classList.add("offline");
        dom.mcpStatusText.textContent = "MCP Offline";
      } else {
        dom.mcpStatusText.textContent = "MCP Configurado";
      }
    } catch (_err) {
      dom.mcpStatusChip.classList.add("offline");
      dom.mcpStatusText.textContent = "Backend Indisponível";
    }
  }

  async function loadSessions() {
    try {
      const resp = await fetch("/api/sessions");
      if (!resp.ok) return;
      const data = await resp.json();
      state.sessions = data.sessions || [];
      renderSessionList();
    } catch (_err) {
      // Ignore transient errors on initial load.
    }
  }

  async function openSession(sessionId) {
    if (state.isStreaming) return;
    try {
      const resp = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`);
      if (!resp.ok) throw new Error("Sessão não encontrada");
      const data = await resp.json();
      state.activeSessionId = data.session_id;
      state.turns = data.turns || [];
      dom.activeSessionTitle.textContent = data.title || "Análise BCB";
      renderSessionList();
      renderAllTurns();
      closeMobileSidebar();
    } catch (err) {
      showSnackbar(err.message || "Falha ao abrir sessão.");
    }
  }

  async function startNewSession() {
    if (state.isStreaming) return;
    state.activeSessionId = null;
    state.turns = [];
    state.selectedTraceId = null;
    dom.activeSessionTitle.textContent = "Nova análise BCB";
    renderSessionList();
    renderAllTurns();
    renderInspector(null);
    closeMobileSidebar();
    dom.promptInput.focus();
  }

  async function deleteSession(sessionId, ev) {
    ev.stopPropagation();
    if (state.isStreaming) return;
    try {
      await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
      if (state.activeSessionId === sessionId) {
        await startNewSession();
      }
      await loadSessions();
      showSnackbar("Sessão removida.");
    } catch (_err) {
      showSnackbar("Erro ao remover sessão.");
    }
  }

  async function exportTurnPdf(turn, buttonEl) {
    const originalHtml = buttonEl.innerHTML;
    buttonEl.disabled = true;
    buttonEl.innerHTML = `<span class="material-symbols-outlined">hourglass_top</span><span>Gerando PDF...</span>`;

    try {
      const title = inferTitleFromMarkdown(turn.assistant_text, turn.user_message);
      const payload = {
        title,
        markdown: turn.assistant_text,
        prompt: turn.user_message || "",
        agents: turn.agents || [],
        models: turn.models || [],
        tool_calls_count: (turn.tool_calls || []).length,
        latency_s: turn.latency_s ?? null,
        critic_verdict: turn.critic_verdict || null,
        session_id: state.activeSessionId || "",
      };

      const resp = await fetch("/api/export/pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (resp.status === 401) {
        showAuthOverlay("Sessão expirada. Faça login novamente.");
        return;
      }
      if (!resp.ok) {
        throw new Error(`Erro HTTP ${resp.status} ao gerar PDF`);
      }

      const blob = await resp.blob();
      const cd = resp.headers.get("Content-Disposition") || "";
      const filenameMatch = cd.match(/filename="([^"]+)"/);
      const filename = filenameMatch ? filenameMatch[1] : "bacen-fintech-report.pdf";

      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);

      showSnackbar(`PDF gerado: ${filename}`);
    } catch (err) {
      showSnackbar(err.message || "Falha ao exportar PDF.");
    } finally {
      buttonEl.disabled = false;
      buttonEl.innerHTML = originalHtml;
    }
  }

  // ------------------------------------------------------------------------
  // Rendering: Sidebar & Inspector
  // ------------------------------------------------------------------------

  function renderSessionList() {
    dom.sessionList.innerHTML = "";
    if (!state.sessions.length) {
      dom.sessionList.innerHTML = `<div class="session-empty-hint">Nenhuma análise anterior ainda.</div>`;
      return;
    }

    for (const s of state.sessions) {
      const btn = document.createElement("div");
      btn.className = `session-item${s.session_id === state.activeSessionId ? " active" : ""}`;
      btn.setAttribute("role", "button");
      btn.setAttribute("tabindex", "0");
      btn.innerHTML = `
        <span class="material-symbols-outlined">chat_bubble_outline</span>
        <span class="session-item-title">${escapeHtml(s.title)}</span>
        <button class="session-delete-btn" type="button" title="Excluir sessão" aria-label="Excluir sessão">
          <span class="material-symbols-outlined" style="font-size:16px">delete_outline</span>
        </button>
      `;
      btn.addEventListener("click", () => openSession(s.session_id));
      btn.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openSession(s.session_id);
        }
      });
      btn.querySelector(".session-delete-btn").addEventListener("click", (ev) =>
        deleteSession(s.session_id, ev)
      );
      dom.sessionList.appendChild(btn);
    }
  }

  function renderInspector(turn) {
    if (!turn) {
      dom.inspectorSubtitle.textContent = "Selecione uma resposta para inspecionar";
      dom.inspectorBody.innerHTML = `
        <div class="inspector-empty">
          <span class="material-symbols-outlined">analytics</span>
          <p>Clique em <strong>Ver rastreamento</strong> em qualquer resposta para visualizar o grafo de agentes, chamadas MCP BCB e o veredito do Quality Critic.</p>
        </div>`;
      return;
    }

    state.selectedTraceId = turn.id;
    dom.inspectorSubtitle.textContent = turn.latency_s
      ? `Concluído em ${turn.latency_s}s · ${(turn.tool_calls || []).length} tool(s)`
      : `${(turn.agents || []).length} agente(s) · ${(turn.tool_calls || []).length} tool(s)`;

    const sections = [];

    // 1. Agents Orchestration Card
    const agentsHtml = (turn.agents || [])
      .map((ag) => {
        const isPro = ag === "fintech_analyst" || ag === "gcp_cloud_consultant";
        const modelTag = isPro
          ? `<span class="model-tag pro">Gemini Pro</span>`
          : `<span class="model-tag">Gemini Flash</span>`;
        return `<li><code>${escapeHtml(ag)}</code>${modelTag}</li>`;
      })
      .join("");

    sections.push(`
      <div class="inspector-card">
        <h3>Orquestração Multi-Agente</h3>
        <ul class="agent-timeline">${agentsHtml || "<li>Nenhum agente registrado</li>"}</ul>
      </div>
    `);

    // 2. Critic Verdict Card
    if (turn.critic_verdict) {
      const v = turn.critic_verdict;
      const approved = Boolean(v.approved);
      const pillClass = approved ? "approved" : "flagged";
      const pillLabel = approved ? "Aprovado" : "Revisado com ressalvas";
      const issues = Array.isArray(v.issues) ? v.issues : [];
      const issuesHtml = issues.length
        ? `<ul style="margin:8px 0 0;padding-left:18px;font-size:12px;color:#444746">${issues
            .map(
              (iss) =>
                `<li><strong>${escapeHtml(iss.problem)}</strong>: ${escapeHtml(iss.claim)} — <em>${escapeHtml(iss.fix)}</em></li>`
            )
            .join("")}</ul>`
        : `<p style="margin:8px 0 0;font-size:12px;color:#137333">Nenhuma inconsistência numérica ou de fonte detectada.</p>`;

      sections.push(`
        <div class="inspector-card">
          <h3>Quality Critic (LLM-as-Judge)</h3>
          <div class="verdict-pill ${pillClass}" style="margin-bottom:8px">
            <span class="material-symbols-outlined">${approved ? "verified" : "warning"}</span>
            <span>${pillLabel} · Groundedness ${escapeHtml(v.groundedness_score)}/5</span>
          </div>
          <p style="margin:0;font-size:12.5px;color:#3c4043">${escapeHtml(v.summary || "")}</p>
          ${issuesHtml}
        </div>
      `);
    }

    // 3. Tool Calls Card
    const tools = turn.tool_calls || [];
    const toolsHtml = tools.length
      ? tools
          .map(
            (tc) => `
          <details class="tool-detail-item">
            <summary>
              <span><code>${escapeHtml(tc.name)}</code></span>
              <span class="model-tag">${escapeHtml(tc.status || "ok")}</span>
            </summary>
            ${tc.summary ? `<div class="tool-summary-note">${escapeHtml(tc.summary)}</div>` : ""}
            <pre>${escapeHtml(JSON.stringify(tc.args || {}, null, 2))}</pre>
          </details>`
          )
          .join("")
      : `<p style="margin:0;font-size:12.5px;color:#5f6368">Nenhuma ferramenta externa chamada neste turno (dados reutilizados do estado da sessão ou guardrail).</p>`;

    sections.push(`
      <div class="inspector-card">
        <h3>Chamadas de Ferramentas (${tools.length})</h3>
        ${toolsHtml}
      </div>
    `);

    dom.inspectorBody.innerHTML = sections.join("");
  }

  // ------------------------------------------------------------------------
  // Rendering: Conversation Thread
  // ------------------------------------------------------------------------

  function renderAllTurns() {
    dom.messagesList.innerHTML = "";
    const hasTurns = state.turns.length > 0;
    dom.welcomeState.classList.toggle("hidden", hasTurns);

    for (const turn of state.turns) {
      if (turn.user_message) {
        dom.messagesList.appendChild(createUserBubbleEl(turn.user_message));
      }
      if (turn.confirmation) {
        dom.messagesList.appendChild(createConfirmationCardEl(turn.confirmation));
      }
      if (turn.assistant_text) {
        dom.messagesList.appendChild(createAssistantCardEl(turn));
      }
    }
    scrollToBottom();
  }

  function createUserBubbleEl(text) {
    const row = document.createElement("div");
    row.className = "msg-user-row";
    row.innerHTML = `<div class="msg-user-bubble">${escapeHtml(text)}</div>`;
    return row;
  }

  function createAssistantCardEl(turn) {
    const card = document.createElement("article");
    card.className = "msg-assistant-card";

    const agentsCount = (turn.agents || []).length;
    const toolsCount = (turn.tool_calls || []).length;
    const metaParts = [];
    if (agentsCount) metaParts.push(`${agentsCount} agente${agentsCount > 1 ? "s" : ""}`);
    if (toolsCount) metaParts.push(`${toolsCount} consulta${toolsCount > 1 ? "s" : ""} MCP/tool`);
    if (turn.latency_s != null) metaParts.push(`${Number(turn.latency_s).toFixed(1)}s`);

    let verdictBadgeHtml = "";
    if (turn.critic_verdict) {
      const ok = Boolean(turn.critic_verdict.approved);
      const score = turn.critic_verdict.groundedness_score;
      verdictBadgeHtml = `
        <span class="verdict-pill ${ok ? "approved" : "flagged"}" title="${escapeHtml(turn.critic_verdict.summary || "")}">
          <span class="material-symbols-outlined">${ok ? "verified" : "warning"}</span>
          <span>${ok ? "Verificado" : "Ressalva"} · ${escapeHtml(score)}/5</span>
        </span>`;
    }

    card.innerHTML = `
      <div class="assistant-header">
        <div class="assistant-identity">
          <div class="assistant-avatar" aria-hidden="true">
            <span class="material-symbols-outlined">smart_toy</span>
          </div>
          <div>
            <div class="assistant-name">Bacen Fintech Advisor</div>
            <div class="assistant-meta-line">${escapeHtml(metaParts.join(" · ") || "Resposta direta")}</div>
          </div>
        </div>
        <div class="assistant-badges">${verdictBadgeHtml}</div>
      </div>

      <div class="assistant-content">${renderMarkdownSafe(turn.assistant_text)}</div>

      <div class="assistant-actions">
        <div class="action-group">
          <button class="btn-pdf-export" type="button" data-action="export-pdf">
            <span class="material-symbols-outlined">picture_as_pdf</span>
            <span>Exportar PDF</span>
          </button>
          <button class="btn-gcp-advisory" type="button" data-action="gcp-plan" title="Gerar iniciativas e casos de uso Google Cloud a partir desta análise">
            <span class="material-symbols-outlined">cloud_done</span>
            <span>Plano Google Cloud</span>
          </button>
          <button class="btn-whatif-action" type="button" data-action="open-whatif" title="Abrir simulador interativo What-If de ranking BCB">
            <span class="material-symbols-outlined">tune</span>
            <span>Simular What-If</span>
          </button>
          <button class="btn-warroom-action" type="button" data-action="open-warroom" title="Abrir Boardroom War Room C-Level (CTO · CRO · CFO)">
            <span class="material-symbols-outlined">groups</span>
            <span>War Room C-Level</span>
          </button>
          <button class="btn-secondary" type="button" data-action="copy-md">
            <span class="material-symbols-outlined">content_copy</span>
            <span>Copiar</span>
          </button>
          <button class="btn-secondary" type="button" data-action="inspect-trace">
            <span class="material-symbols-outlined">account_tree</span>
            <span>Ver rastreamento</span>
          </button>
        </div>
      </div>

      <div class="gcp-bank-picker" data-role="gcp-bank-picker">
        <div class="gcp-bank-picker-label">
          <span class="material-symbols-outlined">auto_awesome</span>
          <span>Selecione o banco-alvo para o Consultor Sênior Google Cloud:</span>
        </div>
        <div class="gcp-bank-chips">
          ${orderBanksForText(`${turn.user_message || ""} ${turn.assistant_text || ""}`)
            .map(
              (b) =>
                `<button class="bank-chip${b.detected ? " detected" : ""}" type="button" data-bank-label="${escapeHtml(b.label)}">${escapeHtml(b.label)}</button>`
            )
            .join("")}
        </div>
      </div>
    `;

    const pdfBtn = card.querySelector('[data-action="export-pdf"]');
    pdfBtn.addEventListener("click", () => exportTurnPdf(turn, pdfBtn));

    const gcpBtn = card.querySelector('[data-action="gcp-plan"]');
    const bankPicker = card.querySelector('[data-role="gcp-bank-picker"]');
    gcpBtn.addEventListener("click", () => {
      bankPicker.classList.toggle("open");
    });

    const detectedBanks = orderBanksForText(`${turn.user_message || ""} ${turn.assistant_text || ""}`);
    const preferredBankCode = detectedBanks.length && detectedBanks[0].detected ? detectedBanks[0].code : "BRADESCO";

    const whatIfCardBtn = card.querySelector('[data-action="open-whatif"]');
    if (whatIfCardBtn) {
      whatIfCardBtn.addEventListener("click", () => openWhatIfModal(preferredBankCode));
    }

    const warRoomCardBtn = card.querySelector('[data-action="open-warroom"]');
    if (warRoomCardBtn) {
      warRoomCardBtn.addEventListener("click", () => openWarRoomModal(preferredBankCode));
    }
    bankPicker.querySelectorAll(".bank-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const bankLabel = chip.getAttribute("data-bank-label");
        bankPicker.classList.remove("open");
        if (bankLabel && !state.isStreaming) {
          sendPrompt(
            `Com base nos dados do Banco Central coletados, atue como consultor sênior de Google Cloud e gere um plano priorizado de oportunidades, arquiteturas de referência e casos de uso para o ${bankLabel}.`
          );
        }
      });
    });

    const copyBtn = card.querySelector('[data-action="copy-md"]');
    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(turn.assistant_text || "");
        copyBtn.innerHTML = `<span class="material-symbols-outlined">check</span><span>Copiado!</span>`;
        showSnackbar("Conteúdo Markdown copiado.");
        setTimeout(() => {
          copyBtn.innerHTML = `<span class="material-symbols-outlined">content_copy</span><span>Copiar</span>`;
        }, 2000);
      } catch (_err) {
        showSnackbar("Não foi possível copiar para a área de transferência.");
      }
    });

    const inspectBtn = card.querySelector('[data-action="inspect-trace"]');
    inspectBtn.addEventListener("click", () => {
      renderInspector(turn);
      dom.appShell.classList.add("inspector-open");
      dom.toggleInspectorBtn.classList.add("active");
    });

    return card;
  }

  function createConfirmationCardEl(conf) {
    const card = document.createElement("div");
    card.className = "hitl-card";
    const titleArg = conf.args && conf.args.title ? conf.args.title : "Relatório Executivo BCB";
    card.innerHTML = `
      <div class="hitl-header">
        <span class="material-symbols-outlined">shield</span>
        <span>Aprovação Humana Necessária (HITL)</span>
      </div>
      <div class="hitl-body">
        <p style="margin:0 0 8px">${escapeHtml(conf.hint || "Confirme para executar a ação de escrita no Cloud Storage.")}</p>
        <div class="hitl-meta">
          <div><strong>Ferramenta:</strong> <code>${escapeHtml(conf.tool_name || "export_report_to_gcs")}</code></div>
          <div><strong>Título:</strong> ${escapeHtml(titleArg)}</div>
        </div>
        <div class="hitl-actions">
          <button class="btn-pdf-export" type="button" data-hitl="approve">
            <span class="material-symbols-outlined">check_circle</span>
            <span>Aprovar e Exportar</span>
          </button>
          <button class="btn-secondary" type="button" data-hitl="reject">
            <span class="material-symbols-outlined">cancel</span>
            <span>Cancelar</span>
          </button>
        </div>
      </div>
    `;

    card.querySelector('[data-hitl="approve"]').addEventListener("click", () => {
      card.remove();
      sendConfirmation(conf.call_id, true);
    });
    card.querySelector('[data-hitl="reject"]').addEventListener("click", () => {
      card.remove();
      sendConfirmation(conf.call_id, false);
    });
    return card;
  }

  function createLiveProgressCard() {
    const card = document.createElement("div");
    card.className = "progress-card";
    card.innerHTML = `
      <div class="progress-bar-track"><div class="progress-bar-fill"></div></div>
      <div class="progress-body">
        <div class="progress-top">
          <div class="progress-headline">
            <span class="material-symbols-outlined">sync</span>
            <span class="progress-label">Iniciando orquestração multi-agente...</span>
          </div>
          <span class="progress-timer">0s</span>
        </div>
        <div class="step-trail"></div>
        <div class="live-tools"></div>
      </div>
    `;
    return card;
  }

  // ------------------------------------------------------------------------
  // Streaming Execution (SSE over fetch)
  // ------------------------------------------------------------------------

  async function runStreamRequest(bodyPayload, userDisplayPrompt) {
    if (state.isStreaming) return;
    state.isStreaming = true;
    updateSendButtonState();

    dom.welcomeState.classList.add("hidden");
    if (userDisplayPrompt) {
      dom.messagesList.appendChild(createUserBubbleEl(userDisplayPrompt));
      if (!state.activeSessionId || dom.activeSessionTitle.textContent === "Nova análise BCB") {
        dom.activeSessionTitle.textContent =
          userDisplayPrompt.length > 58 ? userDisplayPrompt.slice(0, 58) + "..." : userDisplayPrompt;
      }
    }

    const progressEl = createLiveProgressCard();
    const labelEl = progressEl.querySelector(".progress-label");
    const timerEl = progressEl.querySelector(".progress-timer");
    const trailEl = progressEl.querySelector(".step-trail");
    const toolsEl = progressEl.querySelector(".live-tools");
    dom.messagesList.appendChild(progressEl);
    scrollToBottom();

    const startTs = Date.now();
    const timerInterval = setInterval(() => {
      const secs = Math.floor((Date.now() - startTs) / 1000);
      timerEl.textContent = `${secs}s`;
    }, 500);

    const visitedSteps = new Map();
    const liveToolRows = new Map();

    function markAgentStep(agent, tier) {
      // Mark previous active step done
      visitedSteps.forEach((pill) => {
        if (pill.classList.contains("active")) {
          pill.classList.remove("active");
          pill.classList.add("done");
        }
      });
      if (!visitedSteps.has(agent)) {
        const pill = document.createElement("span");
        pill.className = "step-pill active";
        pill.innerHTML = `<span>${escapeHtml(formatAgentName(agent))}</span><span class="tier-tag">${escapeHtml(tier || "Flash")}</span>`;
        trailEl.appendChild(pill);
        visitedSteps.set(agent, pill);
      } else {
        const existing = visitedSteps.get(agent);
        existing.classList.remove("done");
        existing.classList.add("active");
      }
    }

    try {
      const resp = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(bodyPayload),
      });

      if (resp.status === 401) {
        showAuthOverlay("Sessão expirada. Faça login novamente.");
        throw new Error("Sessão expirada. Faça login novamente.");
      }
      if (!resp.ok || !resp.body) {
        throw new Error(`Falha HTTP ${resp.status} ao conectar com o agente.`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const rawBlock = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          handleSseBlock(rawBlock);
        }
      }
    } catch (err) {
      progressEl.remove();
      const errCard = document.createElement("div");
      errCard.className = "msg-error-card";
      errCard.innerHTML = `<span class="material-symbols-outlined">error</span><div>${escapeHtml(err.message || "Erro na comunicação.")}</div>`;
      dom.messagesList.appendChild(errCard);
    } finally {
      clearInterval(timerInterval);
      if (progressEl.isConnected) progressEl.remove();
      state.isStreaming = false;
      updateSendButtonState();
      scrollToBottom();
      loadSessions();
    }

    function handleSseBlock(block) {
      let eventName = "message";
      const dataLines = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) {
          eventName = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trim());
        }
      }
      if (!dataLines.length) return;
      let payload;
      try {
        payload = JSON.parse(dataLines.join("\n"));
      } catch (_err) {
        return;
      }

      if (payload.session_id && !state.activeSessionId) {
        state.activeSessionId = payload.session_id;
      }

      if (eventName === "status") {
        labelEl.textContent = payload.label || "Processando...";
        if (payload.agent) markAgentStep(payload.agent, payload.tier);
        scrollToBottom();
      } else if (eventName === "tool_call") {
        const row = document.createElement("div");
        row.className = "live-tool-row";
        row.innerHTML = `
          <span class="material-symbols-outlined" style="font-size:16px;color:#1a73e8">database</span>
          <span>Consultando <code>${escapeHtml(payload.name)}</code>...</span>
        `;
        toolsEl.appendChild(row);
        liveToolRows.set(payload.call_id || payload.name, row);
        scrollToBottom();
      } else if (eventName === "tool_result") {
        const row = liveToolRows.get(payload.call_id) || liveToolRows.get(payload.name);
        if (row) {
          const isErr = payload.status === "error";
          row.innerHTML = `
            <span class="material-symbols-outlined" style="font-size:16px;color:${isErr ? "#c5221f" : "#137333"}">${isErr ? "warning" : "check_circle"}</span>
            <span><code>${escapeHtml(payload.name)}</code> · ${escapeHtml(payload.summary || "Concluído")}</span>
          `;
        }
      } else if (eventName === "confirmation_request") {
        progressEl.remove();
        dom.messagesList.appendChild(createConfirmationCardEl(payload));
        scrollToBottom();
      } else if (eventName === "assistant_message") {
        progressEl.remove();
        const turn = {
          id: payload.message_id || String(Date.now()),
          user_message: userDisplayPrompt || payload.prompt || "",
          assistant_text: payload.text || "",
          final_agent: payload.agent,
          agents: payload.agents || [],
          models: payload.models || [],
          tool_calls: payload.tool_calls || [],
          critic_verdict: payload.critic_verdict || null,
          latency_s: payload.latency_s,
        };
        state.turns.push(turn);
        if (turn.assistant_text) {
          dom.messagesList.appendChild(createAssistantCardEl(turn));
          renderInspector(turn);
        }
        scrollToBottom();
      } else if (eventName === "error") {
        progressEl.remove();
        const errCard = document.createElement("div");
        errCard.className = "msg-error-card";
        errCard.innerHTML = `<span class="material-symbols-outlined">error</span><div>${escapeHtml(payload.message || "Erro desconhecido.")}</div>`;
        dom.messagesList.appendChild(errCard);
        scrollToBottom();
      }
    }
  }

  function sendPrompt(text) {
    const clean = text.trim();
    if (!clean || state.isStreaming) return;
    dom.promptInput.value = "";
    autoResizeTextarea();
    updateSendButtonState();
    runStreamRequest(
      { session_id: state.activeSessionId, message: clean },
      clean
    );
  }

  function sendConfirmation(callId, confirmed) {
    if (state.isStreaming) return;
    runStreamRequest(
      {
        session_id: state.activeSessionId,
        confirmation: { call_id: callId, confirmed },
      },
      confirmed ? "Aprovação HITL concedida para exportar relatório." : "Exportação cancelada pelo usuário."
    );
  }

  // ------------------------------------------------------------------------
  // UI Interactions
  // ------------------------------------------------------------------------

  function autoResizeTextarea() {
    dom.promptInput.style.height = "auto";
    dom.promptInput.style.height = Math.min(dom.promptInput.scrollHeight, 180) + "px";
  }

  function updateSendButtonState() {
    dom.sendBtn.disabled = state.isStreaming || !dom.promptInput.value.trim();
  }

  function closeMobileSidebar() {
    dom.appShell.classList.remove("mobile-sidebar-open");
  }

  function bindEvents() {
    dom.toggleSidebarBtn.addEventListener("click", () => {
      if (window.innerWidth <= 820) {
        dom.appShell.classList.toggle("mobile-sidebar-open");
      } else {
        dom.appShell.classList.toggle("sidebar-collapsed");
      }
    });

    dom.closeSidebarBtn.addEventListener("click", closeMobileSidebar);
    dom.sidebarBackdrop.addEventListener("click", closeMobileSidebar);
    dom.newSessionBtn.addEventListener("click", startNewSession);

    dom.toggleInspectorBtn.addEventListener("click", () => {
      const open = dom.appShell.classList.toggle("inspector-open");
      dom.toggleInspectorBtn.classList.toggle("active", open);
    });

    dom.closeInspectorBtn.addEventListener("click", () => {
      dom.appShell.classList.remove("inspector-open");
      dom.toggleInspectorBtn.classList.remove("active");
    });

    dom.starterGrid.querySelectorAll(".starter-card").forEach((card) => {
      card.addEventListener("click", () => {
        const modalType = card.getAttribute("data-open-modal");
        if (modalType === "whatif") {
          openWhatIfModal("BRADESCO");
          return;
        }
        if (modalType === "warroom") {
          openWarRoomModal("BRADESCO");
          return;
        }
        const prompt = card.getAttribute("data-prompt");
        if (prompt) sendPrompt(prompt);
      });
    });

    dom.promptInput.addEventListener("input", () => {
      autoResizeTextarea();
      updateSendButtonState();
    });

    dom.promptInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (!dom.sendBtn.disabled) sendPrompt(dom.promptInput.value);
      }
    });

    dom.composerForm.addEventListener("submit", (e) => {
      e.preventDefault();
      sendPrompt(dom.promptInput.value);
    });

    dom.toggleTokenVisibilityBtn.addEventListener("click", () => {
      const isPass = dom.authTokenInput.type === "password";
      dom.authTokenInput.type = isPass ? "text" : "password";
      dom.toggleTokenVisibilityBtn.querySelector("span").textContent = isPass
        ? "visibility_off"
        : "visibility";
    });

    dom.authForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const token = dom.authTokenInput.value.trim();
      if (!token) return;
      dom.authSubmitBtn.disabled = true;
      dom.authErrorMsg.classList.add("hidden");
      try {
        const resp = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });
        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          throw new Error(errData.detail || "Senha ou token inválido.");
        }
        hideAuthOverlay();
        dom.logoutBtn.classList.remove("hidden");
        showSnackbar("Acesso liberado.");
        loadHealth();
        loadSessions();
      } catch (err) {
        showAuthOverlay(err.message || "Falha na autenticação.");
      } finally {
        dom.authSubmitBtn.disabled = false;
      }
    });

    dom.logoutBtn.addEventListener("click", async () => {
      if (window.google && window.google.accounts && window.google.accounts.id) {
        window.google.accounts.id.disableAutoSelect();
      }
      await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
      state.activeSessionId = null;
      state.turns = [];
      state.sessions = [];
      renderUserPill(null);
      renderAllTurns();
      renderSessionList();
      if (activeGoogleClientId) {
        initGoogleSignInButton(activeGoogleClientId);
      }
      showAuthOverlay("");
    });

    dom.openAdminBtn.addEventListener("click", openAdminModal);
    dom.closeAdminModalBtn.addEventListener("click", closeAdminModal);
    dom.adminModalBackdrop.addEventListener("click", (e) => {
      if (e.target === dom.adminModalBackdrop) closeAdminModal();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        if (!dom.adminModalBackdrop.classList.contains("hidden")) closeAdminModal();
        if (!dom.whatIfModalBackdrop.classList.contains("hidden")) closeWhatIfModal();
        if (!dom.warRoomModalBackdrop.classList.contains("hidden")) closeWarRoomModal();
      }
    });
    dom.adminAddForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const val = dom.adminEntryInput.value.trim();
      if (val) addAllowlistEntry(val);
    });

    // What-If Simulator modal bindings
    dom.openWhatIfBtn.addEventListener("click", () => openWhatIfModal());
    dom.closeWhatIfModalBtn.addEventListener("click", closeWhatIfModal);
    dom.cancelWhatIfBtn.addEventListener("click", closeWhatIfModal);
    dom.whatIfModalBackdrop.addEventListener("click", (e) => {
      if (e.target === dom.whatIfModalBackdrop) closeWhatIfModal();
    });
    dom.whatIfBankSelect.addEventListener("change", () => {
      whatIfState.targetInstitution = dom.whatIfBankSelect.value;
      resetWhatIfOverrides();
    });
    dom.whatIfModalBackdrop.querySelectorAll("[data-preset]").forEach((btn) => {
      btn.addEventListener("click", () => applyWhatIfPreset(btn.getAttribute("data-preset")));
    });
    dom.launchWhatIfBusinessCaseBtn.addEventListener("click", launchWhatIfBusinessCase);

    // Boardroom War Room modal bindings
    dom.openWarRoomBtn.addEventListener("click", () => openWarRoomModal());
    dom.closeWarRoomModalBtn.addEventListener("click", closeWarRoomModal);
    dom.cancelWarRoomBtn.addEventListener("click", closeWarRoomModal);
    dom.warRoomModalBackdrop.addEventListener("click", (e) => {
      if (e.target === dom.warRoomModalBackdrop) closeWarRoomModal();
    });
    dom.warRoomModeGrid.querySelectorAll(".warroom-mode-card").forEach((btn) => {
      btn.addEventListener("click", () => {
        warRoomState.mode = btn.getAttribute("data-mode") || "panel";
        syncWarRoomModeUI();
      });
    });
    dom.warRoomPersonaChips.querySelectorAll(".persona-chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        warRoomState.persona = btn.getAttribute("data-persona") || "CTO (Chief Technology Officer)";
        dom.warRoomPersonaChips.querySelectorAll(".persona-chip").forEach((c) => {
          c.classList.toggle("selected", c === btn);
        });
      });
    });
    dom.launchWarRoomBtn.addEventListener("click", launchWarRoom);
  }

  // ------------------------------------------------------------------------
  // Feature 1: Interactive What-If BCB Ranking Simulator & Business Case
  // ------------------------------------------------------------------------

  const WHATIF_SLIDER_GROUPS = [
    {
      pillarKey: "reclamacoes",
      title: "Pilar 1 · Reclamações BCB (Deati)",
      sliders: [
        {
          field: "indice_reclamacoes",
          label: "Índice Reclamações (/1M clientes)",
          min: 5.0,
          max: 65.0,
          step: 0.5,
          decimals: 1,
          unit: "",
          direction: "lower_is_better",
          floorHint: "↓ Menor é melhor",
        },
      ],
    },
    {
      pillarKey: "taxas_credito",
      title: "Pilar 2 · Taxas de Crédito (Olinda)",
      sliders: [
        {
          field: "taxa_juros_mensal_pct",
          label: "Taxa Cartão Rotativo (% a.m.)",
          min: 6.0,
          max: 18.0,
          step: 0.1,
          decimals: 2,
          unit: "%",
          direction: "lower_is_better",
          floorHint: "↓ Mais competitiva",
        },
      ],
    },
    {
      pillarKey: "pix_med",
      title: "Pilar 3 · Pix, SPI & Fraudes MED",
      sliders: [
        {
          field: "disponibilidade_spi_pct",
          label: "Disponibilidade SPI (%)",
          min: 99.60,
          max: 100.0,
          step: 0.01,
          decimals: 2,
          unit: "%",
          direction: "higher_is_better",
          floorHint: "Piso BCB ≥ 99,80%",
        },
        {
          field: "med_por_100k",
          label: "Fraudes MED (/100k tx Pix)",
          min: 1.5,
          max: 12.0,
          step: 0.1,
          decimals: 1,
          unit: "",
          direction: "lower_is_better",
          floorHint: "↓ Menor fraude",
        },
        {
          field: "taxa_devolucao_med_pct",
          label: "Taxa de Devolução MED (%)",
          min: 12.0,
          max: 50.0,
          step: 0.5,
          decimals: 1,
          unit: "%",
          direction: "higher_is_better",
          floorHint: "↑ Maior recuperação",
        },
      ],
    },
    {
      pillarKey: "prudencial",
      title: "Pilar 4 · Prudencial (IF.data) & Open Finance",
      sliders: [
        {
          field: "roe_anualizado_pct",
          label: "ROE Anualizado (%)",
          min: 6.0,
          max: 35.0,
          step: 0.5,
          decimals: 1,
          unit: "%",
          direction: "higher_is_better",
          floorHint: "↑ Maior rentabilidade",
        },
        {
          field: "inadimplencia_90d_pct",
          label: "Inadimplência > 90d (%)",
          min: 1.0,
          max: 8.5,
          step: 0.1,
          decimals: 1,
          unit: "%",
          direction: "lower_is_better",
          floorHint: "↓ Carteira mais saudável",
        },
        {
          field: "disponibilidade_open_finance_pct",
          label: "Disponibilidade Open Finance (%)",
          min: 99.20,
          max: 100.0,
          step: 0.01,
          decimals: 2,
          unit: "%",
          direction: "higher_is_better",
          floorHint: "Piso BCB ≥ 99,50%",
        },
      ],
    },
  ];

  const whatIfState = {
    baseline: null,
    targetInstitution: "BRADESCO",
    overrides: {},
    lastResult: null,
    debounceTimer: null,
  };

  function bankLabelFromCode(code) {
    const found = SUPPORTED_BANKS.find((b) => b.code === code);
    return found ? found.label : code;
  }

  function populateBankSelect(selectEl, preferredCode) {
    selectEl.innerHTML = SUPPORTED_BANKS.map(
      (b) => `<option value="${escapeHtml(b.code)}">${escapeHtml(b.label)}</option>`
    ).join("");
    if (preferredCode && SUPPORTED_BANKS.some((b) => b.code === preferredCode)) {
      selectEl.value = preferredCode;
    }
  }

  function getTargetBaselineRecord() {
    if (!whatIfState.baseline || !Array.isArray(whatIfState.baseline.records)) return null;
    return (
      whatIfState.baseline.records.find((r) => r.instituicao === whatIfState.targetInstitution) ||
      whatIfState.baseline.records[0] ||
      null
    );
  }

  async function openWhatIfModal(preferredBankCode) {
    dom.whatIfModalBackdrop.classList.remove("hidden");
    const bankCode = preferredBankCode || whatIfState.targetInstitution || "BRADESCO";
    whatIfState.targetInstitution = bankCode;
    populateBankSelect(dom.whatIfBankSelect, bankCode);

    if (!whatIfState.baseline) {
      dom.whatIfBaselineMeta.textContent = "Carregando baseline oficial dos 4 pilares no MCP BCB...";
      dom.whatIfSlidersHost.innerHTML = `<p class="whatif-empty-hint" style="padding:18px">Consultando séries oficiais do Banco Central...</p>`;
      try {
        const resp = await fetch("/api/simulator/baseline?modalidade=CARTAO_ROTATIVO");
        if (resp.status === 401) {
          closeWhatIfModal();
          showAuthOverlay("Sessão expirada. Faça login novamente.");
          return;
        }
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          throw new Error(err.detail || "Falha ao carregar baseline BCB.");
        }
        whatIfState.baseline = await resp.json();
      } catch (err) {
        dom.whatIfBaselineMeta.textContent = err.message || "Não foi possível carregar o baseline BCB.";
        dom.whatIfSlidersHost.innerHTML = `<div class="whatif-alerts">${escapeHtml(err.message || "Erro ao consultar MCP BCB.")}</div>`;
        return;
      }
    }

    const meta = whatIfState.baseline;
    dom.whatIfBaselineMeta.textContent = `Baseline oficial BCB (${meta.periodo_referencia || "atual"} · ${meta.records.length} instituições · ${meta.modalidade_credito || "CARTAO_ROTATIVO"})`;
    resetWhatIfOverrides();
  }

  function closeWhatIfModal() {
    dom.whatIfModalBackdrop.classList.add("hidden");
  }

  function resetWhatIfOverrides() {
    whatIfState.overrides = {};
    renderWhatIfSliders();
    runWhatIfSimulationNow();
  }

  function applyWhatIfPreset(presetName) {
    const rec = getTargetBaselineRecord();
    if (!rec) return;
    if (presetName === "reset") {
      resetWhatIfOverrides();
      return;
    }
    const clampVal = (v, min, max, dec) => Number(Math.max(min, Math.min(max, v)).toFixed(dec));
    const ov = {};
    if (presetName === "top2") {
      if (rec.indice_reclamacoes != null) ov.indice_reclamacoes = clampVal(rec.indice_reclamacoes * 0.62, 5, 65, 1);
      if (rec.taxa_juros_mensal_pct != null) ov.taxa_juros_mensal_pct = clampVal(rec.taxa_juros_mensal_pct - 1.6, 6, 18, 2);
      if (rec.disponibilidade_spi_pct != null) ov.disponibilidade_spi_pct = clampVal(Math.max(rec.disponibilidade_spi_pct, 99.96), 99.6, 100, 2);
      if (rec.med_por_100k != null) ov.med_por_100k = clampVal(rec.med_por_100k * 0.72, 1.5, 12, 1);
      if (rec.taxa_devolucao_med_pct != null) ov.taxa_devolucao_med_pct = clampVal(rec.taxa_devolucao_med_pct * 1.35, 12, 50, 1);
      if (rec.roe_anualizado_pct != null) ov.roe_anualizado_pct = clampVal(rec.roe_anualizado_pct + 4.0, 6, 35, 1);
      if (rec.inadimplencia_90d_pct != null) ov.inadimplencia_90d_pct = clampVal(rec.inadimplencia_90d_pct * 0.78, 1, 8.5, 1);
    } else if (presetName === "pix_shock") {
      ov.disponibilidade_spi_pct = 99.98;
      if (rec.med_por_100k != null) ov.med_por_100k = clampVal(rec.med_por_100k * 0.60, 1.5, 12, 1);
      if (rec.taxa_devolucao_med_pct != null) ov.taxa_devolucao_med_pct = clampVal(rec.taxa_devolucao_med_pct * 1.45, 12, 50, 1);
      if (rec.indice_reclamacoes != null) ov.indice_reclamacoes = clampVal(rec.indice_reclamacoes * 0.82, 5, 65, 1);
    } else if (presetName === "cx_credit") {
      if (rec.indice_reclamacoes != null) ov.indice_reclamacoes = clampVal(rec.indice_reclamacoes * 0.60, 5, 65, 1);
      if (rec.taxa_juros_mensal_pct != null) ov.taxa_juros_mensal_pct = clampVal(rec.taxa_juros_mensal_pct - 2.0, 6, 18, 2);
      if (rec.inadimplencia_90d_pct != null) ov.inadimplencia_90d_pct = clampVal(rec.inadimplencia_90d_pct * 0.75, 1, 8.5, 1);
      if (rec.roe_anualizado_pct != null) ov.roe_anualizado_pct = clampVal(rec.roe_anualizado_pct + 2.5, 6, 35, 1);
    }
    whatIfState.overrides = ov;
    renderWhatIfSliders();
    runWhatIfSimulationNow();
  }

  function renderWhatIfSliders() {
    const rec = getTargetBaselineRecord();
    if (!rec) return;

    dom.whatIfSlidersHost.innerHTML = WHATIF_SLIDER_GROUPS.map((grp) => {
      const itemsHtml = grp.sliders
        .map((s) => {
          const baseVal = Number(rec[s.field] ?? s.min);
          const curVal =
            whatIfState.overrides[s.field] != null ? Number(whatIfState.overrides[s.field]) : baseVal;
          const diff = curVal - baseVal;
          const changed = Math.abs(diff) > 1e-4;
          const improved = s.direction === "lower_is_better" ? diff < 0 : diff > 0;
          const deltaHtml = changed
            ? `<span class="slider-delta ${improved ? "improved" : "worsened"}">${diff > 0 ? "+" : ""}${diff.toFixed(s.decimals)}${s.unit}</span>`
            : "";

          return `
            <div class="slider-item" data-field="${s.field}">
              <div class="slider-row-top">
                <span class="slider-label">${escapeHtml(s.label)} <span class="slider-floor-tag">(${escapeHtml(s.floorHint)})</span></span>
                <span class="slider-val-group">
                  <span class="slider-before">${baseVal.toFixed(s.decimals)}${s.unit}</span>
                  <span>→</span>
                  <span class="slider-after" data-role="val-${s.field}">${curVal.toFixed(s.decimals)}${s.unit}</span>
                  <span data-role="delta-${s.field}">${deltaHtml}</span>
                </span>
              </div>
              <input
                type="range"
                class="m3-range"
                data-slider-field="${s.field}"
                min="${s.min}"
                max="${s.max}"
                step="${s.step}"
                value="${curVal}"
              />
            </div>`;
        })
        .join("");

      return `
        <div class="slider-pillar-group">
          <div class="slider-pillar-head">
            <span class="slider-pillar-title">${escapeHtml(grp.title)}</span>
            <span class="slider-pillar-score" data-pillar-score="${grp.pillarKey}">—</span>
          </div>
          ${itemsHtml}
        </div>`;
    }).join("");

    dom.whatIfSlidersHost.querySelectorAll("[data-slider-field]").forEach((input) => {
      input.addEventListener("input", () => {
        const field = input.getAttribute("data-slider-field");
        const meta = WHATIF_SLIDER_GROUPS.flatMap((g) => g.sliders).find((s) => s.field === field);
        if (!meta) return;
        const baseVal = Number(rec[field] ?? meta.min);
        const val = Number(input.value);
        if (Math.abs(val - baseVal) < 1e-4) {
          delete whatIfState.overrides[field];
        } else {
          whatIfState.overrides[field] = val;
        }
        const valEl = dom.whatIfSlidersHost.querySelector(`[data-role="val-${field}"]`);
        const deltaEl = dom.whatIfSlidersHost.querySelector(`[data-role="delta-${field}"]`);
        if (valEl) valEl.textContent = `${val.toFixed(meta.decimals)}${meta.unit}`;
        if (deltaEl) {
          const diff = val - baseVal;
          if (Math.abs(diff) > 1e-4) {
            const improved = meta.direction === "lower_is_better" ? diff < 0 : diff > 0;
            deltaEl.innerHTML = `<span class="slider-delta ${improved ? "improved" : "worsened"}">${diff > 0 ? "+" : ""}${diff.toFixed(meta.decimals)}${meta.unit}</span>`;
          } else {
            deltaEl.innerHTML = "";
          }
        }
        scheduleWhatIfSimulation();
      });
    });
  }

  function scheduleWhatIfSimulation() {
    if (whatIfState.debounceTimer) clearTimeout(whatIfState.debounceTimer);
    whatIfState.debounceTimer = setTimeout(runWhatIfSimulationNow, 40);
  }

  async function runWhatIfSimulationNow() {
    if (!whatIfState.baseline || !whatIfState.baseline.records) return;
    try {
      const resp = await fetch("/api/simulator/what-if", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_institution: whatIfState.targetInstitution,
          overrides: whatIfState.overrides,
          benchmark_records: whatIfState.baseline.records,
        }),
      });
      if (!resp.ok) return;
      const data = await resp.json();
      whatIfState.lastResult = data;
      renderWhatIfResults(data);
    } catch (_err) {
      // Transient UI debounce error ignored gracefully.
    }
  }

  function renderWhatIfResults(res) {
    // 1. Hero Position & Score Banner
    dom.whatIfPosDisplay.textContent = `#${res.position_before} → #${res.position_after}`;
    const posGain = Number(res.positions_gained || 0);
    dom.whatIfPosDelta.textContent =
      posGain > 0 ? `+${posGain} pos.` : posGain < 0 ? `${posGain} pos.` : "sem mudança";
    dom.whatIfPosDelta.className = `kpi-delta-pill ${posGain > 0 ? "positive" : posGain < 0 ? "negative" : "neutral"}`;

    dom.whatIfScoreDisplay.textContent = `${Number(res.score_before_0_10).toFixed(2)} → ${Number(res.score_after_0_10).toFixed(2)}`;
    const sDelta = Number(res.score_delta || 0);
    dom.whatIfScoreDelta.textContent = `${sDelta > 0 ? "+" : ""}${sDelta.toFixed(2)} pts`;
    dom.whatIfScoreDelta.className = `kpi-delta-pill ${sDelta > 0 ? "positive" : sDelta < 0 ? "negative" : "neutral"}`;

    // 2. Pillar score badges inside slider groups
    (res.pillar_deltas || []).forEach((pd) => {
      const el = dom.whatIfSlidersHost.querySelector(`[data-pillar-score="${pd.pillar}"]`);
      if (!el) return;
      const d = Number(pd.delta_score || 0);
      el.textContent = `${pd.before_score.toFixed(2)} → ${pd.after_score.toFixed(2)}${Math.abs(d) > 0.005 ? ` (${d > 0 ? "+" : ""}${d.toFixed(2)})` : ""}`;
      el.className = `slider-pillar-score ${d > 0.005 ? "up" : d < -0.005 ? "down" : ""}`;
    });

    // 3. Overtaken rivals
    if (res.overtaken_competitors && res.overtaken_competitors.length) {
      const labels = res.overtaken_competitors.map(bankLabelFromCode).join(", ");
      dom.whatIfOvertakenBox.innerHTML = `<span class="material-symbols-outlined">emoji_events</span><span>Ultrapassa no ranking BCB: <strong>${escapeHtml(labels)}</strong></span>`;
      dom.whatIfOvertakenBox.classList.remove("hidden");
    } else {
      dom.whatIfOvertakenBox.classList.add("hidden");
    }

    // 4. Regulatory floor alerts
    if (res.regulatory_alerts && res.regulatory_alerts.length) {
      dom.whatIfAlertsBox.innerHTML = res.regulatory_alerts.map((a) => `<div>⚠️ ${escapeHtml(a)}</div>`).join("");
      dom.whatIfAlertsBox.classList.remove("hidden");
    } else {
      dom.whatIfAlertsBox.classList.add("hidden");
    }

    // 5. Live 10-bank leaderboard
    dom.whatIfLeaderboard.innerHTML = (res.ranking_after || [])
      .map((row) => {
        const isTarget = row.instituicao === res.target_institution;
        const pct = Math.max(8, Math.min(100, (Number(row.weighted_score_0_10) / 10.0) * 100));
        return `
          <div class="lb-row${isTarget ? " target" : ""}">
            <span class="lb-pos">#${row.position}</span>
            <span>${escapeHtml(bankLabelFromCode(row.instituicao))}</span>
            <div class="lb-bar-track"><div class="lb-bar-fill" style="width:${pct.toFixed(1)}%"></div></div>
            <span class="lb-score">${Number(row.weighted_score_0_10).toFixed(2)}</span>
          </div>`;
      })
      .join("");

    // 6. Auto-matched Google Cloud FSI blueprints
    const bps = res.recommended_gcp_blueprints || [];
    if (!bps.length) {
      dom.whatIfBlueprints.innerHTML = `<p class="whatif-empty-hint">Mova qualquer slider à esquerda (ou clique em um cenário pronto acima) para mapear automaticamente os blueprints Google Cloud habilitadores.</p>`;
    } else {
      dom.whatIfBlueprints.innerHTML = bps
        .map(
          (bp) => `
          <div class="bp-mini-card">
            <div class="bp-mini-top">
              <span class="bp-mini-title">${escapeHtml(bp.title)}</span>
              <span class="bp-mini-horizon">${escapeHtml(bp.horizon)}</span>
            </div>
            <div class="bp-mini-services">${escapeHtml((bp.gcp_services || []).join(" · "))}</div>
          </div>`
        )
        .join("");
    }
  }

  function launchWhatIfBusinessCase() {
    const res = whatIfState.lastResult;
    const bankLabel = bankLabelFromCode(whatIfState.targetInstitution);
    const changes = (res && res.metric_changes) || [];
    closeWhatIfModal();
    if (state.isStreaming) return;

    if (!changes.length) {
      sendPrompt(
        `Com base nos dados do Banco Central, atue como consultor sênior de Google Cloud e gere um plano de oportunidades, arquiteturas de referência e business case direcional para o ${bankLabel}.`
      );
      return;
    }

    const changeLines = changes
      .map((c) => `${c.label}: ${c.before_value}${c.unit} → ${c.after_value}${c.unit} (${c.delta_pct > 0 ? "+" : ""}${c.delta_pct}%)`)
      .join("; ");
    const overtakenText =
      res.overtaken_competitors && res.overtaken_competitors.length
        ? ` ultrapassando ${res.overtaken_competitors.map(bankLabelFromCode).join(", ")}`
        : "";
    sendPrompt(
      `Atue como consultor sênior de Google Cloud e gere um Business Case executivo e plano de arquiteturas Google Cloud para o ${bankLabel} com base nesta simulação What-If validada nos 4 pilares do BCB (ranking #${res.position_before} → #${res.position_after}${overtakenText}, score ${res.score_before_0_10} → ${res.score_after_0_10}): ${changeLines}. Use simulate_bcb_what_if_scenario e o catálogo oficial Google Cloud FSI para detalhar as alavancas direcionais, arquiteturas, compliance Brasil e perguntas de discovery sem fabricar percentuais de ROI.`
    );
  }

  // ------------------------------------------------------------------------
  // Feature 2: Boardroom War Room (CTO · CRO · CFO ParallelAgent & Roleplay)
  // ------------------------------------------------------------------------

  const warRoomState = {
    mode: "panel",
    persona: "CTO (Chief Technology Officer)",
  };

  function openWarRoomModal(preferredBankCode) {
    populateBankSelect(dom.warRoomBankSelect, preferredBankCode || "BRADESCO");
    syncWarRoomModeUI();
    dom.warRoomModalBackdrop.classList.remove("hidden");
  }

  function closeWarRoomModal() {
    dom.warRoomModalBackdrop.classList.add("hidden");
  }

  function syncWarRoomModeUI() {
    const isRoleplay = warRoomState.mode === "roleplay";
    dom.warRoomModeGrid.querySelectorAll(".warroom-mode-card").forEach((c) => {
      c.classList.toggle("selected", c.getAttribute("data-mode") === warRoomState.mode);
    });
    dom.warRoomPersonaBox.classList.toggle("hidden", !isRoleplay);
    dom.launchWarRoomBtnLabel.textContent = isRoleplay
      ? "Iniciar Roleplay Executivo 1:1"
      : "Gerar Dossiê War Room (CTO · CRO · CFO)";
  }

  function launchWarRoom() {
    const bankCode = dom.warRoomBankSelect.value || "BRADESCO";
    const bankLabel = bankLabelFromCode(bankCode);
    const topic = dom.warRoomTopicSelect.value || "estratégia geral nos 4 pilares do Banco Central";
    closeWarRoomModal();
    if (state.isStreaming) return;

    if (warRoomState.mode === "roleplay") {
      sendPrompt(
        `Inicie um roleplay executivo 1:1 assumindo o papel de ${warRoomState.persona} do ${bankLabel} com foco em ${topic}. Use os dados oficiais do Banco Central do ${bankLabel} para disparar a primeira objeção realista de sala de diretoria contra uma proposta Google Cloud e aguarde minha resposta para dar nota no Scorecard do Pitch.`
      );
    } else {
      sendPrompt(
        `Abra um Boardroom War Room de diretoria (CTO, CRO/Compliance e CFO) para o ${bankLabel} com foco em ${topic}. Simule as objeções mais duras desses três executivos ancoradas nos dados reais do Banco Central e entregue a matriz de contra-argumentos prontos, battlecard Google Cloud e roteiro Quick Win de 0–90 dias.`
      );
    }
  }

  // ------------------------------------------------------------------------
  // Bootstrap
  // ------------------------------------------------------------------------
  document.addEventListener("DOMContentLoaded", () => {
    bindEvents();
    updateSendButtonState();
    checkAuthAndBoot();
  });
})();

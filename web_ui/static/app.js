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
      if (e.key === "Escape" && !dom.adminModalBackdrop.classList.contains("hidden")) {
        closeAdminModal();
      }
    });
    dom.adminAddForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const val = dom.adminEntryInput.value.trim();
      if (val) addAllowlistEntry(val);
    });
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

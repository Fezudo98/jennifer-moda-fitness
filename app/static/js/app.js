// Utilitários compartilhados por todas as páginas do painel Jennifer Moda Fitness

const JF = {
    token() {
        return localStorage.getItem("jf_token");
    },

    async api(url, options = {}) {
        JF._iniciarCarregamento();
        try {
            const headers = options.headers || {};
            headers["x-access-token"] = JF.token() || "";
            if (!(options.body instanceof FormData)) {
                headers["Content-Type"] = "application/json";
            }
            const resp = await fetch(url, { ...options, headers });

            if (resp.status === 401) {
                localStorage.removeItem("jf_token");
                window.location.href = "/auth/login?expirada=1";
                return Promise.reject(new Error("Sessão expirada"));
            }

            let data = null;
            try {
                data = await resp.json();
            } catch (e) {
                data = null;
            }

            if (!resp.ok) {
                const msg = (data && data.erro) || "Ocorreu um erro. Tente novamente.";
                throw new Error(msg);
            }
            return data;
        } finally {
            JF._finalizarCarregamento();
        }
    },

    moeda(valor) {
        const n = Number(valor || 0);
        return "R$ " + n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },

    data(iso) {
        if (!iso) return "-";
        const d = new Date(iso);
        return d.toLocaleDateString("pt-BR") + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    },

    toast(mensagem, tipo = "sucesso") {
        const container = document.getElementById("jf-toasts") || JF._criarContainerToast();
        const cores = { sucesso: "var(--jf-verde)", erro: "var(--jf-vermelho)", aviso: "var(--jf-amarelo)" };
        const el = document.createElement("div");
        el.className = "toast-jf rounded-3 px-3 py-2 mb-2 shadow";
        el.style.borderLeft = `4px solid ${cores[tipo] || cores.sucesso}`;
        el.style.minWidth = "260px";
        el.textContent = mensagem;
        container.appendChild(el);
        setTimeout(() => {
            el.style.transition = "opacity .3s";
            el.style.opacity = "0";
            setTimeout(() => el.remove(), 300);
        }, 3500);
    },

    _criarContainerToast() {
        const div = document.createElement("div");
        div.id = "jf-toasts";
        div.setAttribute("aria-live", "polite");
        div.setAttribute("aria-atomic", "true");
        div.setAttribute("role", "status");
        div.style.position = "fixed";
        div.style.bottom = "1.25rem";
        div.style.right = "1.25rem";
        div.style.zIndex = "2000";
        document.body.appendChild(div);
        return div;
    },

    erro(e) {
        JF.toast(e.message || "Ocorreu um erro.", "erro");
    },

    // ------------------------------------------------------------------
    // Barra de carregamento global (indica requisições em andamento)
    // ------------------------------------------------------------------
    _requisicoesAtivas: 0,
    _timeoutMostrar: null,

    _barraCarregamento() {
        let barra = document.getElementById("jf-barra-carregamento");
        if (!barra) {
            barra = document.createElement("div");
            barra.id = "jf-barra-carregamento";
            document.body.appendChild(barra);
        }
        return barra;
    },

    _iniciarCarregamento() {
        JF._requisicoesAtivas++;
        if (JF._requisicoesAtivas === 1) {
            // Pequeno atraso para não piscar em requisições muito rápidas.
            JF._timeoutMostrar = setTimeout(() => {
                JF._barraCarregamento().classList.add("ativa");
            }, 150);
        }
    },

    _finalizarCarregamento() {
        JF._requisicoesAtivas = Math.max(0, JF._requisicoesAtivas - 1);
        if (JF._requisicoesAtivas === 0) {
            clearTimeout(JF._timeoutMostrar);
            JF._barraCarregamento().classList.remove("ativa");
        }
    },

    // ------------------------------------------------------------------
    // Confirmação no tema (substitui window.confirm)
    // ------------------------------------------------------------------
    confirmar(mensagem, opcoes = {}) {
        return new Promise((resolve) => {
            let modalEl = document.getElementById("jf-modal-confirmar");
            if (!modalEl) {
                modalEl = document.createElement("div");
                modalEl.id = "jf-modal-confirmar";
                modalEl.className = "modal fade";
                modalEl.tabIndex = -1;
                modalEl.setAttribute("aria-hidden", "true");
                modalEl.innerHTML = `
                    <div class="modal-dialog modal-dialog-centered">
                        <div class="modal-content">
                            <div class="modal-body text-center pt-4 pb-2">
                                <i class="bi bi-exclamation-circle text-rosa" style="font-size:2rem"></i>
                                <p class="mt-3 mb-0" id="jf-modal-confirmar-texto"></p>
                            </div>
                            <div class="modal-footer border-0 justify-content-center pb-4">
                                <button type="button" class="btn btn-jf-outline" id="jf-modal-confirmar-cancelar">Cancelar</button>
                                <button type="button" class="btn btn-jf" id="jf-modal-confirmar-ok">Confirmar</button>
                            </div>
                        </div>
                    </div>`;
                document.body.appendChild(modalEl);
            }

            modalEl.querySelector("#jf-modal-confirmar-texto").textContent = mensagem;
            const btnOk = modalEl.querySelector("#jf-modal-confirmar-ok");
            const btnCancelar = modalEl.querySelector("#jf-modal-confirmar-cancelar");
            btnOk.textContent = opcoes.textoConfirmar || "Confirmar";
            btnCancelar.textContent = opcoes.textoCancelar || "Cancelar";
            btnOk.classList.toggle("btn-jf", !opcoes.perigo);
            btnOk.classList.toggle("btn-danger", !!opcoes.perigo);

            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            let resolvido = false;
            const finalizar = (valor) => {
                if (resolvido) return;
                resolvido = true;
                resolve(valor);
                modal.hide();
            };

            btnOk.addEventListener("click", () => finalizar(true), { once: true });
            btnCancelar.addEventListener("click", () => finalizar(false), { once: true });
            modalEl.addEventListener("hidden.bs.modal", () => finalizar(false), { once: true });

            modal.show();
        });
    },

    // ------------------------------------------------------------------
    // Paginação reutilizável
    // ------------------------------------------------------------------
    renderizarPaginacao(container, paginaAtual, totalPaginas, aoMudarPagina) {
        if (!container) return;
        if (!totalPaginas || totalPaginas <= 1) {
            container.innerHTML = "";
            return;
        }
        const paginas = [];
        for (let p = 1; p <= totalPaginas; p++) {
            if (p === 1 || p === totalPaginas || Math.abs(p - paginaAtual) <= 1) {
                paginas.push(p);
            } else if (paginas[paginas.length - 1] !== "...") {
                paginas.push("...");
            }
        }
        container.innerHTML = `
            <li class="page-item ${paginaAtual <= 1 ? "disabled" : ""}">
                <a class="page-link" href="#" data-pagina="${paginaAtual - 1}">Anterior</a>
            </li>
            ${paginas.map(p => p === "..."
                ? `<li class="page-item disabled"><span class="page-link">…</span></li>`
                : `<li class="page-item ${p === paginaAtual ? "active" : ""}"><a class="page-link" href="#" data-pagina="${p}">${p}</a></li>`
            ).join("")}
            <li class="page-item ${paginaAtual >= totalPaginas ? "disabled" : ""}">
                <a class="page-link" href="#" data-pagina="${paginaAtual + 1}">Próxima</a>
            </li>
        `;
        container.querySelectorAll("a.page-link").forEach(link => {
            link.addEventListener("click", (e) => {
                e.preventDefault();
                const pagina = parseInt(e.target.dataset.pagina);
                if (!pagina || pagina < 1 || pagina > totalPaginas || pagina === paginaAtual) return;
                aoMudarPagina(pagina);
            });
        });
    },

    logout() {
        localStorage.removeItem("jf_token");
        window.location.href = "/auth/logout";
    },

    // ------------------------------------------------------------------
    // Tema (escuro / claro / rosa)
    // ------------------------------------------------------------------
    TEMA_PADRAO: "escuro",

    temaAtual() {
        return localStorage.getItem("jf_tema") || JF.TEMA_PADRAO;
    },

    aplicarTema(tema) {
        document.documentElement.setAttribute("data-theme", tema);
        document.querySelectorAll(".jf-tema-opcao").forEach((btn) => {
            const ativo = btn.dataset.tema === tema;
            btn.classList.toggle("ativo", ativo);
            btn.setAttribute("aria-pressed", String(ativo));
        });
    },

    definirTema(tema) {
        localStorage.setItem("jf_tema", tema);
        JF.aplicarTema(tema);
    },
};

document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.querySelector(".jf-sidebar-toggle");
    const sidebar = document.querySelector(".jf-sidebar");
    const overlay = document.querySelector(".jf-overlay");
    if (toggle && sidebar && overlay) {
        toggle.addEventListener("click", () => {
            sidebar.classList.toggle("aberta");
            overlay.classList.toggle("ativo");
        });
        overlay.addEventListener("click", () => {
            sidebar.classList.remove("aberta");
            overlay.classList.remove("ativo");
        });
    }

    JF.aplicarTema(JF.temaAtual());
    document.querySelectorAll(".jf-tema-opcao").forEach((btn) => {
        btn.addEventListener("click", () => JF.definirTema(btn.dataset.tema));
    });
});

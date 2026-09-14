/**
 * Editor de grafo integrado ao node-list — CNPD-OSINT
 * Insere botões ✏️/🗑️ nos itens do <div id="node-list"> e gerencia
 * adição/edição/remoção de nós e arestas, atualizando o Cytoscape.
 */
'use strict';

let editorAtivo = false;
let cyRef = null;        // referência ao Cytoscape, setada na init
let arestasData = [];
let nósData = [];
let cnpdId = 0;
let coresMap = {};
let tipoParaCorMap = {};

// ── Inicialização (chamada depois que o Cytoscape está pronto) ─────────────
function initGraphEditor(cy, nós, arestas, id, cores, tipoParaCor) {
  cyRef = cy;
  nósData = nós || [];
  arestasData = arestas || [];
  cnpdId = id || 0;
  coresMap = cores || {};
  tipoParaCorMap = tipoParaCor || {};
  // Adiciona os botões de edição em cada node-list-item
  injectEditorButtons();
}

// ── toggleEditor() — chamada pelo botão "✏️ Editar nó/aresta" ─────────────
function toggleEditor() {
  editorAtivo = !editorAtivo;
  const btn = document.getElementById('btn-editar-grafo');
  if (!btn) return;

  if (editorAtivo) {
    btn.textContent = '✖ Fechar editor';
    btn.style.background = '#ef4444';
    btn.style.color = '#fff';
    btn.style.borderColor = '#ef4444';
    // Garante que os botões de edição estão nos items
    injectEditorButtons();
  } else {
    btn.textContent = '✏️ Editar nó/aresta';
    btn.style.background = '';
    btn.style.color = '';
    btn.style.borderColor = '';
    removeEditorButtons();
  }
}

// ── Injetar botões ✏️ e 🗑️ em cada node-list-item ────────────────────────
function injectEditorButtons() {
  const items = document.querySelectorAll('.node-list-item');
  items.forEach(item => {
    if (item.classList.contains('editor-botões-injetados')) return;
    item.classList.add('editor-botões-injetados');

    // Remove comportamento de foco que pode conflitar
    const existingFocus = item.querySelector('.editor-foco-original');
    if (!existingFocus) {
      item.addEventListener('click', function (e) {
        // Só foca se o click não foi em um botão de edição
        if (e.target.closest('.editor-btn')) return;
        const id = this.dataset.nodeId;
        if (cyRef) {
          const nodeEl = cyRef.getElementById(id);
          if (nodeEl.length) {
            cyRef.animate({ center: { eles: nodeEl }, zoom: 1.5, duration: 300 });
          }
        }
        // Marca active
        document.querySelectorAll('.node-list-item').forEach(i => i.classList.remove('active'));
        this.classList.add('active');
      });
    }

    // Botão editar
    const btnEdit = document.createElement('button');
    btnEdit.className = 'editor-btn editor-btn-edit';
    btnEdit.textContent = '✏️';
    btnEdit.title = 'Editar nó';
    btnEdit.style.cssText = `
      margin-left: 0.25rem; padding: 0.1rem 0.25rem; font-size: 0.7rem;
      border: 1px solid var(--border); background: var(--surface-2); color: var(--text);
      border-radius: 0.2rem; cursor: pointer; line-height: 1;
    `;
    btnEdit.addEventListener('click', function (e) {
      e.stopPropagation();
      const id = parseInt(this.closest('.node-list-item').dataset.nodeId, 10);
      editarNó(id);
    });

    // Botão remover
    const btnDel = document.createElement('button');
    btnDel.className = 'editor-btn editor-btn-del';
    btnDel.textContent = '🗑️';
    btnDel.title = 'Remover nó';
    btnDel.style.cssText = `
      margin-left: 0.1rem; padding: 0.1rem 0.25rem; font-size: 0.7rem;
      border: 1px solid var(--danger); background: rgba(239,68,68,0.15); color: var(--danger);
      border-radius: 0.2rem; cursor: pointer; line-height: 1;
    `;
    btnDel.addEventListener('click', function (e) {
      e.stopPropagation();
      const id = parseInt(this.closest('.node-list-item').dataset.nodeId, 10);
      removerNó(id);
    });

    // Insere depois do texto do nó
    const smallEl = item.querySelector('small');
    if (smallEl) {
      smallEl.after(btnEdit, btnDel);
    } else {
      item.appendChild(btnEdit);
      item.appendChild(btnDel);
    }
  });
}

function removeEditorButtons() {
  document.querySelectorAll('.editor-btn').forEach(el => el.remove());
  document.querySelectorAll('.node-list-item').forEach(item => {
    item.classList.remove('editor-botões-injetados');
  });
}

// ── Modal: editar/adicionar nó ──────────────────────────────────────────────
function abrirModalNó(nó, isEdit) {
  // Cria ou reutiliza o modal
  let modal = document.getElementById('modal-novo-no');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'modal-novo-no';
    modal.style.cssText = `
      display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
      background: rgba(0,0,0,0.4); z-index: 100; align-items: center; justify-content: center;
    `;
    modal.innerHTML = `
      <div style="background:#141d33; padding: 1.5rem; border-radius: 0.5rem; width:90%; max-width:440px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.4); border:1px solid var(--border);">
        <h3 style="margin:0 0 1rem; font-size:1.1rem; color:var(--text);">${isEdit ? 'Editar nó' : 'Adicionar nó'}</h3>
        <form id="form-novo-no" style="display:flex; flex-direction:column; gap:0.75rem;">
          <input name="rótulo" placeholder="Rótulo (ex: Fulano de Tal)" required
            style="padding:0.4rem; border:1px solid var(--border); border-radius:0.25rem; font-size:0.9rem; background:#0c1427; color:var(--text);">
          <select name="tipo_nó"
            style="padding:0.4rem; border:1px solid var(--border); border-radius:0.25rem; font-size:0.9rem; background:#0c1427; color:var(--text);">
            <option value="PESSOA_DESAPARECIDA" style="color:var(--text);">Pessoa desaparecida</option>
            <option value="PESSOA_RELACIONADA" style="color:var(--text);">Pessoa relacionada</option>
            <option value="LOCAL" style="color:var(--text);">Local / Endereço</option>
            <option value="TELEFONE" style="color:var(--text);">Telefone</option>
            <option value="EMAIL" style="color:var(--text);">E-mail</option>
            <option value="DOCUMENTO" style="color:var(--text);">Documento</option>
            <option value="FATO" style="color:var(--text);">Fato / Evidência</option>
            <option value="OUTRO" style="color:var(--text);">Outro</option>
          </select>
          <input name="subtítulo" placeholder="Subtítulo (opcional)"
            style="padding:0.4rem; border:1px solid var(--border); border-radius:0.25rem; font-size:0.9rem; background:#0c1427; color:var(--text);">
          <input name="valor_principal" placeholder="Valor principal (opcional)"
            style="padding:0.4rem; border:1px solid var(--border); border-radius:0.25rem; font-size:0.9rem; background:#0c1427; color:var(--text);">
          <select name="nível_confianca"
            style="padding:0.4rem; border:1px solid var(--border); border-radius:0.25rem; font-size:0.9rem; background:#0c1427; color:var(--text);">
            <option value="INVESTIGADOR">INVESTIGADOR (manual)</option>
            <option value="IA_SUGERIDO">IA_SUGERIDO</option>
            <option value="MÉDIA">MÉDIA</option>
            <option value="ALTA">ALTA</option>
          </select>
          <div style="display:flex; gap:0.5rem; justify-content:flex-end;">
            <button type="button" id="btn-fechar-modal-novo-no"
              style="padding:0.4rem 0.8rem; border:1px solid var(--border); background:#1a2743; color:var(--text);
              cursor:pointer; border-radius:0.25rem;">Cancelar</button>
            <button type="submit"
              style="padding:0.4rem 0.8rem; background:var(--primary-strong); color:#fff; border:none;
              cursor:pointer; border-radius:0.25rem;">Salvar</button>
          </div>
        </form>
      </div>
    `;
    document.body.appendChild(modal);

    // Botão fechar
    const btnFechar = modal.querySelector('#btn-fechar-modal-novo-no');
    btnFechar.onclick = () => { modal.style.display = 'none'; };
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.style.display = 'none';
    });

    // Submit do form
    modal.querySelector('#form-novo-no').addEventListener('submit', async (e) => {
      e.preventDefault();
      const form = modal.querySelector('#form-novo-no');
      const dados = {
        rótulo: form.querySelector('[name="rótulo"]').value,
        tipo_nó: form.querySelector('[name="tipo_nó"]').value,
        subtítulo: form.querySelector('[name="subtítulo"]').value,
        valor_principal: form.querySelector('[name="valor_principal"]').value,
        nível_confianca: form.querySelector('[name="nível_confianca"]').value,
      };
      if (isEdit && nó) {
        await atualizarNóManual(nó.id, dados);
      } else {
        await adicionarNóManual(dados);
      }
      modal.style.display = 'none';
    });
  }

  // Preenche o formulário
  const form = modal.querySelector('#form-novo-no');
  if (form) {
    if (nó) {
      form.querySelector('[name="rótulo"]').value = nó.rótulo || '';
      form.querySelector('[name="tipo_nó"]').value = nó.tipo_nó || 'OUTRO';
      form.querySelector('[name="subtítulo"]').value = nó.subtítulo || '';
      form.querySelector('[name="valor_principal"]').value = nó.valor_principal || '';
      form.querySelector('[name="nível_confianca"]').value = nó.nível_confianca || 'INVESTIGADOR';
      modal.querySelector('h3').textContent = 'Editar nó';
      modal.querySelector('#form-novo-no').dataset.isEdit = 'true';
      modal.querySelector('#form-novo-no').dataset.editId = nó.id;
    } else {
      form.querySelector('[name="rótulo"]').value = '';
      form.querySelector('[name="tipo_nó"]').value = 'PESSOA_RELACIONADA';
      form.querySelector('[name="subtítulo"]').value = '';
      form.querySelector('[name="valor_principal"]').value = '';
      form.querySelector('[name="nível_confianca"]').value = 'INVESTIGADOR';
      modal.querySelector('h3').textContent = 'Adicionar nó';
      modal.querySelector('#form-novo-no').dataset.isEdit = 'false';
      modal.querySelector('#form-novo-no').dataset.editId = '';
    }
  }

  modal.style.display = 'flex';
}

function fecharModalNó() {
  const modal = document.getElementById('modal-novo-no');
  if (modal) modal.style.display = 'none';
}

// ── Modal: editar/adicionar aresta ──────────────────────────────────────────
function abrirModalAresta(aresta, isEdit) {
  let modal = document.getElementById('modal-nova-aresta');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'modal-nova-aresta';
    modal.style.cssText = `
      display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
      background: rgba(0,0,0,0.4); z-index: 100; align-items: center; justify-content: center;
    `;
    modal.innerHTML = `
      <div style="background:#141d33; padding:1.5rem; border-radius:0.5rem; width:90%; max-width:460px;
        box-shadow:0 8px 24px rgba(0,0,0,0.4); border:1px solid var(--border);">
        <h3 style="margin:0 0 1rem; font-size:1.1rem; color:var(--text);">${isEdit ? 'Editar aresta' : 'Adicionar aresta'}</h3>
        <form id="form-nova-aresta" style="display:flex; flex-direction:column; gap:0.75rem;">
          <select name="origem_id" required
            style="padding:0.4rem; border:1px solid var(--border); border-radius:0.25rem; font-size:0.9rem; background:#0c1427; color:var(--text);">
            <option value="">Selecione origem...</option>
          </select>
          <select name="destino_id" required
            style="padding:0.4rem; border:1px solid var(--border); border-radius:0.25rem; font-size:0.9rem; background:#0c1427; color:var(--text);">
            <option value="">Selecione destino...</option>
          </select>
          <select name="tipo_relação"
            style="padding:0.4rem; border:1px solid var(--border); border-radius:0.25rem; font-size:0.9rem; background:#0c1427; color:var(--text);">
            <option value="CONHECE" style="color:var(--text);">Conhece</option>
            <option value="TRABALHA_COM" style="color:var(--text);">Trabalha com</option>
            <option value="MORADA_EM" style="color:var(--text);">Mora em / está em</option>
            <option value="FALOU_COM" style="color:var(--text);">Falou com</option>
            <option value="RESIDENCIA_EM" style="color:var(--text);">Residência em</option>
            <option value="PARCEIRO" style="color:var(--text);">Parceiro</option>
            <option value="DESCONHECIDO" style="color:var(--text);">Desconhecido</option>
            <option value="OUTRO" style="color:var(--text);">Outro</option>
          </select>
          <input name="rótulo_aresta" placeholder="Label (ex: 'conhece desde 2020')"
            style="padding:0.4rem; border:1px solid var(--border); border-radius:0.25rem; font-size:0.9rem; background:#0c1427; color:var(--text);">
          <select name="nível_confianca"
            style="padding:0.4rem; border:1px solid var(--border); border-radius:0.25rem; font-size:0.9rem; background:#0c1427; color:var(--text);">
            <option value="INVESTIGADOR">INVESTIGADOR (manual)</option>
            <option value="IA_SUGERIDO">IA_SUGERIDO</option>
            <option value="MÉDIA">MÉDIA</option>
            <option value="ALTA">ALTA</option>
          </select>
          <div style="display:flex; gap:0.5rem; justify-content:flex-end;">
            <button type="button" id="btn-fechar-modal-nova-aresta"
              style="padding:0.4rem 0.8rem; border:1px solid var(--border); background:#1a2743; color:var(--text);
              cursor:pointer; border-radius:0.25rem;">Cancelar</button>
            <button type="submit"
              style="padding:0.4rem 0.8rem; background:var(--primary-strong); color:#fff; border:none;
              cursor:pointer; border-radius:0.25rem;">Salvar</button>
          </div>
        </form>
      </div>
    `;
    document.body.appendChild(modal);

    const btnFechar = modal.querySelector('#btn-fechar-modal-nova-aresta');
    btnFechar.onclick = () => { modal.style.display = 'none'; };
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.style.display = 'none';
    });

    modal.querySelector('#form-nova-aresta').addEventListener('submit', async (e) => {
      e.preventDefault();
      const form = modal.querySelector('#form-nova-aresta');
      const dados = {
        origem_id: parseInt(form.querySelector('[name="origem_id"]').value, 10),
        destino_id: parseInt(form.querySelector('[name="destino_id"]').value, 10),
        tipo_relação: form.querySelector('[name="tipo_relação"]').value,
        rótulo_aresta: form.querySelector('[name="rótulo_aresta"]').value,
        nível_confianca: form.querySelector('[name="nível_confianca"]').value,
      };
      if (isEdit && aresta) {
        await atualizarArestaManual(aresta.id, dados);
      } else {
        await adicionarArestaManual(dados.origem_id, dados.destino_id, {
          tipo_relação: dados.tipo_relação,
          rótulo_aresta: dados.rótulo_aresta,
          nível_confianca: dados.nível_confianca,
        });
      }
      modal.style.display = 'none';
    });
  }

  // Preenche
  const form = modal.querySelector('#form-nova-aresta');
  if (form) {
    // Popular selects de origem/destino com os nós atuais
    const origemSelect = form.querySelector('[name="origem_id"]');
    const destinoSelect = form.querySelector('[name="destino_id"]');
    // Limpa e repopula (garante que os dados são atualizados)
    origemSelect.innerHTML = '<option value="">Selecione origem...</option>';
    destinoSelect.innerHTML = '<option value="">Selecione destino...</option>';
    const nós = Array.from(window.nósData || []);
    nós.forEach(nó => {
      const opt1 = document.createElement('option');
      opt1.value = nó.id;
      opt1.textContent = nó.rótulo || '(sem rótulo)';
      origemSelect.appendChild(opt1);

      const opt2 = document.createElement('option');
      opt2.value = nó.id;
      opt2.textContent = nó.rótulo || '(sem rótulo)';
      destinoSelect.appendChild(opt2);
    });

    if (aresta) {
      for (const opt of origemSelect.options) {
        if (String(opt.value) === String(aresta.nó_origem)) opt.selected = true;
      }
      for (const opt of destinoSelect.options) {
        if (String(opt.value) === String(aresta.nó_destino)) opt.selected = true;
      }
      form.querySelector('[name="tipo_relação"]').value = aresta.tipo_relação || 'OUTRO';
      form.querySelector('[name="rótulo_aresta"]').value = aresta.rótulo_aresta || '';
      form.querySelector('[name="nível_confianca"]').value = aresta.nível_confianca || 'INVESTIGADOR';
      modal.querySelector('h3').textContent = 'Editar aresta';
    } else {
      form.querySelector('[name="tipo_relação"]').value = 'OUTRO';
      form.querySelector('[name="rótulo_aresta"]').value = '';
      form.querySelector('[name="nível_confianca"]').value = 'INVESTIGADOR';
      modal.querySelector('h3').textContent = 'Adicionar aresta';
    }
  }

  modal.style.display = 'flex';
}

function fecharModalAresta() {
  const modal = document.getElementById('modal-nova-aresta');
  if (modal) modal.style.display = 'none';
}

// ── Ações CRUD via API ───────────────────────────────────────────────────────
async function adicionarNóManual(dados) {
  const csrfToken = getCSRFToken();
  const formData = new FormData();
  formData.append('tipo_nó', dados.tipo_nó || 'OUTRO');
  formData.append('grupo_nó', 'investigador');
  formData.append('rótulo', dados.rótulo);
  formData.append('subtítulo', dados.subtítulo || '');
  formData.append('valor_principal', dados.valor_principal || '');
  formData.append('nível_confianca', dados.nível_confianca || 'INVESTIGADOR');

  try {
    const resp = await fetch(`/grafos/casos/${cnpdId}/api/nós`, { method: 'POST', body: formData, headers: { 'X-CSRF-Token': csrfToken } });
    if (!resp.ok) throw new Error(`Erro ${resp.status}: ${await resp.text()}`);
    const grafo = await resp.json();
    window.nósData = grafo.nós || [];
    window.arestasData = grafo.arestas || [];
    arestasData = grafo.arestas || [];
    nósData = grafo.nós || [];
    toast(`Nó "${dados.rótulo}" adicionado.`);
    // Re-render node-list (Jinja2 não re-renderiza, então atualizamos manualmente)
    atualizarNodeList();
    atualizarCytoscape();
  } catch (err) {
    toast(`Erro ao adicionar nó: ${err.message}`, 'error');
  }
}

async function atualizarNóManual(no_id, dados) {
  const csrfToken = getCSRFToken();
  const formData = new FormData();
  if (dados.tipo_nó) formData.append('tipo_nó', dados.tipo_nó);
  if (dados.rótulo !== undefined) formData.append('rótulo', dados.rótulo);
  if (dados.subtítulo !== undefined) formData.append('subtítulo', dados.subtítulo);
  if (dados.valor_principal !== undefined) formData.append('valor_principal', dados.valor_principal);
  if (dados.nível_confianca) formData.append('nível_confianca', dados.nível_confianca);

  try {
    const resp = await fetch(`/grafos/casos/${cnpdId}/api/nós/${no_id}/atualizar`, { method: 'POST', body: formData, headers: { 'X-CSRF-Token': csrfToken } });
    if (!resp.ok) throw new Error(`Erro ${resp.status}: ${await resp.text()}`);
    const grafo = await resp.json();
    window.nósData = grafo.nós || [];
    window.arestasData = grafo.arestas || [];
    arestasData = grafo.arestas || [];
    nósData = grafo.nós || [];
    toast('Nó atualizado.');
    atualizarNodeList();
    atualizarCytoscape();
  } catch (err) {
    toast(`Erro ao atualizar nó: ${err.message}`, 'error');
  }
}

async function adicionarArestaManual(origem_id, destino_id, dados) {
  const csrfToken = getCSRFToken();
  const formData = new FormData();
  formData.append('origem_id', origem_id);
  formData.append('destino_id', destino_id);
  formData.append('tipo_relação', dados.tipo_relação || 'OUTRO');
  formData.append('rótulo_aresta', dados.rótulo_aresta || '');
  formData.append('nível_confianca', dados.nível_confianca || 'INVESTIGADOR');

  try {
    const resp = await fetch(`/grafos/casos/${cnpdId}/api/arestas`, { method: 'POST', body: formData, headers: { 'X-CSRF-Token': csrfToken } });
    if (!resp.ok) throw new Error(`Erro ${resp.status}: ${await resp.text()}`);
    const grafo = await resp.json();
    window.nósData = grafo.nós || [];
    window.arestasData = grafo.arestas || [];
    arestasData = grafo.arestas || [];
    nósData = grafo.nós || [];
    toast('Aresta adicionada.');
    atualizarNodeList();
    atualizarCytoscape();
  } catch (err) {
    toast(`Erro ao adicionar aresta: ${err.message}`, 'error');
  }
}

async function atualizarArestaManual(a_id, dados) {
  const csrfToken = getCSRFToken();
  const formData = new FormData();
  if (dados.tipo_relação) formData.append('tipo_relação', dados.tipo_relação);
  if (dados.rótulo_aresta !== undefined) formData.append('rótulo_aresta', dados.rótulo_aresta);
  if (dados.nível_confianca) formData.append('nível_confianca', dados.nível_confianca);

  try {
    const resp = await fetch(`/grafos/casos/${cnpdId}/api/arestas/${a_id}/atualizar`, { method: 'POST', body: formData, headers: { 'X-CSRF-Token': csrfToken } });
    if (!resp.ok) throw new Error(`Erro ${resp.status}: ${await resp.text()}`);
    const grafo = await resp.json();
    window.nósData = grafo.nós || [];
    window.arestasData = grafo.arestas || [];
    arestasData = grafo.arestas || [];
    nósData = grafo.nós || [];
    toast('Aresta atualizada.');
    atualizarNodeList();
    atualizarCytoscape();
  } catch (err) {
    toast(`Erro ao atualizar aresta: ${err.message}`, 'error');
  }
}

async function removerNó(no_id) {
  if (!confirm('Remover este nó e todas as arestas conectadas a ele?')) return;
  const csrfToken = getCSRFToken();
  try {
    const resp = await fetch(`/grafos/casos/${cnpdId}/api/nós/${no_id}/remover`, { method: 'POST', headers: { 'X-CSRF-Token': csrfToken } });
    if (!resp.ok) throw new Error(`Erro ${resp.status}: ${await resp.text()}`);
    const grafo = await resp.json();
    window.nósData = grafo.nós || [];
    window.arestasData = grafo.arestas || [];
    arestasData = grafo.arestas || [];
    nósData = grafo.nós || [];
    toast('Nó removido.');
    atualizarNodeList();
    atualizarCytoscape();
  } catch (err) {
    toast(`Erro ao remover nó: ${err.message}`, 'error');
  }
}

async function removerAresta(a_id) {
  if (!confirm('Remover esta aresta?')) return;
  const csrfToken = getCSRFToken();
  try {
    const resp = await fetch(`/grafos/casos/${cnpdId}/api/arestas/${a_id}/remover`, { method: 'POST', headers: { 'X-CSRF-Token': csrfToken } });
    if (!resp.ok) throw new Error(`Erro ${resp.status}: ${await resp.text()}`);
    const grafo = await resp.json();
    window.nósData = grafo.nós || [];
    window.arestasData = grafo.arestas || [];
    arestasData = grafo.arestas || [];
    nósData = grafo.nós || [];
    toast('Aresta removida.');
    atualizarNodeList();
    atualizarCytoscape();
  } catch (err) {
    toast(`Erro ao remover aresta: ${err.message}`, 'error');
  }
}

async function sincronizarArestas() {
  if (!confirm('Reconstruir todas as arestas automaticamente? Isto removerá as arestas atuais e criará novas baseadas nos nós existentes.')) return;
  const csrfToken = getCSRFToken();
  try {
    const resp = await fetch(`/grafos/casos/${cnpdId}/api/grafo/sincronizar`, { method: 'POST', headers: { 'X-CSRF-Token': csrfToken } });
    if (!resp.ok) throw new Error(`Erro ${resp.status}: ${await resp.text()}`);
    const grafo = await resp.json();
    window.nósData = grafo.nós || [];
    window.arestasData = grafo.arestas || [];
    arestasData = grafo.arestas || [];
    nósData = grafo.nós || [];
    toast(grafo.mensagem || 'Arestas sincronizadas.');
    atualizarNodeList();
    atualizarCytoscape();
  } catch (err) {
    toast(`Erro ao sincronizar: ${err.message}`, 'error');
  }
}

// ── Editar nó (abre modal pré-preenchido) ───────────────────────────────────
function editarNó(no_id) {
  const nó = Array.from(window.nósData || []).find(n => String(n.id) === String(no_id));
  if (!nó) return;
  abrirModalNó(nó, true);
}

// ── Editar aresta (abre modal pré-preenchido) ───────────────────────────────
function editarAresta(a_id) {
  const aresta = Array.from(window.arestasData || []).find(a => String(a.id) === String(a_id));
  if (!aresta) return;
  abrirModalAresta(aresta, true);
}

// ── Re-renderizar o node-list com os dados atualizados ──────────────────────
function atualizarNodeList() {
  const container = document.getElementById('node-list');
  if (!container) return;

  // Remove itens existentes (mantém o heading)
  const heading = container.previousElementSibling;
  container.innerHTML = '';

  const nós = Array.from(window.nósData || []);
  if (nós.length === 0) {
    container.innerHTML = '<p class="empty">Nenhum nó no grafo. Clique em "Regenerar com IA".</p>';
    return;
  }

  const corMap = {
    'central': '#10b981',
    'fonte_oficial': '#3b82f6',
    'evidência': '#f59e0b',
    'pessoa': '#8b5cf6',
    'rede_social': '#ec4899',
    'localização': '#14b8a6',
    'documento': '#6b7280',
    'investigador': '#f97316',
  };

  nós.forEach(nó => {
    const cor = corMap[nó.grupo_nó] || '#6b7280';
    const item = document.createElement('div');
    item.className = 'node-list-item';
    item.dataset.nodeId = nó.id;
    item.style.borderLeftColor = cor;

    item.innerHTML = `
      <span class="dot" style="background:${cor};"></span>
      <div>
        <strong>${escapeHTML(nó.rótulo || '(sem rótulo)')}</strong>
        <small style="color: var(--muted); display:block;">
          ${nó.tipo_nó || 'OUTRO'} · ${nó.subtítulo || nó.valor_principal || ''}
        </small>
      </div>
    `;

    container.appendChild(item);
  });

  // Reaplica os botões de edição se o editor estiver ativo
  if (editorAtivo) {
    injectEditorButtons();
  }

  // Reaplica o listener de clique para focar
  document.querySelectorAll('.node-list-item').forEach(item => {
    item.addEventListener('click', function () {
      const id = this.dataset.nodeId;
      if (cyRef) {
        const nodeEl = cyRef.getElementById(id);
        if (nodeEl.length) {
          cyRef.animate({ center: { eles: nodeEl }, zoom: 1.5, duration: 300 });
        }
      }
      document.querySelectorAll('.node-list-item').forEach(i => i.classList.remove('active'));
      this.classList.add('active');
    });
  });
}

// ── Atualizar Cytoscape ──────────────────────────────────────────────────────
function atualizarCytoscape() {
  if (!cyRef) return;

  // Remove tudo
  cyRef.elements().remove();

  // Adiciona nós
  const novosNós = Array.from(window.nósData || []).map(nó => ({
    data: {
      id: String(nó.id),
      label: nó.rótulo || '',
      subtitle: nó.subtítulo || '',
      principal: nó.valor_principal || '',
      grupo: nó.grupo_nó || 'investigador',
      tipo: nó.tipo_nó || 'OUTRO',
      cor: coresMap[nó.grupo_nó] || tipoParaCorMap[nó.tipo_nó] || '#6b7280',
      confiança: nó.nível_confianca || 'IA_SUGERIDO',
    },
  }));

  // Adiciona arestas
  const novasArestas = Array.from(window.arestasData || []).map(a => ({
    data: {
      id: 'e' + a.id,
      source: String(a.nó_origem),
      target: String(a.nó_destino),
      label: a.rótulo_aresta || a.tipo_relação || '',
      tipo: a.tipo_relação || 'OUTRO',
      confiança: a.nível_confianca || 'IA_SUGERIDO',
    },
  }));

  cyRef.add({ nodes: novosNós, edges: novasArestas });

  // Reaplica classes de confiança
  cyRef.edges().forEach(edgeEl => {
    const conf = edgeEl.data('confiança');
    if (conf === 'ALTA') edgeEl.addClass('confiança-alta');
    else if (conf === 'MÉDIA') edgeEl.addClass('confiança-média');
    else if (conf === 'BAIXA') edgeEl.addClass('confiança-baixa');
  });

  cyRef.nodes().forEach(nodeEl => {
    if (nodeEl.data('grupo') === 'central') nodeEl.addClass('grupo-central');
  });

  // Re-layout
  cyRef.layout({
    name: 'breadthfirst',
    directed: true,
    padding: 30,
    spacingFactor: 1.2,
    animate: true,
    animationDuration: 400,
  }).run();
}

// ── Toast ────────────────────────────────────────────────────────────────────
function toast(msg, type) {
  let el = document.getElementById('toast-mensagem');
  if (!el) {
    el = document.createElement('div');
    el.id = 'toast-mensagem';
    el.style.cssText = `
      position:fixed; bottom:1.5rem; right:1.5rem; background:#1e293b; color:#fff;
      padding:0.75rem 1rem; border-radius:0.4rem; max-width:360px; z-index:200;
      font-size:0.9rem; box-shadow:0 4px 12px rgba(0,0,0,0.2);
    `;
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.style.background = type === 'error' ? '#ef4444' : '#1e293b';
  el.style.display = 'block';
  setTimeout(() => { el.style.display = 'none'; }, 3000);
}

// ── CSRF token ───────────────────────────────────────────────────────────────
function getCSRFToken() {
  const match = document.cookie.match(/csrf_token=([^;]+)/);
  if (match) return match[1];
  const input = document.querySelector('input[name="csrf_token"]');
  return input ? input.value : '';
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function escapeHTML(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

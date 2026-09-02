/**
 * BNET IT Doc System - Vanilla JS App
 */

const API_BASE = "/api";
let currentCategories = [];
let currentCategoryId = null;

// App Core Object
const app = {
    state: {
        token: localStorage.getItem('bnet_token'),
        username: localStorage.getItem('bnet_user'),
        currentItems: [],
        catSearch: '',
        catSort: { key: 'display_order', dir: 'asc' },
        itemSearch: '',
        itemSort: { key: 'id', dir: 'asc' }
    },
    
    init() {
        this.bindEvents();
        this.checkStatus(); // Fetch status for login screen LDAP mode
        if (this.state.token) {
            this.scheduleSessionTimer();
            this.ui.showDashboard();
            this.loadCategories();
            this.loadDashboardStats();
        }
    },
    
    bindEvents() {
        document.getElementById('login-form').addEventListener('submit', this.handleLogin.bind(this));
        document.getElementById('btn-logout').addEventListener('click', this.handleLogout.bind(this));
        
        // Navigation
        document.querySelectorAll('.nav-item').forEach(el => {
            el.addEventListener('click', (e) => {
                const view = e.currentTarget.dataset.view;
                if(view) {
                    this.ui.switchSubView(view);
                    this.ui.setActiveNav(e.currentTarget);
                }
            });
        });

        // Category Form
        document.getElementById('btn-add-attr-row').addEventListener('click', this.ui.appendAttributeRow);
        document.getElementById('form-create-category').addEventListener('submit', this.handleCreateCategory.bind(this));
        document.getElementById('form-edit-category').addEventListener('submit', this.handleEditCategory.bind(this));
        document.getElementById('btn-add-edit-attr-row').addEventListener('click', this.ui.appendEditAttributeRow);
        
        // Entity Form
        document.getElementById('btn-new-entity').addEventListener('click', () => {
            document.getElementById('edit-entity-id').value = '';
            this.ui.buildEntityForm();
            this.ui.showModal('modal-entity-form');
        });
        document.getElementById('form-entity').addEventListener('submit', this.handleCreateEntity.bind(this));
        document.getElementById('form-report').addEventListener('submit', this.generateReport.bind(this));
    },
    
    // API Wrapper
    async api(endpoint, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        };
        
        if (this.state.token) {
            headers['Authorization'] = `Bearer ${this.state.token}`;
            headers['X-API-Token'] = this.state.token;
        }
        
        try {
            const res = await fetch(`${API_BASE}${endpoint}`, {
                ...options,
                headers
            });
            
            if (res.status === 401) {
                this.handleLogout();
                throw new Error("Sessão expirada. Faça login novamente.");
            }
            
            if (res.status === 204) return null;
            
            const data = await res.json();
            if (!res.ok) {
                const err = Array.isArray(data.detail) ? data.detail[0].msg : data.detail;
                throw new Error(err || "Erro na solicitação");
            }
            return data;
        } catch (err) {
            this.ui.toast(err.message, 'error');
            throw err;
        }
    },
    
    // Handlers
    async handleLogin(e) {
        e.preventDefault();
        const btn = document.getElementById('btn-login');
        btn.innerHTML = "<i class='bx bx-loader-alt bx-spin'></i> Entrando...";
        btn.disabled = true;
        
        const username = e.target.username.value;
        const password = e.target.password.value;
        
        try {
            const data = await this.api('/auth/login-json', {
                method: 'POST',
                body: JSON.stringify({ username, password })
            });
            
            this.state.token = data.access_token;
            this.state.username = username;
            localStorage.setItem('bnet_token', data.access_token);
            localStorage.setItem('bnet_user', username);
            
            this.ui.toast('Login realizado com sucesso', 'success');
            this.scheduleSessionTimer();
            this.ui.showDashboard();
            this.loadCategories();
            this.checkStatus();
            this.loadDashboardStats();
        } catch (err) {
            // Error handled by api()
        } finally {
            btn.innerHTML = "<span>Entrar no Sistema</span>";
            btn.disabled = false;
        }
    },
    
    handleLogout() {
        this.state.token = null;
        this.state.username = null;
        localStorage.removeItem('bnet_token');
        localStorage.removeItem('bnet_user');
        
        if (this.sessionTimer) clearTimeout(this.sessionTimer);
        if (this.warningTimer) clearTimeout(this.warningTimer);
        
        document.getElementById('app-view').classList.add('hidden');
        document.getElementById('login-view').classList.remove('hidden');
    },

    scheduleSessionTimer() {
        if (!this.state.token) return;
        try {
            // Decodifica a carga útil do JWT (Header.Payload.Signature)
            const base64Url = this.state.token.split('.')[1];
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            const payload = JSON.parse(decodeURIComponent(atob(base64).split('').map(function(c) {
                return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
            }).join('')));
            
            if (payload.exp) {
                const timeRemaining = (payload.exp * 1000) - Date.now();
                if (this.sessionTimer) clearTimeout(this.sessionTimer);
                if (this.warningTimer) clearTimeout(this.warningTimer);
                
                if (timeRemaining > 0) {
                    this.sessionTimer = setTimeout(() => {
                        this.ui.hideModal('modal-renew-session');
                        this.ui.toast("Sessão expirada por inatividade. Faça login novamente.", "warning");
                        this.handleLogout();
                    }, timeRemaining);
                    
                    if (timeRemaining > 60000) {
                        this.warningTimer = setTimeout(() => {
                            this.ui.showModal('modal-renew-session');
                        }, timeRemaining - 60000);
                    } else {
                        this.ui.showModal('modal-renew-session');
                    }
                } else {
                    this.handleLogout();
                }
            }
        } catch (e) {
            console.warn("Could not schedule session timer", e);
        }
    },

    async renewSession() {
        try {
            const data = await this.api('/auth/refresh', {
                method: 'POST'
            });
            this.state.token = data.access_token;
            localStorage.setItem('bnet_token', data.access_token);
            this.scheduleSessionTimer();
            this.ui.hideModal('modal-renew-session');
            this.ui.toast("Sessão renovada com sucesso.", "success");
        } catch (err) {
            this.ui.toast("Erro ao renovar sessão. Por favor faça login novamente.", "error");
            this.handleLogout();
        }
    },

    async checkStatus() {
        try {
            const { database, ldap_mode } = await this.api('/status');
            document.getElementById('api-status-badge').innerText = `Banco: ${database} | LDAP: ${ldap_mode}`;
            
            // Handle LDAP mock visibility on login screen
            const ldapSubtitle = document.getElementById('ldap-subtitle');
            const ldapMockHint = document.getElementById('ldap-mock-hint');
            if (ldapSubtitle && ldapMockHint) {
                if (ldap_mode !== 'mock') {
                    ldapSubtitle.innerText = 'Autenticação';
                    ldapMockHint.style.display = 'none';
                } else {
                    ldapSubtitle.innerText = 'Autenticação (LDAP Mock)';
                    ldapMockHint.style.display = 'block';
                }
            }
        } catch (e) {
            document.getElementById('api-status-badge').innerText = 'Backend Offline';
        }
        this.checkMasterPasswordStatus();
    },

    async checkMasterPasswordStatus() {
        if (!this.state.token) return;
        try {
            const res = await this.api('/config/master-password/status');
            const navMasterPassword = document.getElementById('nav-master-password');
            if (navMasterPassword) {
                if (res.can_manage) {
                    navMasterPassword.style.display = 'block';
                } else {
                    navMasterPassword.style.display = 'none';
                }
            }
            if (!res.is_setup && res.can_manage) {
                this.ui.showModal('modal-setup-master-password');
            }
        } catch (e) {
            console.error("Failed to check master password status");
        }
    },

    async loadDashboardStats() {
        try {
            const stats = await this.api('/dashboard/stats');
            const catList = document.getElementById('dashboard-category-counts');
            const recentList = document.getElementById('dashboard-recent-items');
            
            catList.innerHTML = '';
            if (stats.category_counts.length === 0) {
                catList.innerHTML = '<li>Nenhuma categoria.</li>';
            } else {
                stats.category_counts.forEach(c => {
                    catList.insertAdjacentHTML('beforeend', `<li style="padding: 0.5rem 0; border-bottom: 1px solid rgba(0,0,0,0.1); display: flex; justify-content: space-between;"><span>${app.ui.escapeHtml(c.name)}</span> <strong>${c.count}</strong></li>`);
                });
            }
            
            recentList.innerHTML = '';
            if (stats.recent_items.length === 0) {
                recentList.innerHTML = '<tr><td colspan="3" class="text-center">Nenhum item recente.</td></tr>';
            } else {
                stats.recent_items.forEach(i => {
                    const dateStr = new Date(i.updated_at).toLocaleString('pt-BR');
                    recentList.insertAdjacentHTML('beforeend', `<tr><td>#${i.id}</td><td>${app.ui.escapeHtml(i.category_name)}</td><td>${dateStr}</td></tr>`);
                });
            }
        } catch(e) {}
    },

    async loadModificationLogs() {
        const tbody = document.getElementById('table-mod-logs-body');
        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">Carregando...</td></tr>';
        try {
            const logs = await this.api('/dashboard/logs');
            tbody.innerHTML = '';
            if (logs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center">Nenhum log encontrado.</td></tr>';
            } else {
                logs.forEach(log => {
                    const dateStr = new Date(log.created_at).toLocaleString('pt-BR');
                    tbody.insertAdjacentHTML('beforeend', `
                        <tr>
                            <td>${dateStr}</td>
                            <td>${app.ui.escapeHtml(log.username || '-')}</td>
                            <td><span class="badge ${log.action === 'CREATE' ? 'badge-success' : log.action === 'UPDATE' ? 'badge-primary' : 'badge-danger'}" style="background: var(--${log.action === 'DELETE' ? 'danger' : 'primary'}); color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;">${log.action}</span></td>
                            <td>${app.ui.escapeHtml(log.category_name || '-')}</td>
                            <td>#${log.entity_id || '-'}</td>
                        </tr>
                    `);
                });
            }
        } catch(e) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center">Erro ao carregar logs.</td></tr>';
        }
    },

    async loadCategories() {
        const data = await this.api('/categories/');
        currentCategories = data;
        
        document.getElementById('stat-categories').innerText = data.length;
        this.ui.renderCategories();
        
        // Populate Sidebar Nav
        
        const reportSel = document.getElementById('report-category-select');
        reportSel.innerHTML = '<option value="ALL">Todas as Categorias</option>';
        data.forEach(cat => reportSel.insertAdjacentHTML('beforeend', `<option value="${cat.id}">${cat.name}</option>`));
        const nav = document.getElementById('dynamic-categories-nav');
        nav.innerHTML = '';
        data.forEach(cat => {
            const a = document.createElement('a');
            a.href = '#';
            a.className = 'nav-item';
            a.innerHTML = `<i class='bx bx-folder'></i> ${app.ui.escapeHtml(cat.name)}`;
            a.onclick = (e) => {
                e.preventDefault();
                app.ui.setActiveNav(a);
                app.loadCategoryItems(cat);
            };
            nav.appendChild(a);
        });
    },

    
    async openEditCategory(id) {
        const cat = currentCategories.find(c => c.id === id);
        if(!cat) return;
        
        document.getElementById('edit-category-id').value = cat.id;
        document.getElementById('edit-category-name').value = cat.name;
        
        const list = document.getElementById('edit-attributes-list');
        list.innerHTML = '';
        
        cat.attributes.forEach(attr => {
            const html = `
                <div class="flex-between mb-2 attr-row-existing" style="gap: 0.5rem; background: rgba(0,0,0,0.1); padding: 0.5rem; border-radius: 4px;" data-id="${attr.id}">
                    <input type="text" class="attr-edit-name-existing" data-original-name="${app.ui.escapeHtml(attr.name)}" value="${app.ui.escapeHtml(attr.name)}" style="flex:2" required>
                    <span style="flex:1; padding-left:0.5rem; display:flex; align-items:center;">${attr.type}</span>
                    <select class="attr-edit-req-existing" data-original-req="${attr.is_required}" style="flex:1">
                        <option value="false" ${!attr.is_required ? 'selected' : ''}>Opcional</option>
                        <option value="true" ${attr.is_required ? 'selected' : ''}>Obrigatório</option>
                    </select>
                    <div style="display:flex; flex-direction:column; gap:2px;">
                        <button type="button" class="btn-icon" onclick="app.ui.moveRowUp(this)" style="padding:0; font-size:16px;"><i class='bx bx-chevron-up'></i></button>
                        <button type="button" class="btn-icon" onclick="app.ui.moveRowDown(this)" style="padding:0; font-size:16px;"><i class='bx bx-chevron-down'></i></button>
                    </div>
                    <button type="button" class="btn-icon" onclick="app.deleteAttribute(${cat.id}, ${attr.id})" title="Deletar Atributo">
                        <i class='bx bx-trash text-danger'></i>
                    </button>
                </div>
            `;
            list.insertAdjacentHTML('beforeend', html);
        });
        
        this.ui.showModal('modal-edit-category');
    },

    async deleteAttribute(catId, attrId) {
        app.ui.confirmAction('Atenção: Deletar este atributo apagará os dados deste campo em TODOS os itens. Tem certeza?', async () => {
            await this.api(`/categories/${catId}/attributes/${attrId}`, { method: 'DELETE' });
            this.ui.toast('Atributo removido', 'success');
            await this.loadCategories();
            this.openEditCategory(catId); // reload modal data
        });
    },

    async handleEditCategory(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        const catId = formData.get('id');
        const name = formData.get('name');
        
        // 1. Update Category Name
        await this.api(`/categories/${catId}`, { 
            method: 'PUT', 
            body: JSON.stringify({ name }) 
        });

        // 2. Add new attributes if any
        const attrNames = formData.getAll('attr_name[]');
        const attrTypes = formData.getAll('attr_type[]');
        const attrReq = formData.getAll('attr_req[]');

        for(let i=0; i<attrNames.length; i++) {
            if(attrNames[i].trim() !== '') {
                await this.api(`/categories/${catId}/attributes`, {
                    method: 'POST',
                    body: JSON.stringify({
                        name: attrNames[i].trim(),
                        type: attrTypes[i],
                        is_required: attrReq[i] === 'true',
                        display_order: i + 1000 // Force at end initially
                    })
                });
            }
        }
        
        // 3. Update existing attributes (order, name, requirement)
        const existingRows = document.querySelectorAll('#edit-attributes-list .attr-row-existing');
        const orderPayload = [];
        for (let i = 0; i < existingRows.length; i++) {
            const row = existingRows[i];
            const attrId = row.getAttribute('data-id');
            if (attrId) {
                orderPayload.push({ id: parseInt(attrId), display_order: i });
                
                // Fetch updated values
                const nameInput = row.querySelector('.attr-edit-name-existing');
                const reqSelect = row.querySelector('.attr-edit-req-existing');
                if (nameInput && reqSelect) {
                    const originalName = nameInput.getAttribute('data-original-name');
                    const originalReq = reqSelect.getAttribute('data-original-req') === 'true';
                    const newReq = reqSelect.value === 'true';
                    const newName = nameInput.value.trim();
                    
                    if (newName !== originalName || newReq !== originalReq) {
                        await this.api(`/categories/${catId}/attributes/${attrId}`, {
                            method: 'PUT',
                            body: JSON.stringify({
                                name: newName,
                                is_required: newReq
                            })
                        });
                    }
                }
            }
        }
        if(orderPayload.length > 0) {
            await this.api(`/categories/${catId}/attributes/order`, {
                method: 'PUT',
                body: JSON.stringify(orderPayload)
            });
        }
        
        this.ui.toast('Categoria atualizada!', 'success');
        this.ui.hideModal('modal-edit-category');
        e.target.reset();
        await this.loadCategories();
    },

    async handleCreateCategory(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        
        const payload = {
            name: formData.get('name'),
            attributes: []
        };

        const attrNames = formData.getAll('attr_name[]');
        const attrTypes = formData.getAll('attr_type[]');
        const attrReq = formData.getAll('attr_req[]');

        for(let i=0; i<attrNames.length; i++) {
            if(attrNames[i].trim() !== '') {
                payload.attributes.push({
                    name: attrNames[i].trim(),
                    type: attrTypes[i],
                    is_required: attrReq[i] === 'true',
                    display_order: i
                });
            }
        }

        try {
            await this.api('/categories/', { method: 'POST', body: JSON.stringify(payload) });
            this.ui.toast('Categoria criada com sucesso', 'success');
            this.ui.hideModal('modal-create-category');
            e.target.reset();
            document.getElementById('attributes-list').innerHTML = ''; // Limpa campos dinamicos do form
            this.loadCategories();
        } catch (e) {
            // Already handled
        }
    },

    async deleteCategory(id) {
        app.ui.confirmAction('Tem certeza? Isso apagará a categoria e todos itens relacionados.', async () => {
            await this.api(`/categories/${id}`, { method: 'DELETE' });
            this.ui.toast('Categoria removida', 'success');
            await this.loadCategories();
            await this.loadDashboardStats();
        });
    },

    async loadCategoryItems(category) {
        currentCategoryId = category.id;
        document.getElementById('current-category-name').innerText = `Itens: ${category.name}`;
        this.ui.switchSubView('entities-list');

        const thead = document.getElementById('table-entities-head');
        let headerRow = `<tr><th style="cursor:pointer; user-select:none;" onclick="app.ui.sortItems('id')">ID <i class='bx bx-sort' id="sort-icon-item-id"></i></th>`;
        category.attributes.forEach(attr => {
            headerRow += `<th style="cursor:pointer; user-select:none;" onclick="app.ui.sortItems('${app.ui.escapeHtml(attr.name)}')">${attr.name} <i class='bx bx-sort' id="sort-icon-item-${app.ui.escapeHtml(attr.name)}"></i></th>`;
        });
        headerRow += '<th>Ações</th></tr>';
        thead.innerHTML = headerRow;

        const tbody = document.getElementById('table-entities-body');
        tbody.innerHTML = `<tr><td colspan="${category.attributes.length + 2}" class="text-center">Carregando...</td></tr>`;

        try {
            const items = await this.api(`/categories/${category.id}/items/`);
            app.state.currentItems = items;
            app.state.itemSearch = '';
            app.state.itemSort = { key: 'id', dir: 'asc' };
            document.getElementById('search-items').value = '';
            
            this.ui.renderItems(category);
        } catch(e) {}
    },

        openEditItem(catId, itemId) {
        const item = app.state.currentItems.find(i => i.id === itemId);
        if(!item) return;

        document.getElementById('edit-entity-id').value = item.id;
        this.ui.buildEntityForm(item);
        this.ui.showModal('modal-entity-form');
    },

    async deleteItem(catId, itemId) {
        app.ui.confirmAction('Apagar este item?', async () => {
            await this.api(`/categories/${catId}/items/${itemId}`, { method: 'DELETE' });
            this.ui.toast('Item apagado', 'success');
            const cat = currentCategories.find(c => c.id === catId);
            if(cat) this.loadCategoryItems(cat);
            this.loadDashboardStats();
        });
    },

    
    async generateReport(e) {
        e.preventDefault();
        const btn = document.getElementById('btn-generate-report');
        btn.innerHTML = "<i class='bx bx-loader-alt bx-spin'></i> Gerando...";
        btn.disabled = true;

        const catId = document.getElementById('report-category-select').value;
        const showPwd = document.getElementById('report-show-passwords').checked;
        const canvas = document.getElementById('report-canvas');
        const content = document.getElementById('report-content');
        
        let targetCategories = [];
        if (catId === 'ALL') {
            targetCategories = currentCategories;
        } else {
            const cat = currentCategories.find(c => c.id == parseInt(catId));
            if (cat) targetCategories = [cat];
        }

        const doGenerate = async (masterPassword = null) => {
            content.innerHTML = ''; // Limpa relatórios anteriores
            document.getElementById('report-timestamp').innerText = "Data: " + new Date().toLocaleString('pt-BR');
            
            try {
                for (const category of targetCategories) {
                    // Busca itens
                    const headers = {};
                    if (masterPassword) headers['X-Master-Password'] = masterPassword;
                    const items = await this.api(`/categories/${category.id}/items/`, { headers });
                    
                    // HTML Build Process
                    let html = `<div><h3 style="margin-bottom: 0.5rem; color: #333; margin-top:2rem;">Categoria: ${category.name}</h3>`;
                    
                    if(items.length === 0) {
                        html += `<p>Nenhum item documentado nesta categoria.</p></div>`;
                        content.insertAdjacentHTML('beforeend', html);
                        continue;
                    }

                    html += `<table class="report-table"><thead><tr><th>ID</th>`;
                    category.attributes.forEach(attr => { html += `<th>${attr.name}</th>`; });
                    html += `</tr></thead><tbody>`;

                    items.forEach(item => {
                        html += `<tr><td>#${item.id}</td>`;
                        category.attributes.forEach(attr => {
                            let val = item.properties[attr.name];
                            if (val === null || val === undefined) val = '-';
                            else if (attr.type === 'Boolean') val = val ? 'Sim' : 'Não';
                            else if (attr.type === 'Password') {
                                val = showPwd ? app.ui.escapeHtml(String(val)) : '********';
                            } else if (attr.type === 'File') {
                                if (val && val !== '-') {
                                    val = app.ui.escapeHtml(val.split('/').pop());
                                } else {
                                    val = '-';
                                }
                            } else if (attr.type === 'RichText') {
                                if (val && val !== '-' && val.trim() !== '') {
                                    val = `<div class="ql-editor" style="padding: 0; min-height: auto; white-space: normal; overflow-wrap: break-word;">${val}</div>`;
                                } else {
                                    val = '-';
                                }
                            } else {
                                val = app.ui.escapeHtml(String(val));
                            }
                            html += `<td style="vertical-align: top;">${val}</td>`;
                        });
                        html += `</tr>`;
                    });
                    
                    html += `</tbody></table></div>`;
                    content.insertAdjacentHTML('beforeend', html);
                }

                canvas.classList.add('active'); // Mostra canvas
                
                // Dá um curto delay pro navegador renderizar o DOM antes de acionar Dialog de Impressão
                setTimeout(() => {
                    window.print();
                    btn.innerHTML = "<i class='bx bx-printer'></i> Gerar A4 e Imprimir";
                    btn.disabled = false;
                }, 500);

            } catch (err) {
                btn.innerHTML = "<i class='bx bx-printer'></i> Gerar A4 e Imprimir";
                btn.disabled = false;
            }
        };

        if (showPwd) {
            app.ui.verifyPassword(
                (pwd) => { doGenerate(pwd); }, 
                () => { 
                    btn.innerHTML = "<i class='bx bx-printer'></i> Gerar A4 e Imprimir";
                    btn.disabled = false;
                }
            );
        } else {
            doGenerate();
        }
    },

    async handleCreateEntity(e) {
        e.preventDefault();
        const cat = currentCategories.find(c => c.id === currentCategoryId);
        if(!cat) return;

        const formData = new FormData(e.target);
        const payload = {};
        
        let hasPasswords = false;

        cat.attributes.forEach(attr => {
            let val = formData.get(attr.name);
            if (attr.type === 'Integer') val = val ? parseInt(val) : null;
            if (attr.type === 'Boolean') val = formData.get(attr.name) === 'on';
            if (attr.type === 'Password' && formData.get(attr.name) === '') val = null;
            if (attr.type === 'Password' && val) hasPasswords = true;
            if (attr.type === 'File' && val instanceof File && val.size > 0) { payload[attr.name] = val; }
            else if (attr.type === 'File') { val = null; }
            if (val !== null && val !== '') payload[attr.name] = val;
        });
        
        const executeSave = async (masterPassword = null) => {
            try {
                const editId = document.getElementById('edit-entity-id').value;
                
                // Upload files first
                for (const key of Object.keys(payload)) {
                    if (payload[key] instanceof File) {
                        const uploadRes = await this.uploadFile(payload[key]);
                        payload[key] = uploadRes.file_path;
                    }
                }
                
                const headers = {};
                if (masterPassword) {
                    headers['X-Master-Password'] = masterPassword;
                }
                
                if(editId) {
                    await this.api(`/categories/${cat.id}/items/${editId}`, { 
                        method: 'PUT', 
                        headers,
                        body: JSON.stringify(payload) 
                    });
                    this.ui.toast('Item atualizado com sucesso!', 'success');
                } else {
                    await this.api(`/categories/${cat.id}/items/`, { 
                        method: 'POST', 
                        headers,
                        body: JSON.stringify(payload) 
                    });
                    this.ui.toast('Item criado!', 'success');
                }
                this.ui.hideModal('modal-entity-form');
                this.loadCategoryItems(cat);
                this.loadDashboardStats();
            } catch(e) {}
        };

        if (hasPasswords) {
            app.ui.verifyPassword((pwd) => {
                executeSave(pwd);
            });
        } else {
            executeSave();
        }
    },


    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        const headers = {};
        if (this.state.token) {
            headers['Authorization'] = `Bearer ${this.state.token}`;
            headers['X-API-Token'] = this.state.token;
        }
        
        const res = await fetch(`${API_BASE}/files/upload`, {
            method: 'POST',
            headers,
            body: formData
        });
        
        if (res.status === 401) {
            this.handleLogout();
            throw new Error("Sessão expirada. Faça login novamente.");
        }
        
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Erro no upload do arquivo");
        }
        return data;
    },

    async previewFile(filePath) {
        if (!filePath || filePath === '-') return;
        
        try {
            const filename = filePath.split('/').pop();
            const ext = filename.split('.').pop().toLowerCase();
            
            const headers = {};
            if (this.state.token) {
                headers['Authorization'] = `Bearer ${this.state.token}`;
                headers['X-API-Token'] = this.state.token;
            }
            
            this.ui.toast('Carregando arquivo...', 'info');
            
            const res = await fetch(`${API_BASE}/files/download?path=${encodeURIComponent(filePath)}`, {
                headers
            });
            
            if (res.status === 401) {
                this.handleLogout();
                throw new Error("Sessão expirada.");
            }
            if (!res.ok) {
                throw new Error("Erro ao baixar o arquivo.");
            }
            
            const blob = await res.blob();
            const objectUrl = URL.createObjectURL(blob);
            
            const imgExts = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'];
            const audioExts = ['mp3', 'wav', 'ogg', 'm4a'];
            const videoExts = ['mp4', 'webm', 'ogg', 'avi', 'mov'];
            
            if (imgExts.includes(ext)) {
                this.ui.showPreviewModal(filename, `<img src="${objectUrl}" style="max-width: 100%; max-height: 70vh; object-fit: contain; border-radius: 8px;">`, objectUrl, filename);
            } else if (audioExts.includes(ext)) {
                this.ui.showPreviewModal(filename, `<audio src="${objectUrl}" controls style="width: 100%; max-width: 500px;"></audio>`, objectUrl, filename);
            } else if (videoExts.includes(ext)) {
                this.ui.showPreviewModal(filename, `<video src="${objectUrl}" controls style="max-width: 100%; max-height: 70vh; border-radius: 8px;"></video>`, objectUrl, filename);
            } else if (ext === 'pdf') {
                this.ui.showPreviewModal(filename, `<iframe src="${objectUrl}" style="width: 100%; height: 70vh; border: none; border-radius: 8px;"></iframe>`, objectUrl, filename);
            } else if (ext === 'txt') {
                const text = await blob.text();
                const escText = this.ui.escapeHtml(text);
                this.ui.showPreviewModal(filename, `<pre style="width: 100%; max-height: 70vh; padding: 1rem; color: var(--text-main); font-family: monospace; white-space: pre-wrap; word-break: break-all; overflow: auto; background: rgba(0,0,0,0.3); border-radius: 8px; text-align: left; margin: 0;">${escText}</pre>`, objectUrl, filename);
            } else {
                const a = document.createElement('a');
                a.href = objectUrl;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                
                setTimeout(() => URL.revokeObjectURL(objectUrl), 10000);
            }
        } catch (err) {
            this.ui.toast(`Erro: ${err.message}`, 'error');
        }
    },

    // UI Helpers
    ui: {
        showDashboard() {
            document.getElementById('login-view').classList.add('hidden');
            document.getElementById('app-view').classList.remove('hidden');
            document.getElementById('display-user').innerText = app.state.username;
        },
        
        switchSubView(id) {
            document.querySelectorAll('.sub-view').forEach(el => el.classList.add('hidden'));
            const target = document.getElementById(`sub-${id}`);
            if (target) {
                target.classList.remove('hidden');
                
                // Update Title
                let title = "Dashboard";
                if(id === 'categories-manager') title = "Categorias (EAV)";
                if(id === 'entities-list') title = "Gerenciar Itens";
                if(id === 'reports') title = "Relatórios";
                if(id === 'mod-logs') title = "Logs de Modificações";
                document.getElementById('page-title').innerText = title;
            }
        },
        
        setActiveNav(el) {
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            if(el) el.classList.add('active');
        },
        
        
        escapeHtml(str) {
            if (str === null || str === undefined) return '';
            if (typeof str !== 'string') return str;
            return str
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        },
        toast(msg, type = 'info') {
            const container = document.getElementById('toast-container');
            const el = document.createElement('div');
            el.className = `toast ${type}`;
            el.innerHTML = msg;
            container.appendChild(el);
            setTimeout(() => {
                el.style.opacity = '0';
                setTimeout(() => el.remove(), 300);
            }, 3000);
        },

        showPreviewModal(title, htmlContent, downloadUrl = null, downloadName = null) {
            document.getElementById('modal-preview-title').innerText = title;
            document.getElementById('modal-preview-body').innerHTML = htmlContent;
            
            const btnDownload = document.getElementById('modal-preview-download');
            if (btnDownload) {
                if (downloadUrl && downloadName) {
                    btnDownload.href = downloadUrl;
                    btnDownload.download = downloadName;
                    btnDownload.classList.remove('hidden');
                } else {
                    btnDownload.classList.add('hidden');
                }
            }
            
            this.showModal('modal-preview');
        },

        showModal(id) {
            document.getElementById(id).classList.remove('hidden');
        },

        hideModal(id) {
            document.getElementById(id).classList.add('hidden');
        },

        confirmCallback: null,
        confirmTimers: [],
        
        confirmAction(message, callback) {
            this.confirmCallback = callback;
            document.getElementById('modal-confirm-message').innerText = message;
            this.showModal('modal-confirm-delete');
            
            const btnYes = document.getElementById('btn-confirm-yes');
            const btnNo = document.getElementById('btn-confirm-no');
            
            btnYes.disabled = true;
            btnNo.innerHTML = `<span>Não</span><small style="font-size: 0.75rem; margin-top: 0.2rem; display: block; height: 14px;"><span id="confirm-timer-no">10</span>s</small>`;
            btnYes.innerHTML = `<span>Sim</span><small style="font-size: 0.75rem; margin-top: 0.2rem; display: block; height: 14px;"><span id="confirm-timer-yes">5</span>s</small>`;
            
            this.confirmTimers.forEach(t => clearInterval(t));
            this.confirmTimers = [];
            
            let yesTime = 5;
            const yesInterval = setInterval(() => {
                yesTime--;
                const ty = document.getElementById('confirm-timer-yes');
                if(ty) ty.innerText = yesTime;
                
                if (yesTime <= 0) {
                    clearInterval(yesInterval);
                    btnYes.disabled = false;
                    btnYes.innerHTML = `<span>Sim</span><small style="font-size: 0.75rem; margin-top: 0.2rem; display: block; height: 14px;"></small>`;
                    
                    let noTime = 10;
                    const noInterval = setInterval(() => {
                        noTime--;
                        const tn = document.getElementById('confirm-timer-no');
                        if(tn) tn.innerText = noTime;
                        
                        if (noTime <= 0) {
                            clearInterval(noInterval);
                            app.ui.cancelConfirm();
                        }
                    }, 1000);
                    app.ui.confirmTimers.push(noInterval);
                }
            }, 1000);
            this.confirmTimers.push(yesInterval);
        },
        
        executeConfirm() {
            this.confirmTimers.forEach(t => clearInterval(t));
            this.hideModal('modal-confirm-delete');
            if(this.confirmCallback) this.confirmCallback();
        },
        
        cancelConfirm() {
            this.confirmTimers.forEach(t => clearInterval(t));
            this.hideModal('modal-confirm-delete');
            this.confirmCallback = null;
        },

        async saveCategoryOrder() {
            const tbody = document.getElementById('table-categories-body');
            const rows = tbody.querySelectorAll('tr[data-id]');
            const orderPayload = [];
            rows.forEach((row, index) => {
                const id = row.getAttribute('data-id');
                if(id) {
                    orderPayload.push({ id: parseInt(id), display_order: index });
                }
            });
            if(orderPayload.length > 0) {
                try {
                    await app.api(`/categories/order/update`, {
                        method: 'PUT',
                        body: JSON.stringify(orderPayload)
                    });
                    app.ui.toast('Ordem salva com sucesso!', 'success');
                    await app.loadCategories();
                } catch(e) {}
            }
        },

        moveCategoryUp(btn) {
            const row = btn.closest('tr');
            if(row.previousElementSibling && row.previousElementSibling.hasAttribute('data-id')) {
                row.parentNode.insertBefore(row, row.previousElementSibling);
                this.saveCategoryOrder();
            }
        },
        moveCategoryDown(btn) {
            const row = btn.closest('tr');
            if(row.nextElementSibling && row.nextElementSibling.hasAttribute('data-id')) {
                row.parentNode.insertBefore(row.nextElementSibling, row);
                this.saveCategoryOrder();
            }
        },

        verifyPasswordCallback: null,
        verifyPasswordCancelCallback: null,
        verifyPassword(onSuccess, onCancel) {
            this.verifyPasswordCallback = onSuccess;
            this.verifyPasswordCancelCallback = onCancel;
            document.getElementById('verify-password-input').value = '';
            this.showModal('modal-verify-password');
        },
        cancelVerifyPassword() {
            this.hideModal('modal-verify-password');
            if(this.verifyPasswordCancelCallback) this.verifyPasswordCancelCallback();
            this.verifyPasswordCallback = null;
            this.verifyPasswordCancelCallback = null;
        },

        async submitSetupMasterPassword(e) {
            e.preventDefault();
            const pwd = document.getElementById('setup-master-password-input').value;
            if(pwd.length < 6) {
                app.ui.toast('A senha deve ter pelo menos 6 caracteres.', 'error');
                return;
            }
            try {
                await app.api('/config/master-password', {
                    method: 'POST',
                    body: JSON.stringify({ master_password: pwd })
                });
                app.ui.toast('Senha Mestra configurada!', 'success');
                app.ui.hideModal('modal-setup-master-password');
                document.getElementById('setup-master-password-input').value = '';
            } catch(err) {
                // Error handled
            }
        },

        async submitChangeMasterPassword(e) {
            e.preventDefault();
            const oldPwd = document.getElementById('change-old-password').value;
            const newPwd = document.getElementById('change-new-password').value;
            
            if(newPwd.length < 6) {
                app.ui.toast('A nova senha deve ter pelo menos 6 caracteres.', 'error');
                return;
            }
            
            const btn = e.target.querySelector('button[type="submit"]');
            btn.innerHTML = "<i class='bx bx-loader-alt bx-spin'></i> Aguarde...";
            btn.disabled = true;
            
            try {
                await app.api('/config/master-password/change', {
                    method: 'POST',
                    body: JSON.stringify({ old_password: oldPwd, new_password: newPwd })
                });
                app.ui.toast('Senha Mestra alterada com sucesso!', 'success');
                app.ui.hideModal('modal-change-master-password');
                e.target.reset();
            } catch(err) {
                // Error handled
            } finally {
                btn.innerHTML = "Alterar e Migrar Dados";
                btn.disabled = false;
            }
        },

        submitVerifyPassword(e) {
            e.preventDefault();
            const pwd = document.getElementById('verify-password-input').value;
            this.hideModal('modal-verify-password');
            if (this.verifyPasswordCallback) {
                this.verifyPasswordCallback(pwd);
            }
            this.verifyPasswordCallback = null;
            this.verifyPasswordCancelCallback = null;
        },
        
        filterCategories(term) {
            app.state.catSearch = term.toLowerCase();
            this.renderCategories();
        },
        sortCategories(key) {
            if (app.state.catSort.key === key) {
                app.state.catSort.dir = app.state.catSort.dir === 'asc' ? 'desc' : 'asc';
            } else {
                app.state.catSort.key = key;
                app.state.catSort.dir = 'asc';
            }
            this.renderCategories();
        },
        renderCategories() {
            let data = currentCategories.filter(c => 
                c.name.toLowerCase().includes(app.state.catSearch) || 
                c.id.toString().includes(app.state.catSearch)
            );
            data.sort((a, b) => {
                let valA = a[app.state.catSort.key];
                let valB = b[app.state.catSort.key];
                if (typeof valA === 'string') valA = valA.toLowerCase();
                if (typeof valB === 'string') valB = valB.toLowerCase();
                if (valA < valB) return app.state.catSort.dir === 'asc' ? -1 : 1;
                if (valA > valB) return app.state.catSort.dir === 'asc' ? 1 : -1;
                return 0;
            });
            const tbody = document.getElementById('table-categories-body');
            tbody.innerHTML = '';
            if (data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center">Nenhuma categoria encontrada.</td></tr>';
            } else {
                data.forEach(cat => {
                    const tr = document.createElement('tr');
                    tr.setAttribute('data-id', cat.id);
                    const attrs = cat.attributes.map(a => `<span class="badge" style="margin-right: 4px;">${app.ui.escapeHtml(a.name)} (${a.type})</span>`).join('') || '-';
                    tr.innerHTML = `
                        <td>#${cat.id}</td>
                        <td><strong>${app.ui.escapeHtml(cat.name)}</strong></td>
                        <td>
                            <div style="display:flex; gap:2px;">
                                <button type="button" class="btn-icon" onclick="app.ui.moveCategoryUp(this)" style="padding:0; font-size:20px;" title="Subir"><i class='bx bx-up-arrow-circle text-primary'></i></button>
                                <button type="button" class="btn-icon" onclick="app.ui.moveCategoryDown(this)" style="padding:0; font-size:20px;" title="Descer"><i class='bx bx-down-arrow-circle text-primary'></i></button>
                            </div>
                        </td>
                        <td>${attrs}</td>
                        <td>
                            <button class="btn-icon" onclick="app.openEditCategory(${cat.id})" title="Editar"><i class='bx bx-edit text-primary'></i></button>
                            <button class="btn-icon" onclick="app.deleteCategory(${cat.id})" title="Deletar"><i class='bx bx-trash text-danger' style="color:var(--danger)"></i></button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            }
            document.getElementById('sort-icon-cat-id').className = 'bx bx-sort';
            document.getElementById('sort-icon-cat-name').className = 'bx bx-sort';
            const icon = document.getElementById(`sort-icon-cat-${app.state.catSort.key}`);
            if(icon) icon.className = app.state.catSort.dir === 'asc' ? 'bx bx-sort-down' : 'bx bx-sort-up';
        },

        filterItems(term) {
            app.state.itemSearch = term.toLowerCase();
            const cat = currentCategories.find(c => c.id === currentCategoryId);
            if(cat) this.renderItems(cat);
        },
        sortItems(key) {
            if (app.state.itemSort.key === key) {
                app.state.itemSort.dir = app.state.itemSort.dir === 'asc' ? 'desc' : 'asc';
            } else {
                app.state.itemSort.key = key;
                app.state.itemSort.dir = 'asc';
            }
            const cat = currentCategories.find(c => c.id === currentCategoryId);
            if(cat) this.renderItems(cat);
        },
        renderItems(category) {
            const tbody = document.getElementById('table-entities-body');
            
            let data = app.state.currentItems.filter(item => {
                if (app.state.itemSearch === '') return true;
                if (item.id.toString().includes(app.state.itemSearch)) return true;
                
                for (const attr of category.attributes) {
                    if (attr.type === 'Password') continue; // Do not search passwords
                    let val = item.properties[attr.name];
                    if (val === null || val === undefined) continue;
                    
                    if (attr.type === 'Boolean') val = val ? 'Sim' : 'Não';
                    else if (attr.type === 'File') val = val.split('/').pop();
                    else val = String(val);
                    
                    if (val.toLowerCase().includes(app.state.itemSearch)) return true;
                }
                return false;
            });
            
            data.sort((a, b) => {
                let valA, valB;
                if (app.state.itemSort.key === 'id') {
                    valA = a.id; valB = b.id;
                } else {
                    valA = a.properties[app.state.itemSort.key] || '';
                    valB = b.properties[app.state.itemSort.key] || '';
                }
                if (typeof valA === 'string') valA = valA.toLowerCase();
                if (typeof valB === 'string') valB = valB.toLowerCase();
                if (valA < valB) return app.state.itemSort.dir === 'asc' ? -1 : 1;
                if (valA > valB) return app.state.itemSort.dir === 'asc' ? 1 : -1;
                return 0;
            });
            
            tbody.innerHTML = '';
            if(data.length === 0) {
                tbody.innerHTML = `<tr><td colspan="${category.attributes.length + 2}" class="text-center">Nenhum item encontrado.</td></tr>`;
                return;
            }

            data.forEach(item => {
                const tr = document.createElement('tr');
                let cols = `<td>#${item.id}</td>`;
                
                category.attributes.forEach(attr => {
                    let val = item.properties[attr.name];
                    if (val === null || val === undefined) val = '-';
                    else if (attr.type === 'Boolean') val = val ? 'Sim' : 'Não';
                    else if (attr.type === 'Password') {
                        const esAttr = app.ui.escapeHtml(attr.name);
                        val = `<span style="position:relative; padding-right:2rem;"><span class="pwd-mask">********</span> <i class="bx bx-show pwd-toggle" onclick="app.ui.togglePwd(this, ${item.id}, ${category.id}, '${esAttr}')"></i></span>`;
                    } else if (attr.type === 'File') {
                        if (val && val !== '-') {
                            const filename = val.split('/').pop();
                            const esVal = app.ui.escapeHtml(String(val));
                            const esName = app.ui.escapeHtml(String(filename));
                            val = `<div class="file-cell">
                                     <span class="file-name" title="${esVal}">${esName}</span>
                                     <button type="button" class="btn-icon" onclick="app.previewFile('${esVal}')" title="Visualizar/Baixar"><i class='bx bx-show-alt text-primary'></i></button>
                                   </div>`;
                        } else {
                            val = '-';
                        }
                    } else if (attr.type === 'RichText') {
                        if (val && val !== '-' && val.trim() !== '') {
                            const safeName = app.ui.escapeHtml(attr.name);
                            
                            // Extrai o texto limpo do HTML para gerar o título/assunto
                            const tempDiv = document.createElement('div');
                            tempDiv.innerHTML = val;
                            let extractedTitle = '';
                            
                            // Tenta extrair apenas do primeiro bloco (ex: o primeiro <p> ou <h1>) para evitar vazamento de outras linhas
                            const firstChild = tempDiv.firstElementChild;
                            if (firstChild) {
                                extractedTitle = (firstChild.innerText || firstChild.textContent || '').trim();
                            } else {
                                extractedTitle = (tempDiv.innerText || tempDiv.textContent || '').trim();
                            }
                            
                            // Garante que só pegará a primeira linha
                            extractedTitle = extractedTitle.split('\n')[0].trim();
                            
                            if (extractedTitle.length > 40) {
                                extractedTitle = extractedTitle.substring(0, 40) + '...';
                            }
                            if (!extractedTitle) extractedTitle = '(Conteúdo Rico)';
                            
                            val = `<div class="file-cell">
                                     <span class="file-name" style="color:var(--text-color);" title="${app.ui.escapeHtml(extractedTitle)}"><b>${app.ui.escapeHtml(extractedTitle)}</b></span>
                                     <button type="button" class="btn-icon" onclick="app.ui.showPreviewModal('${safeName}', '<div class=\\'ql-editor\\' style=\\'text-align: left;\\'>' + decodeURIComponent('${encodeURIComponent(val)}') + '</div>')" title="Visualizar Conteúdo"><i class='bx bx-show-alt text-primary'></i></button>
                                   </div>`;
                        } else {
                            val = '-';
                        }
                    } else {
                        val = app.ui.escapeHtml(String(val));
                    }
                    cols += `<td>${val}</td>`;
                });

                cols += `
                    <td>
                        <button class="btn-icon" onclick="app.openEditItem(${category.id}, ${item.id})" title="Editar"><i class='bx bx-edit text-primary'></i></button>
                        <button class="btn-icon" onclick="app.deleteItem(${category.id}, ${item.id})" title="Deletar"><i class='bx bx-trash' style="color:var(--danger)"></i></button>
                    </td>
                `;
                tr.innerHTML = cols;
                tbody.appendChild(tr);
            });
            
            // update sort icons
            document.querySelectorAll('#table-entities-head .bx-sort, #table-entities-head .bx-sort-up, #table-entities-head .bx-sort-down').forEach(el => el.className = 'bx bx-sort');
            const iconId = app.state.itemSort.key === 'id' ? 'sort-icon-item-id' : `sort-icon-item-${app.ui.escapeHtml(app.state.itemSort.key)}`;
            const icon = document.getElementById(iconId);
            if(icon) icon.className = app.state.itemSort.dir === 'asc' ? 'bx bx-sort-down' : 'bx bx-sort-up';
        },
        async togglePwd(iconEl, itemId, catId, attrName) {
            const span = iconEl.previousElementSibling;
            if(span.innerText === '********') {
                this.verifyPassword(async (pwd) => {
                    try {
                        const res = await app.api(`/categories/${catId}/items/${itemId}/reveal`, {
                            method: 'POST',
                            body: JSON.stringify({ master_password: pwd })
                        });
                        if (res[attrName]) {
                            span.innerText = res[attrName];
                            iconEl.classList.replace('bx-show', 'bx-hide');
                        } else {
                            app.ui.toast('Não foi possível descriptografar', 'error');
                        }
                    } catch(e) {
                        // Error handled by api wrapper
                    }
                });
            } else {
                span.innerText = '********';
                iconEl.classList.replace('bx-hide', 'bx-show');
            }
        },
        
        moveRowUp(btn) {
            const row = btn.closest('.flex-between');
            if(row.previousElementSibling) {
                row.parentNode.insertBefore(row, row.previousElementSibling);
            }
        },
        moveRowDown(btn) {
            const row = btn.closest('.flex-between');
            if(row.nextElementSibling) {
                row.parentNode.insertBefore(row.nextElementSibling, row);
            }
        },

        toggleInputPwd(iconEl) {
            const inp = iconEl.previousElementSibling;
            if(inp.type === 'password') {
                inp.type = 'text';
                iconEl.classList.replace('bx-show', 'bx-hide');
            } else {
                inp.type = 'password';
                iconEl.classList.replace('bx-hide', 'bx-show');
            }
        },
        appendEditAttributeRow() {
            const list = document.getElementById('edit-attributes-list');
            const html = `
                <div class="flex-between mb-2" style="gap: 0.5rem">
                    <input type="text" name="attr_name[]" placeholder="Nome do novo campo" style="flex:2" required>
                    <select name="attr_type[]" style="flex:1">
                        <option value="String">Texto</option>
                        <option value="Integer">Número (Int)</option>
                        <option value="Date">Data</option>
                        <option value="Boolean">Verdadeiro/Falso</option>
                        <option value="Password">Senha (Oculto)</option>
                        <option value="File">Arquivo</option>
                        <option value="RichText">Texto Longo</option>
                    </select>
                    <select name="attr_req[]" style="flex:1">
                        <option value="false">Opcional</option>
                        <option value="true">Obrigatório</option>
                    </select>
                    <div style="display:flex; flex-direction:column; gap:2px;">
                        <button type="button" class="btn-icon" onclick="app.ui.moveRowUp(this)" style="padding:0; font-size:16px;"><i class='bx bx-chevron-up'></i></button>
                        <button type="button" class="btn-icon" onclick="app.ui.moveRowDown(this)" style="padding:0; font-size:16px;"><i class='bx bx-chevron-down'></i></button>
                    </div>
                    <button type="button" class="btn-icon" onclick="this.parentElement.remove()"><i class='bx bx-x text-danger'></i></button>
                </div>
            `;
            list.insertAdjacentHTML('beforeend', html);
        },
        appendAttributeRow() {
            const list = document.getElementById('attributes-list');
            const html = `
                <div class="flex-between mb-2" style="gap: 0.5rem">
                    <input type="text" name="attr_name[]" placeholder="Nome do campo" style="flex:2" required>
                    <select name="attr_type[]" style="flex:1">
                        <option value="String">Texto</option>
                        <option value="Integer">Número (Int)</option>
                        <option value="Date">Data</option>
                        <option value="Boolean">Verdadeiro/Falso</option>
                        <option value="Password">Senha (Oculto)</option>
                        <option value="File">Arquivo</option>
                        <option value="RichText">Texto Longo</option>
                    </select>
                    <select name="attr_req[]" style="flex:1">
                        <option value="false">Opcional</option>
                        <option value="true">Obrigatório</option>
                    </select>
                    <div style="display:flex; flex-direction:column; gap:2px;">
                        <button type="button" class="btn-icon" onclick="app.ui.moveRowUp(this)" style="padding:0; font-size:16px;"><i class='bx bx-chevron-up'></i></button>
                        <button type="button" class="btn-icon" onclick="app.ui.moveRowDown(this)" style="padding:0; font-size:16px;"><i class='bx bx-chevron-down'></i></button>
                    </div>
                    <button type="button" class="btn-icon" onclick="this.parentElement.remove()"><i class='bx bx-x text-danger'></i></button>
                </div>
            `;
            list.insertAdjacentHTML('beforeend', html);
        },

        buildEntityForm(existingItem = null) {
            const cat = currentCategories.find(c => c.id === currentCategoryId);
            if(!cat) return;
            
            document.getElementById('modal-entity-title').innerText = existingItem ? `Editar Item: ${cat.name}` : `Novo Item: ${cat.name}`;
            const fieldsContainer = document.getElementById('dynamic-form-fields');
            fieldsContainer.innerHTML = '';

            cat.attributes.forEach(attr => {
                const reqAttr = attr.is_required ? 'required' : '';
                const reqStar = attr.is_required ? '<span style="color:var(--danger)">*</span>' : '';
                
                let val = '';
                let isChecked = '';
                if (existingItem) {
                    val = existingItem.properties[attr.name];
                    if (val === null || val === undefined) val = '';
                    if (attr.type === 'Boolean' && val === true) isChecked = 'checked';
                    if (attr.type === 'Password') val = ''; // Por segurança a senha não volta preenchida para edição (vai null se vazio)
                }
                
                let inputHtml = '';
                if(attr.type === 'String') {
                    inputHtml = `<input type="text" name="${app.ui.escapeHtml(attr.name)}" ${reqAttr} value="${app.ui.escapeHtml(String(val))}">`;
                } else if(attr.type === 'Integer') {
                    inputHtml = `<input type="number" name="${app.ui.escapeHtml(attr.name)}" ${reqAttr} value="${val}">`;
                } else if(attr.type === 'Date') {
                    inputHtml = `<input type="date" name="${app.ui.escapeHtml(attr.name)}" ${reqAttr} value="${val}">`;
                } else if(attr.type === 'Boolean') {
                    inputHtml = `<input type="checkbox" name="${app.ui.escapeHtml(attr.name)}" id="${app.ui.escapeHtml(attr.name)}" style="width: auto; margin-right: 8px;" ${isChecked}>`;
                } else if(attr.type === 'File') {
                    let existingFileText = '';
                    let currentReqAttr = reqAttr;
                    if (val && val !== '-') {
                        const filename = val.split('/').pop();
                        existingFileText = `<div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.3rem;">Arquivo atual: <strong>${app.ui.escapeHtml(filename)}</strong> (Deixe em branco para manter)</div>`;
                        currentReqAttr = ''; // Not required if it already exists
                    }
                    inputHtml = `
                        ${existingFileText}
                        <input type="file" name="${app.ui.escapeHtml(attr.name)}" ${currentReqAttr} class="form-control">
                    `;
                } else if(attr.type === 'Password') {
                    let currentReqAttr = reqAttr;
                    if (existingItem && existingItem.properties[attr.name]) {
                        currentReqAttr = ''; // Already has password, so not required to type again
                    }
                    inputHtml = `
                        <div style="position:relative; width:100%;">
                            <input type="password" name="${app.ui.escapeHtml(attr.name)}" ${currentReqAttr} placeholder="${existingItem ? 'Deixe em branco para manter original' : ''}" style="padding-right: 2.5rem;">
                            <i class='bx bx-show pwd-toggle' style="top: 10px; right: 10px;" onclick="app.ui.toggleInputPwd(this)"></i>
                        </div>`;
                } else if(attr.type === 'RichText') {
                    inputHtml = `
                        <div style="font-size: 0.8rem; color: var(--primary); margin-bottom: 0.2rem;"><i class='bx bx-info-circle'></i> Dica: A primeira linha do seu texto será usada como o <b>Assunto</b> na listagem principal.</div>
                        <input type="hidden" name="${app.ui.escapeHtml(attr.name)}" id="hidden-${app.ui.escapeHtml(attr.name)}" value="${app.ui.escapeHtml(String(val))}">
                        <div id="editor-${app.ui.escapeHtml(attr.name)}" style="height: 250px; background: white; color: black; border-radius: 0 0 4px 4px;">${val}</div>
                    `;
                }

                fieldsContainer.insertAdjacentHTML('beforeend', `
                    <div class="input-group">
                        <label>${attr.name} ${reqStar}</label>
                        ${inputHtml}
                    </div>
                `);
            });

            // Initialize Quill editors
            setTimeout(() => {
                cat.attributes.forEach(attr => {
                    if (attr.type === 'RichText') {
                        const editorId = `editor-${app.ui.escapeHtml(attr.name)}`;
                        const hiddenId = `hidden-${app.ui.escapeHtml(attr.name)}`;
                        
                        const quill = new Quill(`#${editorId}`, {
                            theme: 'snow',
                            modules: {
                                toolbar: [
                                    [{ 'header': [1, 2, 3, false] }],
                                    ['bold', 'italic', 'underline', 'strike'],
                                    ['blockquote', 'code-block'],
                                    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                                    [{ 'color': [] }, { 'background': [] }],
                                    ['link', 'image'],
                                    ['clean']
                                ]
                            }
                        });
                        
                        // Custom image handler to upload to API instead of base64
                        quill.getModule('toolbar').addHandler('image', function() {
                            const input = document.createElement('input');
                            input.setAttribute('type', 'file');
                            input.setAttribute('accept', 'image/*');
                            input.click();
                            
                            input.onchange = async () => {
                                const file = input.files[0];
                                if (file) {
                                    try {
                                        app.ui.toast("Enviando imagem...", "info");
                                        const res = await app.uploadFile(file);
                                        const url = `/api/files/download?path=${encodeURIComponent(res.file_path)}`;
                                        const range = quill.getSelection(true);
                                        quill.insertEmbed(range.index, 'image', url);
                                        quill.setSelection(range.index + 1);
                                        app.ui.toast("Imagem enviada com sucesso!", "success");
                                    } catch(e) {
                                        app.ui.toast("Erro ao enviar imagem: " + e.message, "error");
                                    }
                                }
                            };
                        });
                        
                        quill.on('text-change', function() {
                            document.getElementById(hiddenId).value = quill.root.innerHTML;
                        });
                    }
                });
            }, 100);
        }
    }
};

document.addEventListener('DOMContentLoaded', () => app.init());

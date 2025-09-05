async function updateCanton() {
    const parroquia = document.getElementById('gad_parroquial')?.value;
    if (parroquia) {
        try {
            const response = await fetch('/get_canton', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ parroquia })
            });
            if (!response.ok) throw new Error('Error en la petición');
            const data = await response.json();
            document.getElementById('canton').value = data.canton || '';
        } catch (error) {
            document.getElementById('canton').value = '';
        }
    } else {
        document.getElementById('canton').value = '';
    }
}
const flashes = document.querySelectorAll('.alert');
flashes.forEach((flash, index) => {
    flash.style.top = `${20 + (index * 80)}px`;
    setTimeout(() => {
        flash.style.animation = 'fadeOut 0.5s ease-in-out';
        setTimeout(() => flash.remove(), 500);
    }, 3000);
});


async function fetchNotifications() {
    try {
        console.log('Fetching notifications...');
        const response = await fetch('/get_notifications', {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });
        if (!response.ok) throw new Error(`Error fetching notifications: ${response.status}`);
        const data = await response.json();
        console.log('Notifications data:', data);

        const notificationCount = document.getElementById('notificationCount');
        const notificationList = document.getElementById('notificationList');
        if (!notificationCount || !notificationList) {
            console.error('Notification elements not found in DOM');
            return;
        }

        notificationCount.textContent = data.count || 0;
        notificationList.innerHTML = '';
        if (data.count === 0 || !data.notifications.length) {
            notificationList.innerHTML = '<li class="dropdown-item text-muted">No hay notificaciones</li>';
        } else {
            data.notifications.forEach(notification => {
                const li = document.createElement('li');
                li.className = 'dropdown-item';
                li.innerHTML = `<strong>${notification.message}</strong><br><small>${notification.timestamp}</small>`;
                notificationList.appendChild(li);
            });
        }
    } catch (error) {
        console.error('Error in fetchNotifications:', error);
        const notificationList = document.getElementById('notificationList');
        if (notificationList) {
            notificationList.innerHTML = '<li class="dropdown-item text-danger">Error al cargar notificaciones</li>';
        }
    }
}

async function clearNotifications() {
    try {
        console.log('Clearing notifications...');
        const response = await fetch('/clear_notifications', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        console.log('Clear notifications response:', data);
        if (data.success) {
            await fetchNotifications();
        } else {
            console.error('Error clearing notifications:', data.error);
        }
    } catch (error) {
        console.error('Error in clearNotifications:', error);
    }
}

function handleFlashes() {
    const flashes = document.querySelectorAll('.alert');
    flashes.forEach((flash, index) => {
        flash.style.top = `${20 + (index * 80)}px`;
        flash.style.animation = 'fadeIn 0.5s ease-in-out';
        setTimeout(() => {
            flash.style.animation = 'fadeOut 0.5s ease-in-out';
            setTimeout(() => flash.remove(), 500);
        }, 3500);
    });
}
async function clearNotifications() {
        try {
            const response = await fetch('/clear_notifications', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            if (data.success) {
                fetchNotifications();
            } else {
                console.error('Error clearing notifications:', data.error);
            }
        } catch (error) {
            console.error('Error clearing notifications:', error);
        }
    }
    document.addEventListener('DOMContentLoaded', () => {
        fetchNotifications();
        setInterval(fetchNotifications, 10000);
    });


document.addEventListener('DOMContentLoaded', function () {
    console.log('DOM fully loaded');

    function showSection(sectionId) {
        console.log('showSection called with sectionId:', sectionId);

        document.querySelectorAll('.card-section').forEach(section => {
            section.classList.remove('active');
            section.classList.add('d-none');
        });

        const targetSection = document.getElementById(`section-${sectionId}`);
        if (targetSection) {
            targetSection.classList.remove('d-none');
            targetSection.classList.add('active');
            console.log(`Section ${sectionId} is now active`);
        } else {
            console.error(`Section with ID section-${sectionId} not found`);
        }

        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });
        const activeLink = document.querySelector(`.nav-link[onclick="showSection('${sectionId}')"]`);
        if (activeLink) {
            activeLink.classList.add('active');
            console.log(`Nav link for ${sectionId} set to active`);
        }
        localStorage.setItem('currentSection', sectionId);
    }

    function showPanel(panelId) {
        document.querySelectorAll('.fade-panel').forEach(panel => panel.classList.remove('active'));
        document.querySelectorAll('.nav-link').forEach(link => link.classList.remove('active'));
        const panelElement = document.getElementById(`panel-${panelId}`);
        const tabElement = document.getElementById(`tab-${panelId}`);
        if (panelElement && tabElement) {
            panelElement.classList.add('active');
            tabElement.classList.add('active');
        }
        localStorage.setItem('currentPanel', panelId);
    }

    function showPanel(panelId) {
        document.querySelectorAll('.fade-panel').forEach(panel => {
            panel.classList.remove('active');
        });
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });
        document.getElementById(`panel-${panelId}`).classList.add('active');
        document.getElementById(`tab-${panelId}`).classList.add('active');
    }


    window.showSection = showSection;
    window.showPanel = showPanel;


    async function updateCantonEdit() {
        const parroquia = document.getElementById('edit_gad_parroquial')?.value;
        if (parroquia) {
            try {
                const response = await fetch('/get_canton', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ parroquia })
                });
                if (!response.ok) throw new Error('Error fetching canton');
                const data = await response.json();
                document.getElementById('edit_canton').value = data.canton || '';
            } catch (error) {
                console.error('Error in updateCantonEdit:', error);
                document.getElementById('edit_canton').value = '';
            }
        } else {
            document.getElementById('edit_canton').value = '';
        }
    }

    window.updateCantonEdit = updateCantonEdit;

    function addTechnicianPair(container, selectedTechnician = '', selectedAdvisory = '') {
        const tecnicoOptions = Array.from(document.querySelectorAll('#tecnico-options option'))
            .map(opt => `<option value="${opt.value}" ${selectedTechnician === opt.value ? 'selected' : ''}>${opt.text}</option>`)
            .join('');
        const tipoOptions = Array.from(document.querySelectorAll('#tipo-options option'))
            .map(opt => `<option value="${opt.value}" ${selectedAdvisory === opt.value ? 'selected' : ''}>${opt.text}</option>`)
            .join('');

        const pairDiv = document.createElement('div');
        pairDiv.className = 'tecnico-asesoria-pair mb-2';
        pairDiv.innerHTML = `
            <div class="row g-2 align-items-center">
                <div class="col">
                    <select name="tecnico_asignado[]" class="form-select form-select-sm" required>
                        <option value="" disabled ${!selectedTechnician ? 'selected' : ''}>Seleccione Técnico</option>
                        ${tecnicoOptions}
                    </select>
                </div>
                <div class="col">
                    <select name="tipo_asesoria[]" class="form-select form-select-sm" required>
                        <option value="" disabled ${!selectedAdvisory ? 'selected' : ''}>Tipo Asesoría</option>
                        ${tipoOptions}
                    </select>
                </div>
                <div class="col-auto">
                    <button type="button" class="btn btn-sm btn-danger remove-pair">X</button>
                </div>
            </div>
        `;
        container.appendChild(pairDiv);
        pairDiv.querySelector('.remove-pair').addEventListener('click', () => {
            if (container.querySelectorAll('.tecnico-asesoria-pair').length > 1) {
                pairDiv.remove();
            }
        });
    }

    function toggleEntregaFields(oficioId) {
        const entregaRecepcion = document.getElementById(`entrega_recepcion_${oficioId}`);
        if (entregaRecepcion) {
            const entregaFields = document.querySelectorAll(`#entrega_fields_${oficioId}, #acta_entrega_field_${oficioId}`);
            entregaFields.forEach(field => {
                field.style.display = entregaRecepcion.value === 'Aplica' ? 'block' : 'none';
            });
        }
    }

    window.toggleEntregaFields = toggleEntregaFields;

    async function fetchNotifications() {
        try {
            const response = await fetch('/get_notifications');
            const data = await response.json();
            const notificationCount = document.getElementById('notificationCount');
            const notificationList = document.getElementById('notificationList');
            notificationCount.textContent = data.count;
            notificationList.innerHTML = '';
            if (data.count === 0) {
                notificationList.innerHTML = '<li class="dropdown-item text-muted">No hay notificaciones</li>';
            } else {
                data.notifications.forEach(notification => {
                    const li = document.createElement('li');
                    li.className = 'dropdown-item';
                    li.innerHTML = `<strong>${notification.message}</strong><br><small>${notification.timestamp}</small>`;
                    notificationList.appendChild(li);
                });
            }
        } catch (error) {
            console.error('Error fetching notifications:', error);
        }
    }

    
    const staticModals = ['#editModal', '#confirmModal', '#changePasswordModal'];
    staticModals.forEach(selector => {
        const modal = document.querySelector(selector);
        if (modal && !modal._bootstrapModal) {
            new bootstrap.Modal(modal, {
                backdrop: 'static',
                keyboard: false
            });
        }
    });

    document.querySelectorAll('.entregar-btn').forEach(button => {
        const modalId = button.getAttribute('data-modal-id') || `confirmEntregarModal_${button.getAttribute('data-id')}`;
        button.addEventListener('click', () => {
            console.log(`Opening modal: ${modalId}`);
            const modal = document.getElementById(modalId);
            if (modal) {
                const bsModal = new bootstrap.Modal(modal, {
                    backdrop: 'static',
                    keyboard: false
                });
                bsModal.show();
            } else {
                console.error(`Modal with ID ${modalId} not found`);
            }
        });
    });

    document.querySelectorAll('.edit-btn').forEach(button => {
        button.addEventListener('click', function () {
            const id = button.getAttribute('data-id');
            const fechaEnviado = button.getAttribute('data-fecha-enviado');
            const numeroOficio = button.getAttribute('data-numero-oficio');
            const gadParroquial = button.getAttribute('data-gad-parroquial');
            const canton = button.getAttribute('data-canton');
            const detalle = button.getAttribute('data-detalle');
            const assignments = JSON.parse(button.getAttribute('data-assignments') || '[]');

            console.log('Edit button clicked for oficio:', id);

            document.getElementById('edit_oficio_id').value = id;
            document.getElementById('edit_fecha_enviado').value = fechaEnviado;
            document.getElementById('edit_numero_oficio').value = numeroOficio;
            document.getElementById('edit_gad_parroquial').value = gadParroquial;
            document.getElementById('edit_canton').value = canton;
            document.getElementById('edit_detalle').value = detalle;

            const pairContainer = document.getElementById('edit_tecnico_asesoria_pairs');
            pairContainer.innerHTML = '';
            assignments.forEach(assignment => {
                addTechnicianPair(pairContainer, assignment.tecnico, assignment.tipo_asesoria);
            });

            if (assignments.length === 0) {
                addTechnicianPair(pairContainer);
            }
        });
    });

    document.querySelectorAll('.add-pair').forEach(button => {
        button.addEventListener('click', function () {
            const pairContainer = document.getElementById('edit_tecnico_asesoria_pairs');
            addTechnicianPair(pairContainer);
        });
    });

    document.querySelectorAll('.add-pair').forEach(button => {
        button.addEventListener('click', () => {
            const oficioId = button.getAttribute('data-oficio-id');
            const container = document.getElementById(`tecnico-asesoria-pairs-${oficioId}`);
            if (container) {
                addTechnicianPair(container);
            }
        });
    });

    window.enableEdit = function (tipoId) {
        const input = document.getElementById(`input-tipo-${tipoId}`);
        const saveButton = document.getElementById(`save-tipo-${tipoId}`);
        input.readOnly = false;
        input.focus();
        saveButton.classList.remove('d-none');
    };

    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const numeroOficio = document.getElementById('numero_oficio').value;
            const fechaEnviado = document.getElementById('fecha_enviado').value;
            const gadParroquial = document.getElementById('gad_parroquial').value;
            const canton = document.getElementById('canton').value;
            const detalle = document.getElementById('detalle').value;

            document.getElementById('confirm_numero_oficio').textContent = numeroOficio;
            document.getElementById('confirm_fecha_enviado').textContent = fechaEnviado;
            document.getElementById('confirm_gad_parroquial').textContent = gadParroquial;
            document.getElementById('confirm_canton').textContent = canton;
            document.getElementById('confirm_detalle').textContent = detalle;

            const confirmModal = new bootstrap.Modal(document.getElementById('confirmModal'));
            confirmModal.show();

            const confirmSubmit = document.getElementById('confirmSubmit');
            if (confirmSubmit) {
                confirmSubmit.onclick = () => {
                    registerForm.submit();
                };
            }
        });
    }

    const filterField = document.getElementById('filterField');
    const filterValue = document.getElementById('filterValue');
    const tableRowsReceive = document.querySelectorAll('#historial-registros tbody tr');

    function applyDynamicFilter() {
        const field = filterField.value;
        const value = filterValue.value.toLowerCase();

        tableRowsReceive.forEach(row => {
            let rowValue = '';
            switch (field) {
                case 'id':
                    rowValue = row.dataset.id?.toLowerCase() || '';
                    break;
                case 'fecha':
                    rowValue = row.dataset.fecha?.toLowerCase() || '';
                    break;
                case 'canton':
                    rowValue = row.dataset.canton?.toLowerCase() || '';
                    break;
                case 'gad':
                    rowValue = row.dataset.gad?.toLowerCase() || '';
                    break;
                case 'numero':
                    rowValue = row.dataset.numero?.toLowerCase() || '';
                    break;
            }
            row.style.display = !value || rowValue.includes(value) ? '' : 'none';
        });
    }

    if (filterField && filterValue) {
        filterField.addEventListener('change', applyDynamicFilter);
        filterValue.addEventListener('input', applyDynamicFilter);
    }

    if (filterId) filterId.addEventListener('input', applyReceiveFilters);
    if (filterFecha) filterFecha.addEventListener('change', applyReceiveFilters);
    if (filterCanton) filterCanton.addEventListener('input', applyReceiveFilters);
    if (filterGad) filterGad.addEventListener('change', applyReceiveFilters);
    if (filterNumeroOficio) filterNumeroOficio.addEventListener('input', applyReceiveFilters);

    const filterIdDesign = document.getElementById('filterIdDesign');
    const filterNumeroOficioDesign = document.getElementById('filterNumeroOficioDesign');
    const filterTecnicoDesign = document.getElementById('filterTecnicoDesign');
    const filterTipoAsesoriaDesign = document.getElementById('filterTipoAsesoriaDesign');
    const filterFechaDesign = document.getElementById('filterFechaDesign');
    const tableRowsDesign = document.querySelectorAll('#designadosTable tbody tr');

    function applyDesignFilters() {
        const idValue = filterIdDesign?.value.toLowerCase() || '';
        const numeroValue = filterNumeroOficioDesign?.value.toLowerCase() || '';
        const tecnicoValue = filterTecnicoDesign?.value.toLowerCase() || '';
        const tipoValue = filterTipoAsesoriaDesign?.value.toLowerCase() || '';
        const fechaValue = filterFechaDesign?.value || '';

        const oficioGroups = {};
        tableRowsDesign.forEach(row => {
            const oficioId = row.dataset.oficioId;
            if (oficioId) {
                if (!oficioGroups[oficioId]) {
                    oficioGroups[oficioId] = [];
                }
                oficioGroups[oficioId].push(row);
            }
        });

        Object.values(oficioGroups).forEach(group => {
            const firstRow = group[0];
            const id = firstRow.dataset.id?.toLowerCase() || '';
            const numero = firstRow.dataset.numero?.toLowerCase() || '';
            const tecnicos = firstRow.dataset.tecnicos?.toLowerCase() || '';
            const tipos = firstRow.dataset.tipos?.toLowerCase() || '';
            const fecha = firstRow.dataset.fecha || '';

            const idMatch = !idValue || id.includes(idValue);
            const numeroMatch = !numeroValue || numero === numeroValue;
            const tecnicoMatch = !tecnicoValue || tecnicos.includes(tecnicoValue);
            const tipoMatch = !tipoValue || tipos.includes(tipoValue);
            const fechaMatch = !fechaValue || (fecha && new Date(fecha).toISOString().split('T')[0] === fechaValue);

            const shouldShow = idMatch && numeroMatch && tecnicoMatch && tipoMatch && fechaMatch;

            group.forEach(row => {
                row.style.display = shouldShow ? '' : 'none';
            });
        });

        console.log('Filtros de design aplicados:', { idValue, numeroValue, tecnicoValue, tipoValue, fechaValue });
    }

    if (filterIdDesign) filterIdDesign.addEventListener('input', applyDesignFilters);
    if (filterNumeroOficioDesign) filterNumeroOficioDesign.addEventListener('input', applyDesignFilters);
    if (filterTecnicoDesign) filterTecnicoDesign.addEventListener('change', applyDesignFilters);
    if (filterTipoAsesoriaDesign) filterTipoAsesoriaDesign.addEventListener('change', applyDesignFilters);
    if (filterFechaDesign) filterFechaDesign.addEventListener('change', applyDesignFilters);

    if (filterId || filterFecha || filterCanton || filterGad || filterNumeroOficio) {
        applyReceiveFilters();
    }
    if (filterIdDesign || filterNumeroOficioDesign || filterTecnicoDesign || filterTipoAsesoriaDesign || filterFechaDesign) {
        applyDesignFilters();
    }

    const currentSection = localStorage.getItem('currentSection');
    if (currentSection && document.getElementById(`section-${currentSection}`)) {
        showSection(currentSection);
    } else {
        showSection('oficios');
    }

    const currentPanel = localStorage.getItem('currentPanel');
    if (currentPanel && document.getElementById(`panel-${currentPanel}`)) {
        showPanel(currentPanel);
    } else if (document.getElementById('panel-pendientes') || document.getElementById('panel-asignados')) {
        showPanel('asignados');
    }

    fetchNotifications();
    setInterval(fetchNotifications, 10000);

    const clearNotificationsBtn = document.getElementById('clearNotifications');
    if (clearNotificationsBtn) {
        clearNotificationsBtn.addEventListener('click', clearNotifications);
    }

    document.getElementById('asignar_tecnico').addEventListener('change', function () {
        const tecnicoContainer = document.getElementById('tecnico_container');
        const tecnicoSelect = document.getElementById('tecnico');
        if (this.value === 'sí') {
            tecnicoContainer.style.display = 'block';
            tecnicoSelect.setAttribute('required', 'required');
        } else {
            tecnicoContainer.style.display = 'none';
            tecnicoSelect.removeAttribute('required');
            tecnicoSelect.value = '';
        }
    });

    document.getElementById('asignar_tecnico').addEventListener('change', function () {
        const tecnicoContainer = document.getElementById('tecnico_container');
        const tecnicoSelect = document.getElementById('tecnico');
        if (this.value === 'sí') {
            tecnicoContainer.style.display = 'block';
            tecnicoSelect.setAttribute('required', 'required');
        } else {
            tecnicoContainer.style.display = 'none';
            tecnicoSelect.removeAttribute('required');
            tecnicoSelect.value = '';
        }
    });

    document.getElementById('edit_asignar_tecnico').addEventListener('change', function () {
        const tecnicoContainer = document.getElementById('edit_tecnico_container');
        const tecnicoSelect = document.getElementById('edit_tecnico');
        if (this.value === 'sí') {
            tecnicoContainer.style.display = 'block';
            tecnicoSelect.setAttribute('required', 'required');
        } else {
            tecnicoContainer.style.display = 'none';
            tecnicoSelect.removeAttribute('required');
            tecnicoSelect.value = '';
        }
    });

    document.querySelectorAll('.edit-btn').forEach(button => {
        button.addEventListener('click', function () {
            const modal = document.getElementById('editModal');
            modal.querySelector('#edit_product_id').value = this.dataset.id;
            modal.querySelector('#edit_codigo').value = this.dataset.codigo;
            modal.querySelector('#edit_tipo').value = this.dataset.tipo;
            modal.querySelector('#edit_color').value = this.dataset.color;
            modal.querySelector('#edit_marca').value = this.dataset.marca;
            modal.querySelector('#edit_modelo').value = this.dataset.modelo;
            modal.querySelector('#edit_estado').value = this.dataset.estado;
            modal.querySelector('#edit_detalle').value = this.dataset.detalle;
            const asignarTecnico = this.dataset.tecnico ? 'sí' : 'no';
            modal.querySelector('#edit_asignar_tecnico').value = asignarTecnico;
            modal.querySelector('#edit_tecnico_container').style.display = asignarTecnico === 'sí' ? 'block' : 'none';
            modal.querySelector('#edit_tecnico').value = this.dataset.tecnico || '';
            modal.querySelector('#current_imagen').textContent = this.dataset.imagen || 'Sin imagen';
        });
    });

    document.getElementById('filterTecnico').addEventListener('change', filterTable);
    document.getElementById('filterTipo').addEventListener('change', filterTable);
    document.getElementById('filterSearch').addEventListener('input', filterTable);

    function filterTable() {
        const tecnicoFilter = document.getElementById('filterTecnico').value.toLowerCase();
        const tipoFilter = document.getElementById('filterTipo').value.toLowerCase();
        const searchFilter = document.getElementById('filterSearch').value.toLowerCase();
        const rows = document.querySelectorAll('#inventoryTable tbody tr');

        rows.forEach(row => {
            const tecnico = row.dataset.tecnico || '';
            const tipo = row.dataset.tipo;
            const search = row.dataset.search;
            const tecnicoMatch = !tecnicoFilter || tecnico === tecnicoFilter;
            const tipoMatch = !tipoFilter || tipo === tipoFilter;
            const searchMatch = !searchFilter || search.includes(searchFilter);
            row.style.display = tecnicoMatch && tipoMatch && searchMatch ? '' : 'none';
        });
    }


});



window.tecnicos = JSON.parse(document.getElementById('data-tecnicos')?.textContent || '[]');
window.tipos_asesoria = JSON.parse(document.getElementById('data-tipos-asesoria')?.textContent || '[]');
window.tecnicosData = window.tecnicos;
window.tiposAsesoriaData = window.tipos_asesoria;

function formatDateForInput(dateStr) {
    if (!dateStr) return '';
    const parts = dateStr.split('/');
    if (parts.length !== 3) return '';
    const day = parts[0].padStart(2, '0');
    const month = parts[1].padStart(2, '0');
    let year = parts[2];
    if (year.length === 2) {
        year = '20' + year;
    }
    if (isNaN(day) || isNaN(month) || isNaN(year) ||
        day < 1 || day > 31 || month < 1 || month > 12 || year < 1900) {
        return '';
    }
    return year + '-' + month + '-' + day;
}

function formatDateToTraditional(dateStr) {
    if (!dateStr) return '';
    const parts = dateStr.split('-');
    if (parts.length !== 3) return '';
    const year = parts[0].slice(-2);
    const month = parts[1].padStart(2, '0');
    const day = parts[2].padStart(2, '0');
    return day + '/' + month + '/' + year;
}

async function updateCanton() {
    const parroquia = document.getElementById('gad_parroquial')?.value;
    const cantonInput = document.getElementById('canton');
    if (parroquia && cantonInput) {
        try {
            const response = await fetch('/get_canton', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ parroquia })
            });
            if (!response.ok) throw new Error('Error en la petición: ' + response.status);
            const data = await response.json();
            cantonInput.value = data.canton || '';
            cantonInput.classList.remove('is-invalid');
        } catch (error) {
            console.error('Error in updateCanton:', error);
            cantonInput.value = '';
            cantonInput.classList.add('is-invalid');
        }
    } else {
        if (cantonInput) {
            cantonInput.value = '';
            cantonInput.classList.add('is-invalid');
        }
    }
}

async function updateCantonEdit() {
    const parroquia = document.getElementById('edit_gad_parroquial')?.value;
    const cantonInput = document.getElementById('edit_canton');
    if (parroquia && cantonInput) {
        try {
            const response = await fetch('/get_canton', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ parroquia })
            });
            if (!response.ok) throw new Error('Error fetching canton: ' + response.status);
            const data = await response.json();
            cantonInput.value = data.canton || '';
            cantonInput.classList.remove('is-invalid');
        } catch (error) {
            console.error('Error in updateCantonEdit:', error);
            cantonInput.value = '';
            cantonInput.classList.add('is-invalid');
        }
    } else {
        if (cantonInput) {
            cantonInput.value = '';
            cantonInput.classList.add('is-invalid');
        }
    }
}

async function fetchNotifications() {
    const notificationCount = document.getElementById('notificationCount');
    const notificationList = document.getElementById('notificationList');
    if (!notificationCount || !notificationList) return;
    
    try {
        const response = await fetch('/get_notifications', {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });
        if (!response.ok) throw new Error('Error fetching notifications: ' + response.status);
        const data = await response.json();

        notificationCount.textContent = data.count || 0;
        notificationList.innerHTML = '';
        if (data.count === 0 || !data.notifications.length) {
            notificationList.innerHTML = '<li class="dropdown-item text-muted">No hay notificaciones</li>';
        } else {
            data.notifications.forEach(function(notification) {
                const li = document.createElement('li');
                li.className = 'dropdown-item';
                li.innerHTML = '<strong>' + notification.message + '</strong><br><small>' + notification.timestamp + '</small>';
                notificationList.appendChild(li);
            });
        }
    } catch (error) {
        console.error('Error in fetchNotifications:', error);
        if (notificationList) {
            notificationList.innerHTML = '<li class="dropdown-item text-danger">Error al cargar notificaciones</li>';
        }
    }
}

async function clearNotifications() {
    try {
        const response = await fetch('/clear_notifications', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (data.success) {
            await fetchNotifications();
        }
    } catch (error) {
        console.error('Error in clearNotifications:', error);
    }
}

function handleFlashes() {
    const flashes = document.querySelectorAll('.alert');
    flashes.forEach(function(flash, index) {
        flash.style.top = (20 + (index * 80)) + 'px';
        flash.style.animation = 'fadeIn 0.5s ease-in-out';
        setTimeout(function() {
            flash.style.animation = 'fadeOut 0.5s ease-in-out';
            setTimeout(function() { flash.remove(); }, 500);
        }, 3500);
    });
}

function addTechnicianPair(container, selectedTechnician, selectedAdvisory) {
    selectedTechnician = selectedTechnician || '';
    selectedAdvisory = selectedAdvisory || '';
    
    if (!window.tecnicosData || !window.tiposAsesoriaData) {
        console.error('Datos de técnicos o asesorías no cargados');
        return;
    }

    const tecnicoOptions = window.tecnicosData.map(function(tecnico) {
        const selected = selectedTechnician === tecnico.username ? 'selected' : '';
        return '<option value="' + tecnico.username + '" ' + selected + '>' + tecnico.full_name + '</option>';
    }).join('');

    const tipoOptions = window.tiposAsesoriaData.map(function(tipo) {
        const selected = selectedAdvisory === tipo ? 'selected' : '';
        return '<option value="' + tipo + '" ' + selected + '>' + tipo + '</option>';
    }).join('');

    const pairDiv = document.createElement('div');
    pairDiv.className = 'tecnico-asesoria-pair mb-2';
    pairDiv.innerHTML = '<div class="row g-2 align-items-center">' +
        '<div class="col">' +
        '<select name="tecnico_asignado[]" class="form-select form-select-sm" required>' +
        '<option value="" disabled ' + (!selectedTechnician ? 'selected' : '') + '>Seleccione Técnico</option>' +
        tecnicoOptions +
        '</select>' +
        '</div>' +
        '<div class="col">' +
        '<select name="tipo_asesoria[]" class="form-select form-select-sm" required>' +
        '<option value="" disabled ' + (!selectedAdvisory ? 'selected' : '') + '>Tipo Asesoría</option>' +
        tipoOptions +
        '</select>' +
        '</div>' +
        '<div class="col-auto">' +
        '<button type="button" class="btn btn-sm btn-danger remove-pair">X</button>' +
        '</div>' +
        '</div>';

    container.appendChild(pairDiv);
    
    pairDiv.querySelector('.remove-pair').addEventListener('click', function() {
        if (container.querySelectorAll('.tecnico-asesoria-pair').length > 1) {
            pairDiv.remove();
        }
    });
}

function toggleEntregaFields(oficioId) {
    const entregaRecepcion = document.getElementById('entrega_recepcion_' + oficioId);
    if (entregaRecepcion) {
        const entregaFields = document.querySelectorAll('#entrega_fields_' + oficioId + ', #acta_entrega_field_' + oficioId);
        entregaFields.forEach(function(field) {
            field.style.display = entregaRecepcion.value === 'Aplica' ? 'block' : 'none';
        });
    }
}

function enableEdit(tipoId) {
    const input = document.getElementById('input-tipo-' + tipoId);
    const saveButton = document.getElementById('save-tipo-' + tipoId);
    if (input && saveButton) {
        input.readOnly = false;
        input.focus();
        saveButton.classList.remove('d-none');
    }
}

function showPanel(panelId) {
    document.querySelectorAll('.fade-panel').forEach(function(panel) {
        panel.classList.remove('active');
    });
    document.querySelectorAll('.nav-link').forEach(function(link) {
        link.classList.remove('active');
    });
    const panelElement = document.getElementById('panel-' + panelId);
    const tabElement = document.getElementById('tab-' + panelId);
    if (panelElement && tabElement) {
        panelElement.classList.add('active');
        tabElement.classList.add('active');
        localStorage.setItem('currentPanel', panelId);
    }
}

function showSection(sectionId) {
    document.querySelectorAll('.card-section').forEach(function(section) {
        section.classList.remove('active');
        section.classList.add('d-none');
    });
    const targetSection = document.getElementById('section-' + sectionId);
    if (targetSection) {
        targetSection.classList.remove('d-none');
        targetSection.classList.add('active');
        localStorage.setItem('currentSection', sectionId);
    }
}

function applyDesignFilters() {
    const filterField = document.getElementById('filterField');
    const filterValue = document.getElementById('filterValue');
    const filterDateValue = document.getElementById('filterDateValue');
    const tableRowsDesign = document.querySelectorAll('#designadosTable tbody tr');

    if (!filterField || !tableRowsDesign.length) return;

    const filterValueText = filterField.value === 'fecha' ?
        (filterDateValue ? filterDateValue.value : '') :
        (filterValue ? filterValue.value.toLowerCase() : '') || '';

    tableRowsDesign.forEach(function(row) {
        const id = (row.dataset.id || '').toLowerCase();
        const numero = (row.dataset.numero || '').toLowerCase();
        const tecnicos = (row.dataset.tecnicos || '').toLowerCase();
        const tipos = (row.dataset.tipos || '').toLowerCase();
        const fecha = row.dataset.fecha || '';

        let shouldShow = true;

        if (filterField.value && filterValueText) {
            switch (filterField.value) {
                case 'id':
                    shouldShow = id.includes(filterValueText);
                    break;
                case 'numero':
                    shouldShow = numero.includes(filterValueText);
                    break;
                case 'tecnico':
                    shouldShow = tecnicos.includes(filterValueText);
                    break;
                case 'tipo':
                    shouldShow = tipos.includes(filterValueText);
                    break;
                case 'fecha':
                    shouldShow = fecha === filterValueText;
                    break;
                default:
                    shouldShow = true;
            }
        }

        row.style.display = shouldShow ? '' : 'none';
    });
}

function toggleFilterInput() {
    const filterField = document.getElementById('filterField');
    const filterValue = document.getElementById('filterValue');
    const filterDateValue = document.getElementById('filterDateValue');
    if (!filterField || !filterValue || !filterDateValue) return;

    if (filterField.value === 'fecha') {
        filterValue.classList.add('d-none');
        filterDateValue.classList.remove('d-none');
    } else {
        filterValue.classList.remove('d-none');
        filterDateValue.classList.add('d-none');
        filterDateValue.value = '';
    }
}

function showConfirmModal() {
    const registerForm = document.getElementById('registerForm');
    if (!registerForm) return;
    
    if (!registerForm.checkValidity()) {
        registerForm.classList.add('was-validated');
        return;
    }

    const formData = new FormData(registerForm);
    const fechaEnviadoRaw = document.getElementById('fecha_enviado').value;
    const fechaEnviadoFormatted = formatDateToTraditional(fechaEnviadoRaw);
    
    document.getElementById('confirm_numero_oficio').textContent = formData.get('numero_oficio') || '';
    document.getElementById('confirm_fecha_enviado').textContent = fechaEnviadoFormatted;
    document.getElementById('confirm_gad_parroquial').textContent = formData.get('gad_parroquial') || '';
    document.getElementById('confirm_canton').textContent = formData.get('canton') || '';
    document.getElementById('confirm_detalle').textContent = formData.get('detalle') || 'Sin detalle';
    document.getElementById('confirm_archivo').textContent = document.getElementById('archivo').files[0]?.name || 'Ningún archivo seleccionado';

    const confirmModal = document.getElementById('confirmModal');
    const bootstrapModal = confirmModal._bootstrapModal || new bootstrap.Modal(confirmModal, {
        backdrop: 'static',
        keyboard: false
    });
    bootstrapModal.show();
}

function filterTable(tableId, fieldId, valueId) {
    const fieldElement = document.getElementById(fieldId);
    const valueElement = document.getElementById(valueId);
    const table = document.getElementById(tableId);
    if (!fieldElement || !valueElement || !table) return;
    
    const field = fieldElement.value;
    const value = valueElement.value.toLowerCase();
    const rows = table.querySelectorAll('tbody tr');

    rows.forEach(function(row) {
        const cellValue = (row.getAttribute('data-' + field) || '').toLowerCase();
        row.style.display = cellValue.includes(value) ? '' : 'none';
    });
}

function showInforme(oficioId, numeroOficio, parroquia, canton) {
    fetch('/get_oficio_informe/' + oficioId)
        .then(function(response) { return response.json(); })
        .then(function(data) {
            if (!data.success || !data.assignments) {
                document.getElementById('informeContent').innerHTML = '<p class="text-muted">No hay información disponible.</p>';
                return;
            }

            let content = '<div class="mb-3"><h6><strong>Oficio:</strong> ' + numeroOficio + '</h6><p><strong>Parroquia:</strong> ' + parroquia + ' - <strong>Cantón:</strong> ' + canton + '</p></div><hr>';

            data.assignments.forEach(function(assignment, index) {
                const badgeClass = assignment.sub_estado === 'Concluido' ? 'bg-success' : assignment.sub_estado === 'En proceso' ? 'bg-warning' : 'bg-danger';
                
                content += '<div class="mb-4">';
                content += '<h6 class="text-primary">Técnico: ' + assignment.tecnico_name + '</h6>';
                content += '<div class="row">';
                content += '<div class="col-md-6">';
                content += '<p><strong>Tipo Asesoría:</strong> ' + (assignment.tipo_asesoria || 'N/A') + '</p>';
                content += '<p><strong>Estado:</strong> <span class="badge ' + badgeClass + '">' + (assignment.sub_estado || 'Asignado') + '</span></p>';
                content += '<p><strong>Fecha Asesoría:</strong> ' + (assignment.fecha_asesoria_formatted || 'N/A') + '</p>';
                content += '</div>';
                content += '<div class="col-md-6">';
                content += '<p><strong>Entrega Recepción:</strong> ' + (assignment.entrega_recepcion || 'No Aplica') + '</p>';
                if (assignment.entrega_recepcion === 'Aplica') {
                    content += '<p><strong>Oficio Delegación:</strong> ' + (assignment.oficio_delegacion || 'N/A') + '</p>';
                    content += '<p><strong>Acta Entrega:</strong> ' + (assignment.acta_entrega || 'N/A') + '</p>';
                }
                content += '<p><strong>Anexo:</strong> ' + (assignment.anexo_nombre ? 'Sí' : 'No') + '</p>';
                content += '</div>';
                content += '</div>';
                content += '<div class="mt-2">';
                content += '<p><strong>Desarrollo de Actividad:</strong></p>';
                content += '<div class="bg-light p-2 rounded">' + (assignment.desarrollo_actividad || 'Sin descripción') + '</div>';
                content += '</div>';
                if (index < data.assignments.length - 1) {
                    content += '<hr>';
                }
                content += '</div>';
            });

            document.getElementById('informeContent').innerHTML = content;
        })
        .catch(function(error) {
            console.error('Error in showInforme:', error);
            document.getElementById('informeContent').innerHTML = '<p class="text-muted">Error al cargar la información.</p>';
        });
}

document.addEventListener('DOMContentLoaded', function () {
    const staticModals = ['#designModal', '#editModal', '#confirmModal', '#changePasswordModal', '#inactivityModal', '#previewModal'];
    staticModals.forEach(function(selector) {
        const modal = document.querySelector(selector);
        if (modal && !modal._bootstrapModal) {
            try {
                modal._bootstrapModal = new bootstrap.Modal(modal, {
                    backdrop: 'static',
                    keyboard: false
                });
            } catch (error) {
                console.error('Error initializing modal ' + selector + ':', error);
            }
        }
    });

    let inactivityTimeout;
    let warningTimeout;
    const inactivityTime = 15 * 60 * 1000;
    const warningTime = 14 * 60 * 1000;

    function resetInactivityTimer() {
        clearTimeout(inactivityTimeout);
        clearTimeout(warningTimeout);
        warningTimeout = setTimeout(showWarning, warningTime);
        inactivityTimeout = setTimeout(logoutUser, inactivityTime);
    }

    function showWarning() {
        try {
            const modal = document.getElementById('inactivityModal');
            const bootstrapModal = modal._bootstrapModal || new bootstrap.Modal(modal, {
                backdrop: 'static',
                keyboard: false
            });
            const startTime = Date.now();
            const countdownElement = document.getElementById('countdown');
            countdownElement.textContent = '60 segundos';

            const countdownInterval = setInterval(function() {
                const elapsed = Date.now() - startTime;
                const remaining = 60 - Math.floor(elapsed / 1000);
                countdownElement.textContent = remaining + ' segundos';
                if (remaining <= 0) {
                    clearInterval(countdownInterval);
                    bootstrapModal.hide();
                    logoutUser();
                }
            }, 1000);

            document.getElementById('continueSession').addEventListener('click', function() {
                clearInterval(countdownInterval);
                bootstrapModal.hide();
                resetInactivityTimer();
            });

            bootstrapModal.show();
        } catch (error) {
            console.error('Error showing inactivity modal:', error);
        }
    }

    async function logoutUser() {
        try {
            const response = await fetch('/logout', {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include'
            });
            if (response.ok) {
                window.location.href = '/login';
            }
        } catch (error) {
            console.error('Error in logoutUser:', error);
            window.location.href = '/login';
        }
    }

    ['click', 'mousemove', 'keypress', 'scroll', 'touchstart'].forEach(function(event) {
        document.addEventListener(event, resetInactivityTimer, true);
    });
    resetInactivityTimer();
    handleFlashes();

    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', function(e) {
            e.preventDefault();
            showConfirmModal();
        });
    }
    
    const confirmSubmit = document.getElementById('confirmSubmit');
    if (confirmSubmit) {
        confirmSubmit.addEventListener('click', function() {
            const form = document.getElementById('registerForm');
            const confirmModal = document.getElementById('confirmModal');
            const bootstrapModal = confirmModal._bootstrapModal || new bootstrap.Modal(confirmModal);
            bootstrapModal.hide();
            form.submit();
        });
    }

    document.querySelectorAll('.edit-btn').forEach(function(button) {
        button.addEventListener('click', function () {
            const id = this.getAttribute('data-id');
            const fechaEnviadoTraditional = this.getAttribute('data-fecha-enviado');
            const fechaEnviadoForInput = formatDateForInput(fechaEnviadoTraditional);
            const numeroOficio = this.getAttribute('data-numero-oficio');
            const gadParroquial = this.getAttribute('data-gad-parroquial');
            const canton = this.getAttribute('data-canton');
            const detalle = this.getAttribute('data-detalle') || '';
            let assignments;
            try {
                assignments = JSON.parse(this.getAttribute('data-assignments') || '[]');
            } catch (e) {
                console.error('Error parsing assignments:', e);
                assignments = [];
            }

            const editModal = document.getElementById('editModal');
            if (editModal) {
                editModal.querySelector('#edit_oficio_id').value = id;
                editModal.querySelector('#edit_fecha_enviado').value = fechaEnviadoForInput;
                editModal.querySelector('#edit_numero_oficio').value = numeroOficio || '';
                editModal.querySelector('#edit_gad_parroquial').value = gadParroquial || '';
                editModal.querySelector('#edit_canton').value = canton || '';
                editModal.querySelector('#edit_detalle').value = detalle;

                updateCantonEdit();
            }
        });
    });

    document.addEventListener('click', function (e) {
        if (e.target.classList.contains('remove-pair')) {
            const pair = e.target.closest('.tecnico-asesoria-pair');
            if (pair && pair.parentElement.querySelectorAll('.tecnico-asesoria-pair').length > 1) {
                pair.remove();
            } else {
                const tecnicoSelect = pair.querySelector('select[name="tecnico_asignado[]"]');
                const tipoSelect = pair.querySelector('select[name="tipo_asesoria[]"]');
                if (tecnicoSelect) tecnicoSelect.selectedIndex = 0;
                if (tipoSelect) tipoSelect.selectedIndex = 0;
            }
        }
    });

    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (form.id === 'designForm' || form.querySelector('button[name="designar"]') || form.querySelector('button[name="edit_oficio"]')) {
            const tecnicos = form.querySelectorAll('select[name="tecnico_asignado[]"]');
            const tipos = form.querySelectorAll('select[name="tipo_asesoria[]"]');

            let hasValidPair = false;
            for (let i = 0; i < tecnicos.length; i++) {
                if (tecnicos[i].value && tipos[i] && tipos[i].value) {
                    hasValidPair = true;
                    break;
                }
            }

            if (!hasValidPair) {
                e.preventDefault();
                alert('Debe seleccionar al menos un técnico y tipo de asesoría válidos.');
                return false;
            }
        }
    });

    document.querySelectorAll('.preview-btn').forEach(function(button) {
        button.addEventListener('click', function () {
            const id = this.getAttribute('data-id');
            const archivoNombre = this.getAttribute('data-archivo-nombre');
            const previewFrame = document.getElementById('previewFrame');
            const previewError = document.getElementById('previewError');
            if (previewFrame && previewError) {
                previewFrame.src = '';
                previewError.classList.add('d-none');
                if (archivoNombre && archivoNombre.toLowerCase().endsWith('.pdf')) {
                    previewFrame.src = '/preview/' + id;
                } else {
                    previewError.classList.remove('d-none');
                }
            }
        });
    });

    const filterField = document.getElementById('filterField');
    const filterValue = document.getElementById('filterValue');
    const filterDateValue = document.getElementById('filterDateValue');
    if (filterField && (filterValue || filterDateValue)) {
        filterField.addEventListener('change', function() {
            toggleFilterInput();
            applyDesignFilters();
        });
        if (filterValue) filterValue.addEventListener('input', applyDesignFilters);
        if (filterDateValue) filterDateValue.addEventListener('change', applyDesignFilters);
    }

    const filterValueHistorial = document.getElementById('filterValueHistorial');
    if (filterValueHistorial) {
        filterValueHistorial.addEventListener('input', function() {
            filterTable('historial-registros', 'filterFieldHistorial', 'filterValueHistorial');
        });
    }

    const filterValueSeguimiento = document.getElementById('filterValueSeguimiento');
    if (filterValueSeguimiento) {
        filterValueSeguimiento.addEventListener('input', function() {
            filterTable('seguimiento-registros', 'filterFieldSeguimiento', 'filterValueSeguimiento');
        });
    }

    fetchNotifications();
    setInterval(fetchNotifications, 10000);

    const clearNotificationsBtn = document.getElementById('clearNotifications');
    if (clearNotificationsBtn) {
        clearNotificationsBtn.addEventListener('click', clearNotifications);
    }

    const currentPanel = localStorage.getItem('currentPanel');
    if (currentPanel && document.getElementById('panel-' + currentPanel)) {
        showPanel(currentPanel);
    } else {
        showPanel('registrar');
    }

    window.showPanel = showPanel;
    window.showSection = showSection;
    window.updateCanton = updateCanton;
    window.updateCantonEdit = updateCantonEdit;
    window.toggleEntregaFields = toggleEntregaFields;
    window.enableEdit = enableEdit;
    window.addTechnicianPair = addTechnicianPair;
    window.logoutUser = logoutUser;
    window.showInforme = showInforme;
    window.showConfirmModal = showConfirmModal;
    window.filterTable = filterTable;
    window.handleFlashes = handleFlashes;
});
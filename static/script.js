async function updateCanton() {
    const parroquia = document.getElementById('gad_parroquial')?.value;
    if (parroquia) {
        const response = await fetch('/get_canton', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ parroquia })
        });
        const data = await response.json();
        document.getElementById('canton').value = data.canton;
    } else {
        document.getElementById('canton').value = '';
    }
}

async function updateCantonEdit() {
    const parroquia = document.getElementById('edit_gad_parroquial')?.value;
    if (parroquia) {
        const response = await fetch('/get_canton', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ parroquia })
        });
        const data = await response.json();
        document.getElementById('edit_canton').value = data.canton;
    } else {
        document.getElementById('edit_canton').value = '';
    }
}

function addTechnicianPair(container, tecnicos, tipos, selectedTechnician = '', selectedAdvisory = '') {
    const pairDiv = document.createElement('div');
    pairDiv.className = 'tecnico-asesoria-pair mb-2';
    pairDiv.innerHTML = `
        <div class="row g-2 align-items-center">
            <div class="col">
                <select name="tecnico_asignado[]" class="form-select form-select-sm" required>
                    <option value="" disabled ${!selectedTechnician ? 'selected' : ''}>Seleccione Técnico</option>
                    ${tecnicos.map(tecnico => `<option value="${tecnico}" ${selectedTechnician === tecnico ? 'selected' : ''}>${tecnico}</option>`).join('')}
                </select>
            </div>
            <div class="col">
                <select name="tipo_asesoria[]" class="form-select form-select-sm" required>
                    <option value="" disabled ${!selectedAdvisory ? 'selected' : ''}>Tipo Asesoría</option>
                    ${tipos.map(tipo => `<option value="${tipo}" ${selectedAdvisory === tipo ? 'selected' : ''}>${tipo}</option>`).join('')}
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

document.addEventListener('DOMContentLoaded', () => {
    const flashes = document.querySelectorAll('.alert');
    flashes.forEach((flash, index) => {
        flash.style.top = `${20 + (index * 80)}px`;
        setTimeout(() => {
            flash.style.animation = 'fadeOut 0.5s ease-in-out';
            setTimeout(() => flash.remove(), 500);
        }, 3000);
    });

    const editModal = document.getElementById('editModal');
    if (editModal) {
        editModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const id = button.getAttribute('data-id');
            const fechaEnviado = button.getAttribute('data-fecha-enviado');
            const numeroOficio = button.getAttribute('data-numero-oficio');
            const gadParroquial = button.getAttribute('data-gad-parroquial');
            const canton = button.getAttribute('data-canton');
            const detalle = button.getAttribute('data-detalle');
            const assignments = JSON.parse(button.getAttribute('data-assignments') || '[]');

            document.getElementById('edit_oficio_id').value = id;
            document.getElementById('edit_fecha_enviado').value = fechaEnviado ? fechaEnviado.split('T')[0] : '';
            document.getElementById('edit_numero_oficio').value = numeroOficio || '';
            document.getElementById('edit_gad_parroquial').value = gadParroquial || '';
            document.getElementById('edit_canton').value = canton || '';
            document.getElementById('edit_detalle').value = detalle || '';

            const container = document.getElementById('edit_tecnico_asesoria_pairs');
            container.innerHTML = '';
            const tecnicos = Array.from(document.querySelector('select[name="tecnico_asignado[]"]')?.options || [])
                .map(opt => opt.value)
                .filter(val => val);
            const tipos = Array.from(document.querySelector('select[name="tipo_asesoria[]"]')?.options || [])
                .map(opt => opt.value)
                .filter(val => val);
            if (assignments.length > 0) {
                assignments.forEach(assignment => {
                    addTechnicianPair(container, tecnicos, tipos, assignment.tecnico, assignment.tipo_asesoria);
                });
            } else {
                addTechnicianPair(container, tecnicos, tipos);
            }

            updateCantonEdit();
        });

        const addPairButton = editModal.querySelector('.add-pair');
        addPairButton.addEventListener('click', () => {
            const container = document.getElementById('edit_tecnico_asesoria_pairs');
            const tecnicos = Array.from(document.querySelector('select[name="tecnico_asignado[]"]')?.options || [])
                .map(opt => opt.value)
                .filter(val => val);
            const tipos = Array.from(document.querySelector('select[name="tipo_asesoria[]"]')?.options || [])
                .map(opt => opt.value)
                .filter(val => val);
            addTechnicianPair(container, tecnicos, tipos);
        });
    }

    document.querySelectorAll('.add-pair').forEach(button => {
        button.addEventListener('click', () => {
            const oficioId = button.getAttribute('data-oficio-id');
            const container = document.getElementById(`tecnico-asesoria-pairs-${oficioId}`);
            const tecnicos = Array.from(document.querySelector('select[name="tecnico_asignado[]"]')?.options || [])
                .map(opt => opt.value)
                .filter(val => val);
            const tipos = Array.from(document.querySelector('select[name="tipo_asesoria[]"]')?.options || [])
                .map(opt => opt.value)
                .filter(val => val);
            addTechnicianPair(container, tecnicos, tipos);
        });
    });

    const posiblesPaneles = ['pendientes', 'designados', 'usuarios'];
    for (const panel of posiblesPaneles) {
        if (document.getElementById(`panel-${panel}`)) {
            showPanel(panel);
            break;
        }
    }
});

function showPanel(panelId) {
    document.querySelectorAll('.fade-panel').forEach(panel => panel.classList.remove('active'));
    document.querySelectorAll('.nav-link').forEach(link => link.classList.remove('active'));
    const panelElement = document.getElementById(`panel-${panelId}`);
    const tabElement = document.getElementById(`tab-${panelId}`);
    if (panelElement && tabElement) {
        panelElement.classList.add('active');
        tabElement.classList.add('active');
    }
}

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
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('add-pair')) {
        const oficioId = e.target.getAttribute('data-oficio-id');
        const container = document.getElementById('tecnico-asesoria-pairs-' + oficioId);
        if (container) {
            const pairDiv = document.createElement('div');
            pairDiv.className = 'tecnico-asesoria-pair mb-2';
            pairDiv.innerHTML = `
                <div class="row g-2 align-items-center">
                    <div class="col">
                        <select class="form-select form-select-sm" name="tecnico_asignado[]" required>
                            <option value="" disabled selected>Seleccione Técnico</option>
                            ${tecnicos.map(tecnico => `<option value="${tecnico}">${tecnico}</option>`).join('')}
                        </select>
                    </div>
                    <div class="col">
                        <select class="form-select form-select-sm" name="tipo_asesoria[]" required>
                            <option value="" disabled selected>Tipo Asesoría</option>
                            ${tipos.map(tipo => `<option value="${tipo}">${tipo}</option>`).join('')}
                        </select>
                    </div>
                    <div class="col-auto">
                        <button type="button" class="btn btn-sm btn-danger remove-pair">X</button>
                    </div>
                </div>
            `;
            container.appendChild(pairDiv);
        }
    }
    if (e.target.classList.contains('remove-pair')) {
        const pairDiv = e.target.closest('.tecnico-asesoria-pair');
        if (pairDiv) pairDiv.remove();
    }
});

function showSection(section) {
            document.getElementById('section-oficios').classList.add('d-none');
            document.getElementById('section-usuarios').classList.add('d-none');
            document.getElementById('section-parroquias').classList.add('d-none');
            document.getElementById('section-' + section).classList.remove('d-none');
            document.querySelectorAll('.sidebar .nav-link').forEach(link => link.classList.remove('active'));
            if (section === 'oficios') {
                document.querySelector('.sidebar .nav-link[href="#"]').classList.add('active');
            } else if (section === 'usuarios') {
                document.querySelectorAll('.sidebar .nav-link')[1].classList.add('active');
            } else if (section === 'parroquias') {
                document.querySelectorAll('.sidebar .nav-link')[2].classList.add('active');
            }
        }
        showSection('oficios');
function showSection(section) {
    document.querySelectorAll('.card-section').forEach(function(card) {
        card.classList.add('d-none');
        card.classList.remove('active');
    });
    var target = document.getElementById('section-' + section);
    if (target) {
        target.classList.remove('d-none');
        target.classList.add('active');
    }
    document.querySelectorAll('.nav-link').forEach(function(link) {
        link.classList.remove('active');
    });
    document.querySelectorAll('.nav-link').forEach(function(link) {
        if (link.getAttribute('onclick') && link.getAttribute('onclick').includes(section)) {
            link.classList.add('active');
        }
    });
}
function actualizarNotificaciones() {
    fetch('{{ url_for("notificaciones_count") }}')
        .then(response => response.json())
        .then(data => {
            document.getElementById('notificationCount').textContent = data.count;
        });
}

actualizarNotificaciones();
document.querySelectorAll('form.tecnico-form').forEach(form => {
    form.addEventListener('submit', function() {
        setTimeout(actualizarNotificaciones, 1000);
    });
});

function enableEdit(id) {
    document.getElementById('input-tipo-' + id).removeAttribute('readonly');
    document.getElementById('input-tipo-' + id).focus();
    document.getElementById('save-tipo-' + id).classList.remove('d-none');
}
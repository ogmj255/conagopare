function updateCanton() {
    const parroquia = document.getElementById('gad_parroquial').value;
    if (parroquia) {
        fetch('/get_canton', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ parroquia: parroquia })
        })
        .then(response => response.json())
        .then(data => {
            document.getElementById('canton').value = data.canton;
        })
        .catch(error => console.error('Error:', error));
    } else {
        document.getElementById('canton').value = '';
    }
}

function updateCantonEdit() {
    const parroquia = document.getElementById('edit_gad_parroquial').value;
    if (parroquia) {
        fetch('/get_canton', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ parroquia: parroquia })
        })
        .then(response => response.json())
        .then(data => {
            document.getElementById('edit_canton').value = data.canton;
        })
        .catch(error => console.error('Error:', error));
    } else {
        document.getElementById('edit_canton').value = '';
    }
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
            const tecnicoAsignado = button.getAttribute('data-tecnico-asignado') || '';
            const tipoAsesoria = button.getAttribute('data-tipo-asesoria') || '';

            document.getElementById('edit_oficio_id').value = id;
            document.getElementById('edit_fecha_enviado').value = fechaEnviado ? fechaEnviado.split('T')[0] : '';
            document.getElementById('edit_numero_oficio').value = numeroOficio;
            document.getElementById('edit_gad_parroquial').value = gadParroquial;
            document.getElementById('edit_canton').value = canton;
            document.getElementById('edit_detalle').value = detalle;
            document.getElementById('edit_tecnico_asignado').value = tecnicoAsignado;
            document.getElementById('edit_tipo_asesoria').value = tipoAsesoria;

            updateCantonEdit();
        });
    }

    showPanel('registro');
    showPanel('pendientes');
    showPanel('asignados');
    showPanel('oficios');
});

function showPanel(panel) {
    const panels = document.querySelectorAll('.fade-panel');
    const tabs = document.querySelectorAll('.nav-link');
    
    panels.forEach(p => p.classList.remove('active'));
    tabs.forEach(t => t.classList.remove('active'));
    
    const panelElement = document.getElementById(`panel-${panel}`);
    const tabElement = document.getElementById(`tab-${panel}`);
    
    if (panelElement && tabElement) {
        panelElement.classList.add('active');
        tabElement.classList.add('active');
    }
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
            const tecnicoAsignado = button.getAttribute('data-tecnico-asignado') || '';
            const tipoAsesoria = button.getAttribute('data-tipo-asesoria') || '';

            document.getElementById('edit_oficio_id').value = id;
            document.getElementById('edit_fecha_enviado').value = fechaEnviado ? fechaEnviado.split('T')[0] : '';
            document.getElementById('edit_numero_oficio').value = numeroOficio;
            document.getElementById('edit_gad_parroquial').value = gadParroquial;
            document.getElementById('edit_canton').value = canton;
            document.getElementById('edit_detalle').value = detalle;
            document.getElementById('edit_tecnico_asignado').value = tecnicoAsignado;
            document.getElementById('edit_tipo_asesoria').value = tipoAsesoria;

            updateCantonEdit();
        });
    }

    const posiblesPaneles = ['registro', 'pendientes', 'asignados', 'oficios', 'historial', 'usuarios'];
    for (const panel of posiblesPaneles) {
        if (document.getElementById(`panel-${panel}`)) {
            showPanel(panel);
            break;
        }
    }
});

function showPanel(panelId) {
    document.querySelectorAll('.fade-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    document.getElementById(`panel-${panelId}`).classList.add('active');
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    document.getElementById(`tab-${panelId}`).classList.add('active');
}

async function updateCanton() {
    const parroquia = document.getElementById('gad_parroquial').value;
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
    const parroquia = document.getElementById('edit_gad_parroquial').value;
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

document.querySelectorAll('.edit-btn').forEach(button => {
    button.addEventListener('click', function() {
        const modal = document.getElementById('editModal');
        modal.querySelector('#edit_oficio_id').value = this.dataset.id;
        modal.querySelector('#edit_fecha_enviado').value = this.dataset.fechaEnviado || '';
        modal.querySelector('#edit_numero_oficio').value = this.dataset.numeroOficio || '';
        modal.querySelector('#edit_gad_parroquial').value = this.dataset.gadParroquial || '';
        modal.querySelector('#edit_canton').value = this.dataset.canton || '';
        modal.querySelector('#edit_detalle').value = this.dataset.detalle || '';
        modal.querySelector('#edit_tecnico_asignado').value = this.dataset.tecnicoAsignado || 'Ninguno';
        modal.querySelector('#edit_tipo_asesoria').value = this.dataset.tipoAsesoria || 'Ninguno';
        updateCantonEdit();
    });
});

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

document.querySelectorAll('.edit-btn').forEach(button => {
    button.addEventListener('click', function() {
        const modal = document.getElementById('editModal');
        modal.querySelector('#edit_oficio_id').value = this.dataset.id;
        // Seleccionar técnicos asignados
        const tecnicosAsignados = JSON.parse(this.dataset.tecnicoAsignado || '[]');
        const select = modal.querySelector('#edit_tecnico_asignado');
        Array.from(select.options).forEach(option => {
            option.selected = tecnicosAsignados.includes(option.value);
        });
        // Seleccionar tipo de asesoría
        modal.querySelector('#edit_tipo_asesoria').value = this.dataset.tipoAsesoria || 'Ninguno';
    });
});
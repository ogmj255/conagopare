#!/usr/bin/env python3
"""
Versión local de la aplicación que funciona sin MongoDB
Solo para desarrollo y pruebas
"""
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os
import bcrypt
from html import escape

app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv('SECRET_KEY', 'a1eb8b7d4c7a96ea202923296486a51c')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
app.permanent_session_lifetime = timedelta(minutes=15)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Datos de prueba en memoria
USERS_DATA = {
    'admin': {
        'username': 'admin',
        'password': bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()),
        'role': 'admin',
        'nombre': 'Administrador',
        'apellido': 'Sistema'
    },
    'designer': {
        'username': 'designer',
        'password': bcrypt.hashpw('designer123'.encode('utf-8'), bcrypt.gensalt()),
        'role': 'designer',
        'nombre': 'Diseñador',
        'apellido': 'Prueba'
    },
    'tecnico1': {
        'username': 'tecnico1',
        'password': bcrypt.hashpw('tecnico123'.encode('utf-8'), bcrypt.gensalt()),
        'role': 'tecnico',
        'nombre': 'Técnico',
        'apellido': 'Uno'
    }
}

PARROQUIAS_DATA = [
    {'parroquia': 'Parroquia 1', 'canton': 'Cantón 1'},
    {'parroquia': 'Parroquia 2', 'canton': 'Cantón 2'},
    {'parroquia': 'Parroquia 3', 'canton': 'Cantón 3'}
]

TIPOS_ASESORIA = ['Asesoría Técnica', 'Inspección', 'Consultoría', 'Capacitación']

OFICIOS_DATA = []

class User(UserMixin):
    def __init__(self, username, role, id=None):
        self.id = username
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(username):
    user_data = USERS_DATA.get(username)
    if user_data:
        return User(username=user_data['username'], role=user_data['role'])
    return None

def get_tipos_asesoria():
    return TIPOS_ASESORIA

@app.route('/')
def index():
    if current_user.is_authenticated:
        role_to_endpoint = {
            'admin': 'admin',
            'tecnico': 'tecnico',
            'receiver': 'receive',
            'designer': 'design',
            'sistemas': 'sistemas'
        }
        endpoint = role_to_endpoint.get(current_user.role, 'design')
        return redirect(url_for(endpoint))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = escape(request.form['username'])
        password = request.form['password'].encode('utf-8')
        user_data = USERS_DATA.get(username)
        if user_data and bcrypt.checkpw(password, user_data['password']):
            user_obj = User(username=user_data['username'], role=user_data['role'])
            login_user(user_obj)
            session['full_name'] = f"{user_data.get('nombre', '')} {user_data.get('apellido', '')}".strip() or username
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('Has cerrado sesión exitosamente.', 'success')
    return redirect(url_for('login'))

@app.route('/get_canton', methods=['POST'])
def get_canton():
    try:
        data = request.get_json()
        parroquia = escape(data.get('parroquia', ''))
        if parroquia:
            for p in PARROQUIAS_DATA:
                if p['parroquia'] == parroquia:
                    return jsonify({'canton': p['canton']})
        return jsonify({'canton': ''})
    except Exception as e:
        return jsonify({'canton': '', 'error': str(e)})

@app.route('/design', methods=['GET', 'POST'])
@login_required
def design():
    if current_user.role not in ['designer', 'admin']:
        return redirect(url_for('login'))
    
    # Datos de prueba
    pendientes = [
        {
            '_id': '1',
            'id_secuencial': '2024-0001',
            'numero_oficio': 'OF-001-2024',
            'fecha_enviado_traditional': '15/01/24',
            'gad_parroquial': 'Parroquia 1',
            'canton': 'Cantón 1',
            'detalle': 'Solicitud de asesoría técnica',
            'archivo_nombre': 'documento.pdf'
        }
    ]
    
    designados = [
        {
            '_id': '2',
            'id_secuencial': '2024-0002',
            'numero_oficio': 'OF-002-2024',
            'fecha_enviado_traditional': '16/01/24',
            'gad_parroquial': 'Parroquia 2',
            'canton': 'Cantón 2',
            'detalle': 'Solicitud de inspección',
            'fecha_designacion_formatted': '17/01/24',
            'assignments': [
                {
                    'tecnico': 'tecnico1',
                    'tipo_asesoria': 'Inspección',
                    'sub_estado': 'Asignado'
                }
            ]
        }
    ]
    
    completados = []
    
    tecnicos = [
        {
            'username': 'tecnico1',
            'full_name': 'Técnico Uno'
        }
    ]
    
    if request.method == 'POST':
        if 'designar' in request.form:
            flash('Funcionalidad de designación disponible solo con MongoDB.', 'info')
        elif 'edit_oficio' in request.form:
            flash('Funcionalidad de edición disponible solo con MongoDB.', 'info')
    
    return render_template('design.html',
                           pendientes=pendientes,
                           designados=designados,
                           completados=completados,
                           tecnicos=tecnicos,
                           tipos_asesoria=get_tipos_asesoria(),
                           parroquias=PARROQUIAS_DATA,
                           users=tecnicos)

@app.route('/get_notifications')
def get_notifications():
    return jsonify({'notifications': [], 'count': 0})

@app.route('/clear_notifications', methods=['POST'])
def clear_notifications():
    return jsonify({'success': True})

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    flash('Funcionalidad disponible solo con MongoDB.', 'info')
    return redirect(url_for('index'))

# Rutas adicionales básicas
@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    flash('Panel de administración disponible solo con MongoDB.', 'info')
    return redirect(url_for('design'))

@app.route('/tecnico')
@login_required
def tecnico():
    if current_user.role not in ['tecnico', 'admin']:
        return redirect(url_for('login'))
    flash('Panel de técnico disponible solo con MongoDB.', 'info')
    return redirect(url_for('design'))

@app.route('/receive')
@login_required
def receive():
    if current_user.role not in ['receiver', 'admin']:
        return redirect(url_for('login'))
    flash('Panel de recepción disponible solo con MongoDB.', 'info')
    return redirect(url_for('design'))

@app.route('/sistemas')
@login_required
def sistemas():
    if current_user.role not in ['admin', 'sistemas']:
        return redirect(url_for('login'))
    flash('Panel de sistemas disponible solo con MongoDB.', 'info')
    return redirect(url_for('design'))

if __name__ == '__main__':
    print("=== APLICACIÓN EN MODO LOCAL ===")
    print("Usuarios de prueba:")
    print("- admin / admin123 (Administrador)")
    print("- designer / designer123 (Diseñador)")
    print("- tecnico1 / tecnico123 (Técnico)")
    print("================================")
    app.run(host='0.0.0.0', port=5000, debug=True)
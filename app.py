from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_file, make_response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
from werkzeug.routing import BuildError
from dotenv import load_dotenv
import re
import os
import bcrypt
from io import BytesIO
from gridfs import GridFS
from html import escape
import json
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import threading

app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv('SECRET_KEY', 'a1eb8b7d4c7a96ea202923296486a51c')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
app.permanent_session_lifetime = timedelta(minutes=10)
app.config['SESSION_PERMANENT'] = True

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

mongo_uri = os.getenv('MONGODB_URI', 'mongodb+srv://ogmoscosoj:KcB4gSO579gBCSzY@conagoparedb.vwmlbqg.mongodb.net/?retryWrites=true&w=majority&appName=conagoparedb')
local_uri = os.getenv('MONGODB_LOCAL_URI', 'mongodb://localhost:27017/')

try:
    print("Intentando conectar a MongoDB...")
    client = MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        socketTimeoutMS=10000,
        maxPoolSize=5,
        retryWrites=True
    )
    client.admin.command('ping')
    print("Conectado exitosamente a MongoDB Atlas")
except Exception as e:
    print(f"Error conectando a MongoDB Atlas: {e}")
    print("Intentando conexión local...")
    try:
        client = MongoClient(local_uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        print("Conectado exitosamente a MongoDB local")
    except Exception as local_e:
        print(f"Error conectando a MongoDB local: {local_e}")
        print("\n=== SOLUCIÓN ===\n")
        print("1. Verifique su conexión a internet")
        print("2. O instale MongoDB localmente: https://www.mongodb.com/try/download/community")
        print("3. O configure la variable MONGODB_URI en el archivo .env")
        exit(1)

db_oficios = client['conagoparedb']
oficios = db_oficios['oficios']
parroquias = db_oficios['parroquias']
users = db_oficios['users_db']
notifications = db_oficios['notifications']
tipos_asesoria_coll = db_oficios['tipos_asesoria']
logs = db_oficios['logs']
errors = db_oficios['errors']
active_sessions = db_oficios['active_sessions']
fs = GridFS(db_oficios)

class User(UserMixin):
    def __init__(self, username, role, id=None):
        self.id = username
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(username):
    user_data = users.find_one({'username': username})
    if user_data:
        return User(username=user_data['username'], role=user_data['role'])
    return None

try:
    client.admin.command('ping')
    print("Conexión a MongoDB verificada exitosamente")
except Exception as e:
    print(f"Error de verificación de MongoDB: {e}")
    exit(1)

try:
    oficios.create_index([('id_secuencial', 1)], unique=True)
    print("Índice único creado para id_secuencial.")
except Exception as e:
    print(f"Error al crear índice: {e}")

try:
    active_sessions.create_index([('username', 1), ('session_id', 1)], unique=True)
    active_sessions.create_index([('last_activity', 1)], expireAfterSeconds=3600)
    oficios.create_index([('estado', 1)])
    oficios.create_index([('fecha_recibido', -1)])
    users.create_index([('username', 1)])
    users.create_index([('role', 1)])
    notifications.create_index([('user', 1), ('read', 1)])
    print("Índices creados para optimización.")
except Exception as e:
    print(f"Error al crear índices: {e}")

def log_user_action(username, action, details, ip_address=None):
    """Log user actions"""
    try:
        action_colors = {
            'LOGIN': 'success',
            'LOGOUT': 'secondary',
            'CREATE': 'primary',
            'UPDATE': 'warning',
            'DELETE': 'danger',
            'ASSIGN': 'info',
            'COMPLETE': 'success'
        }
        logs.insert_one({
            'timestamp': datetime.now().isoformat(),
            'username': username,
            'action': action,
            'details': details,
            'ip_address': ip_address or 'Unknown',
            'action_color': action_colors.get(action, 'secondary')
        })
    except Exception as e:
        print(f"Error logging action: {e}")

def log_error(error_type, details, username=None, endpoint=None, level='ERROR'):
    """Log system errors"""
    try:
        level_colors = {
            'ERROR': 'danger',
            'WARNING': 'warning',
            'INFO': 'info',
            'CRITICAL': 'dark'
        }
        errors.insert_one({
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'username': username,
            'endpoint': endpoint,
            'error_type': error_type,
            'details': str(details),
            'level_color': level_colors.get(level, 'secondary')
        })
    except Exception as e:
        print(f"Error logging error: {e}")

def send_email_notification(to_email, subject, message, oficio_data=None):
    """Send email notification using SendGrid Web API"""
    def send_async_email():
        try:
            print(f"[EMAIL] Sending to: {to_email}")
            
            if not to_email or '@' not in to_email:
                print(f"[EMAIL ERROR] Invalid email: {to_email}")
                return False
            
            # Construir cuerpo HTML
            html_body = f"""
            <html>
            <body>
                <h2>Sistema de Gestión de Oficios - CONAGOPARE</h2>
                <p>{message}</p>
                {f'''
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">
                    <h4>Detalles del Oficio:</h4>
                    <p><strong>ID:</strong> {oficio_data.get('id_secuencial', 'N/A')}</p>
                    <p><strong>Número:</strong> {oficio_data.get('numero_oficio', 'N/A')}</p>
                    <p><strong>Parroquia:</strong> {oficio_data.get('gad_parroquial', 'N/A')}</p>
                    <p><strong>Cantón:</strong> {oficio_data.get('canton', 'N/A')}</p>
                    <p><strong>Detalle:</strong> {oficio_data.get('detalle', 'N/A')}</p>
                </div>
                ''' if oficio_data else ''}
                <hr>
                <p><small>Sistema automático CONAGOPARE - No responder</small></p>
            </body>
            </html>
            """
            
            # Crear mensaje
            mail = Mail(
                from_email=os.getenv('FROM_EMAIL', 'ticsconagopare@gmail.com'),
                to_emails=to_email,
                subject=subject,
                html_content=html_body
            )
            
            # Cliente SendGrid
            sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
            response = sg.send(mail)
            
            print(f"[EMAIL SUCCESS] Status: {response.status_code}")
            return True
            
        except Exception as e:
            print(f"[EMAIL ERROR] {e}")
            log_error('EMAIL_ERROR', str(e), None, 'send_email_notification', 'WARNING')
            return False
    
    # Hilo asíncrono para no bloquear la app
    print(f"[EMAIL DEBUG] Starting email thread for {to_email}")
    thread = threading.Thread(target=send_async_email)
    thread.daemon = True
    thread.start()

def get_tipos_asesoria():
    return [t['nombre'] for t in tipos_asesoria_coll.find()] or ['Asesoría Técnica', 'Inspección', 'Consultoría']

def get_tipos_asesoria_by_tecnico(tecnico_username):
    """Get advisory types available for a specific technician"""
    tipos = list(tipos_asesoria_coll.find({
        '$or': [
            {'tecnico_asignado': tecnico_username},
            {'tecnico_asignado': None},
            {'tecnico_asignado': {'$exists': False}}
        ]
    }))
    return [t['nombre'] for t in tipos]
roles_list = ['receiver', 'designer', 'tecnico', 'admin', 'sistemas', 'coordinacion']

def format_date(iso_date):
    """Formatea una fecha ISO a dd de Mes de aaaa."""
    if not iso_date:
        return ''
    try:
        if isinstance(iso_date, datetime):
            dt = iso_date
        else:
            dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        months_es = [
            'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ]
        return f"{dt.day} de {months_es[dt.month - 1]} de {dt.year}"
    except (ValueError, TypeError):
        return ''

def format_date_for_traditional(iso_date):
    """Formatea una fecha ISO a dd/mm/aaaa."""
    if not iso_date:
        return ''
    try:
        if isinstance(iso_date, datetime):
            return iso_date.strftime('%d/%m/%Y')
        dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        return dt.strftime('%d/%m/%Y')
    except (ValueError, TypeError):
        return ''

def format_date_with_time(iso_date):
    """Formatea una fecha ISO a dd/mm/aaaa HH:MM."""
    if not iso_date:
        return ''
    try:
        if isinstance(iso_date, datetime):
            return iso_date.strftime('%d/%m/%Y %H:%M')
        dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        return dt.strftime('%d/%m/%Y %H:%M')
    except (ValueError, TypeError):
        return ''

def reordenar_ids_secuenciales(year):
    prefix = f"{year}-"
    all_in_year = list(oficios.find({'id_secuencial': {'$regex': f"^{re.escape(prefix)}"}}).sort('id_secuencial', 1))
    for i, doc in enumerate(all_in_year, 1):
        new_id = f"{prefix}{i:04d}"
        oficios.update_one({'_id': doc['_id']}, {'$set': {'id_secuencial': new_id}})

def cleanup_expired_sessions():
    """Clean up expired sessions older than 1 hour"""
    try:
        cutoff_time = datetime.now() - timedelta(hours=1)
        result = active_sessions.delete_many({'last_activity': {'$lt': cutoff_time}})
        if result.deleted_count > 0:
            print(f"Cleaned up {result.deleted_count} expired sessions")
    except Exception as e:
        print(f"Error cleaning up sessions: {e}")

# Run cleanup on startup
cleanup_expired_sessions()

for oficio in oficios.find({'assignments': {'$exists': True}}):
    assignments = oficio.get('assignments', [])
    updated_assignments = []
    for assignment in assignments:
        updated_assignment = assignment.copy()
        if 'desarrollo_actividad' not in updated_assignment:
            updated_assignment.update({
                'desarrollo_actividad': oficio.get('desarrollo_actividad', ''),
                'fecha_asesoria': oficio.get('fecha_asesoria', ''),
                'sub_estado': oficio.get('sub_estado', 'Asignado'),
                'entrega_recepcion': oficio.get('entrega_recepcion', 'No Aplica'),
                'oficio_delegacion': oficio.get('oficio_delegacion', '') if oficio.get('entrega_recepcion') == 'Aplica' else '',
                'acta_entrega': oficio.get('acta_entrega', '') if oficio.get('entrega_recepcion') == 'Aplica' else ''
            })
        updated_assignments.append(updated_assignment)
    oficios.update_one(
        {'_id': oficio['_id']},
        {
            '$set': {'assignments': updated_assignments},
            '$unset': {
                'desarrollo_actividad': '',
                'fecha_asesoria': '',
                'sub_estado': '',
                'entrega_recepcion': '',
                'oficio_delegacion': '',
                'acta_entrega': ''
            }
        }
    )

@app.before_request
def check_session_timeout():
    if current_user.is_authenticated:
        session_id = session.get('session_id')
        username = current_user.username
        
        # Check if session exists in database
        active_session = active_sessions.find_one({'username': username, 'session_id': session_id})
        
        if not active_session:
            logout_user()
            session.clear()
            flash('Sesión cerrada - Usuario conectado desde otro dispositivo.', 'warning')
            return redirect(url_for('login'))
        
        # Check timeout (10 minutes = 600 seconds)
        last_activity = active_session.get('last_activity')
        if last_activity:
            try:
                if isinstance(last_activity, str):
                    last_activity_time = datetime.fromisoformat(last_activity)
                else:
                    last_activity_time = last_activity
                    
                if (datetime.now() - last_activity_time).total_seconds() > 600:
                    active_sessions.delete_one({'username': username, 'session_id': session_id})
                    logout_user()
                    session.clear()
                    flash('Sesión cerrada por inactividad (10 minutos).', 'info')
                    return redirect(url_for('login'))
            except (ValueError, TypeError):
                active_sessions.delete_one({'username': username, 'session_id': session_id})
                logout_user()
                session.clear()
                flash('Error en la sesión. Por favor, inicia sesión nuevamente.', 'error')
                return redirect(url_for('login'))
        
        # Update last activity
        active_sessions.update_one(
            {'username': username, 'session_id': session_id},
            {'$set': {'last_activity': datetime.now()}}
        )

@app.route('/')
def index():
    if current_user.is_authenticated:
        role_to_endpoint = {
            'admin': 'admin',
            'tecnico': 'tecnico',
            'receiver': 'receive',
            'designer': 'design',
            'sistemas': 'sistemas',
            'coordinacion': 'coordinacion'
        }
        endpoint = role_to_endpoint.get(current_user.role, 'login')
        try:
            if current_user.role == 'admin':
                return redirect(url_for(endpoint, default_view='oficios'))
            elif current_user.role == 'receiver':
                return redirect(url_for(endpoint, default_view='registrar'))
            elif current_user.role == 'designer':
                return redirect(url_for(endpoint, default_view='pendientes'))
            elif current_user.role == 'tecnico':
                return redirect(url_for(endpoint, default_view='asignados'))
            elif current_user.role == 'sistemas':
                return redirect(url_for(endpoint, default_view='add-product'))
            elif current_user.role == 'coordinacion':
                return redirect(url_for(endpoint, current_view='asignados'))
            else:
                return redirect(url_for(endpoint))
        except BuildError as e:
            flash(f'Error de redirección: {str(e)}', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = escape(request.form['username'])
        password = request.form['password'].encode('utf-8')
        user = users.find_one({'username': username})
        if user:
            stored_password = user['password']
            try:
                if isinstance(stored_password, bytes):
                    password_match = bcrypt.checkpw(password, stored_password)
                else:
                    password_match = bcrypt.checkpw(password, stored_password.data)
                if password_match:
                    import uuid
                    
                    # Generate unique session ID
                    session_id = str(uuid.uuid4())
                    
                    # Check if user has sessions from different IP
                    existing_sessions = list(active_sessions.find({'username': username}))
                    current_ip = request.remote_addr
                    
                    # Remove sessions from different IPs (different devices)
                    for existing_session in existing_sessions:
                        if existing_session.get('ip_address') != current_ip:
                            active_sessions.delete_one({'_id': existing_session['_id']})
                    
                    # Create new session record
                    active_sessions.insert_one({
                        'username': username,
                        'session_id': session_id,
                        'login_time': datetime.now(),
                        'last_activity': datetime.now(),
                        'ip_address': current_ip
                    })
                    
                    user_obj = User(username=user['username'], role=user['role'])
                    login_user(user_obj)
                    session['session_id'] = session_id
                    session['full_name'] = f"{user.get('nombre', '')} {user.get('apellido', '')}".strip() or username
                    log_user_action(username, 'LOGIN', f'Usuario {username} inició sesión', request.remote_addr)
                    return redirect(url_for('index'))
                else:
                    flash('Usuario o contraseña incorrecta.', 'error')
            except Exception as e:
                flash(f'Error al verificar contraseña: {str(e)}', 'error')
        else:
            flash('Usuario o contraseña incorrecta.', 'error')
    return render_template('login.html')

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    username = current_user.username
    session_id = session.get('session_id')
    
    # Remove session from database
    if session_id:
        active_sessions.delete_one({'username': username, 'session_id': session_id})
    
    log_user_action(username, 'LOGOUT', f'Usuario {username} cerró sesión', request.remote_addr)
    logout_user()
    session.clear()
    return redirect(url_for('login'))

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    old_password = request.form.get('old_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    if not old_password or not new_password or not confirm_password:
        flash('Todos los campos son obligatorios', 'error')
        return redirect(url_for('index'))
    
    old_password = old_password.encode('utf-8')
    new_password = new_password.encode('utf-8')
    confirm_password = confirm_password.encode('utf-8')
    
    try:
        user = users.find_one({'username': current_user.username})
        if not user or not bcrypt.checkpw(old_password, user['password']):
            flash('La contraseña anterior es incorrecta', 'error')
        elif new_password != confirm_password:
            flash('Las nuevas contraseñas no coinciden', 'error')
        else:
            hashed_password = bcrypt.hashpw(new_password, bcrypt.gensalt())
            users.update_one({'username': current_user.username}, {'$set': {'password': hashed_password}})
            flash('Contraseña actualizada exitosamente', 'success')
    except PyMongoError as e:
        flash(f'Error de base de datos: {str(e)}', 'error')
    except Exception as e:
        flash(f'Error inesperado: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/get_notifications', methods=['GET'])
def get_notifications():
    if not current_user.is_authenticated:
        return jsonify({'notifications': [], 'count': 0})
    try:
        user_notifications = list(notifications.find(
            {'user': current_user.username, 'read': False},
            {'message': 1, 'details': 1, 'type': 1, 'priority': 1, 'oficio_id': 1, 'timestamp': 1}
        ).sort('timestamp', -1).limit(50))
        count = len(user_notifications)
        formatted_notifications = [
            {
                'id': str(n['_id']),
                'message': escape(n['message']),
                'details': escape(n.get('details', '')),
                'type': n.get('type', 'general'),
                'priority': n.get('priority', 'normal'),
                'oficio_id': n.get('oficio_id', ''),
                'timestamp': format_date_with_time(n['timestamp'])
            } for n in user_notifications
        ]
        return jsonify({'notifications': formatted_notifications, 'count': count})
    except Exception as e:
        return jsonify({'notifications': [], 'count': 0, 'error': str(e)})

@app.route('/clear_notifications', methods=['POST'])
def clear_notifications():
    if not current_user.is_authenticated:
        return jsonify({'success': False})
    try:
        notifications.update_many({'user': current_user.username, 'read': False}, {'$set': {'read': True}})
        return jsonify({'success': True})
    except PyMongoError as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/mark_notification_read', methods=['POST'])
def mark_notification_read():
    if not current_user.is_authenticated:
        return jsonify({'success': False})
    try:
        data = request.get_json()
        notification_id = data.get('notification_id')
        notifications.update_one(
            {'_id': ObjectId(notification_id), 'user': current_user.username},
            {'$set': {'read': True}}
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/delete_notification', methods=['POST'])
def delete_notification():
    if not current_user.is_authenticated:
        return jsonify({'success': False})
    try:
        data = request.get_json()
        notification_id = data.get('notification_id')
        notifications.delete_one(
            {'_id': ObjectId(notification_id), 'user': current_user.username}
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/notificaciones/count')
def notificaciones_count():
    if not current_user.is_authenticated:
        return jsonify({'count': 0})
    try:
        count = notifications.count_documents({'user': current_user.username, 'read': False})
        return jsonify({'count': count})
    except PyMongoError as e:
        return jsonify({'count': 0, 'error': str(e)})

@app.route('/session_heartbeat', methods=['POST'])
def session_heartbeat():
    try:
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
            
        session_id = session.get('session_id')
        username = current_user.username
        
        if not session_id:
            return jsonify({'success': False, 'error': 'No session ID'}), 401
        
        # Check if session exists
        active_session = active_sessions.find_one({'username': username, 'session_id': session_id})
        
        if not active_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 401
        
        # Update last activity
        result = active_sessions.update_one(
            {'username': username, 'session_id': session_id},
            {'$set': {'last_activity': datetime.now()}}
        )
        
        if result.matched_count == 0:
            return jsonify({'success': False, 'error': 'Session expired'}), 401
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/session_cleanup', methods=['POST'])
@login_required
def session_cleanup():
    try:
        session_id = session.get('session_id')
        username = current_user.username
        
        active_sessions.delete_one({'username': username, 'session_id': session_id})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/session_status', methods=['GET'])
def session_status():
    try:
        if not current_user.is_authenticated:
            return jsonify({'valid': False, 'timeLeft': 0, 'reason': 'not_authenticated'})
            
        session_id = session.get('session_id')
        username = current_user.username
        
        if not session_id or not isinstance(session_id, str):
            return jsonify({'valid': False, 'timeLeft': 0, 'reason': 'no_session_id'})
        
        active_session = active_sessions.find_one({'username': username, 'session_id': session_id})
        
        if not active_session:
            return jsonify({'valid': False, 'timeLeft': 0, 'reason': 'session_not_found'})
        
        last_activity = active_session.get('last_activity')
        if last_activity:
            if isinstance(last_activity, str):
                last_activity_time = datetime.fromisoformat(last_activity)
            else:
                last_activity_time = last_activity
                
            time_elapsed = (datetime.now() - last_activity_time).total_seconds()
            time_left = max(0, 600 - time_elapsed)
            
            if time_left <= 0:
                active_sessions.delete_one({'username': username, 'session_id': session_id})
                return jsonify({'valid': False, 'timeLeft': 0, 'reason': 'expired'})
            
            return jsonify({
                'valid': True,
                'timeLeft': int(time_left),
                'lastActivity': last_activity_time.isoformat()
            })
        
        return jsonify({'valid': False, 'timeLeft': 0, 'reason': 'no_activity'})
    except Exception as e:
        return jsonify({'valid': False, 'timeLeft': 0, 'reason': 'error', 'error': str(e)})

@app.route('/get_canton', methods=['POST'])
def get_canton():
    try:
        data = request.get_json()
        parroquia = escape(data.get('parroquia', ''))
        if parroquia:
            parroquia_data = parroquias.find_one({'parroquia': parroquia})
            if parroquia_data:
                return jsonify({'canton': parroquia_data.get('canton', '')})
        return jsonify({'canton': ''})
    except Exception as e:
        return jsonify({'canton': '', 'error': str(e)})

@app.route('/get_tipos_asesoria_by_tecnico/<tecnico_username>', methods=['GET'])
@login_required
def get_tipos_asesoria_by_tecnico_api(tecnico_username):
    try:
        tipos = get_tipos_asesoria_by_tecnico(tecnico_username)
        return jsonify({'tipos_asesoria': tipos})
    except Exception as e:
        return jsonify({'tipos_asesoria': [], 'error': str(e)})

@app.route('/receive', methods=['GET', 'POST'])
@login_required
def receive():
    if current_user.role not in ['receiver', 'admin']:
        flash('Acceso no autorizado.', 'error')
        return redirect(url_for('login'))
    current_view = request.args.get('default_view', 'registrar')

    try:
        parroquias_data = list(parroquias.find().sort('parroquia', 1))
        if not parroquias_data:
            flash('No se encontraron parroquias en la base de datos. Contácte al administrador.', 'warning')
            print("Advertencia: la colección 'parroquias' está vacía.")

        historial = list(oficios.find({'fecha_recibido': {'$exists': True}}).sort('id_secuencial', 1))
        for oficio in historial:
            oficio['fecha_enviado_traditional'] = format_date_for_traditional(oficio.get('fecha_enviado', ''))
            oficio['fecha_recibido_traditional'] = format_date_for_traditional(oficio.get('fecha_recibido', ''))
            oficio['fecha_designacion_traditional'] = format_date_for_traditional(oficio.get('fecha_designacion', ''))
            assignments = oficio.get('assignments', [])
            for assignment in assignments:
                if 'anexo_datos' in assignment:
                    del assignment['anexo_datos']
                if 'archivo_datos' in assignment:
                    del assignment['archivo_datos']
                for key, value in assignment.items():
                    if isinstance(value, ObjectId):
                        assignment[key] = str(value)
                assignment['fecha_asesoria_formatted'] = format_date(assignment.get('fecha_asesoria', ''))
                assignment['fecha_asesoria_traditional'] = format_date_for_traditional(assignment.get('fecha_asesoria', ''))
            oficio['_id'] = str(oficio['_id'])

        oficios_list = list(oficios.find().sort('id_secuencial', 1))
        for oficio in oficios_list:
            oficio['fecha_enviado_formatted'] = format_date(oficio.get('fecha_enviado', ''))
            oficio['fecha_enviado_traditional'] = format_date_for_traditional(oficio.get('fecha_enviado', ''))
            oficio['fecha_recibido_formatted'] = format_date(oficio.get('fecha_recibido', ''))
            oficio['fecha_designacion_formatted'] = format_date(oficio.get('fecha_designacion', ''))
            assignments = oficio.get('assignments', [])
            for assignment in assignments:
                if 'anexo_datos' in assignment:
                    del assignment['anexo_datos']
                if 'archivo_datos' in assignment:
                    del assignment['archivo_datos']
                for key, value in assignment.items():
                    if isinstance(value, ObjectId):
                        assignment[key] = str(value)
                assignment['fecha_asesoria_formatted'] = format_date(assignment.get('fecha_asesoria', ''))
                assignment['fecha_asesoria_traditional'] = format_date_for_traditional(assignment.get('fecha_asesoria', ''))
            oficio['_id'] = str(oficio['_id'])

        users_list = list(users.find({}, {'username': 1, 'nombre': 1, 'apellido': 1, 'role': 1, '_id': 0}))
        for user in users_list:
            user['full_name'] = f"{user.get('nombre', '')} {user.get('apellido', '')}".strip() or user['username']

        if request.method == 'POST':
            if 'register_oficio' in request.form:
                try:
                    fecha_enviado = datetime.strptime(request.form['fecha_enviado'], '%Y-%m-%d').isoformat()
                except ValueError:
                    flash('Formato de fecha inválido.', 'error')
                    return redirect(url_for('receive'))
                numero_oficio = escape(request.form['numero_oficio'])
                gad_parroquial = escape(request.form['gad_parroquial'])
                canton = escape(request.form['canton'])
                detalle = escape(request.form.get('detalle', ''))

                if not all([fecha_enviado, numero_oficio, gad_parroquial, canton]):
                    flash('Todos los campos obligatorios deben completarse.', 'error')
                    return redirect(url_for('receive'))
                if len(detalle) > 10000:
                    flash('Detalle excede longitud máxima.', 'error')
                    return redirect(url_for('receive'))

                year = datetime.strptime(request.form['fecha_enviado'], '%Y-%m-%d').year
                max_id_doc = oficios.find_one({'id_secuencial': {'$regex': f'^{year}-'}}, sort=[('id_secuencial', -1)])
                count = int(max_id_doc['id_secuencial'].split('-')[1]) + 1 if max_id_doc else 1
                id_secuencial = f"{year}-{count:04d}"
                fecha_recibido_iso = datetime.now().isoformat()
                fecha_recibido_traditional = datetime.now().strftime('%d/%m/%y')

                oficio_data = {
                    'id_secuencial': id_secuencial,
                    'fecha_enviado': fecha_enviado,
                    'fecha_recibido': fecha_recibido_iso,
                    'fecha_recibido_traditional': fecha_recibido_traditional,
                    'numero_oficio': numero_oficio,
                    'gad_parroquial': gad_parroquial,
                    'canton': canton,
                    'detalle': detalle,
                    'estado': 'pendiente',
                    'assignments': [],
                    'fecha_designacion': None,
                    'desarrollo_actividad': None,
                    'fecha_asesoria': None,
                    'sub_estado': None,
                    'entrega_recepcion': None,
                    'oficio_delegacion': None,
                    'acta_entrega': None
                }

                archivo = request.files.get('archivo')
                if archivo and archivo.filename:
                    if not archivo.filename.lower().endswith('.pdf'):
                        flash('Solo se permiten archivos PDF.', 'error')
                        return redirect(url_for('receive'))
                    archivo_id = fs.put(archivo, filename=secure_filename(archivo.filename))
                    oficio_data['archivo_id'] = archivo_id
                    oficio_data['archivo_nombre'] = secure_filename(archivo.filename)

                try:
                    print(f"[EMAIL DEBUG] About to insert oficio...")
                    oficios.insert_one(oficio_data)
                    print(f"[EMAIL DEBUG] Oficio inserted successfully")
                    reordenar_ids_secuenciales(year)
                    print(f"[EMAIL DEBUG] Starting email notification process...")
                    
                    try:
                        designers = users.find({'role': {'$in': ['designer', 'admin']}})
                        designers_list = list(designers)
                        print(f"[EMAIL DEBUG] Found {len(designers_list)} designers/admins")
                        
                        for designer in designers_list:
                            print(f"[EMAIL DEBUG] Processing designer: {designer['username']}, email: {designer.get('email', 'NO EMAIL')}, role: {designer.get('role', 'NO ROLE')}")
                            
                            try:
                                notifications.insert_one({
                                    'user': designer['username'],
                                    'message': f'📋 Nuevo oficio de {gad_parroquial} ({canton}) requiere designación',
                                    'details': f'Oficio: {numero_oficio} | ID: {id_secuencial}',
                                    'type': 'new_oficio',
                                    'oficio_id': id_secuencial,
                                    'priority': 'normal',
                                    'timestamp': datetime.now().isoformat(),
                                    'read': False
                                })
                                print(f"[EMAIL DEBUG] Notification inserted for {designer['username']}")
                            except Exception as notif_error:
                                print(f"[EMAIL DEBUG] Error inserting notification: {str(notif_error)}")
                            
                            if designer.get('email'):
                                print(f"[EMAIL DEBUG] *** SENDING EMAIL TO DESIGNER ***")
                                print(f"[EMAIL DEBUG] Designer: {designer['username']}")
                                print(f"[EMAIL DEBUG] Email: {designer['email']}")
                                try:
                                    send_email_notification(
                                        designer['email'],
                                        f'Nuevo Oficio Requiere Designación - {id_secuencial}',
                                        f'Se ha registrado un nuevo oficio de {gad_parroquial} ({canton}) que requiere designación de técnico.',
                                        {
                                            'id_secuencial': id_secuencial,
                                            'numero_oficio': numero_oficio,
                                            'gad_parroquial': gad_parroquial,
                                            'canton': canton,
                                            'detalle': detalle
                                        }
                                    )
                                    print(f"[EMAIL DEBUG] *** EMAIL SENT TO {designer['username']} ***")
                                except Exception as email_error:
                                    print(f"[EMAIL ERROR] *** EMAIL FAILED: {str(email_error)} ***")
                            else:
                                print(f"[EMAIL DEBUG] *** NO EMAIL FOR {designer['username']} ***")

                        print(f"[EMAIL DEBUG] Email sending process completed")
                    except Exception as email_process_error:
                        print(f"[EMAIL DEBUG] Error in email process: {str(email_process_error)}")
                    
                    flash('Oficio registrado exitosamente.', 'success')
                except PyMongoError as e:
                    print(f"[EMAIL DEBUG] Database error during oficio registration: {str(e)}")
                    flash(f'Error de base de datos al registrar oficio: {str(e)}', 'error')
                except Exception as general_error:
                    print(f"[EMAIL DEBUG] General error during oficio registration: {str(general_error)}")
                    flash(f'Error general: {str(general_error)}', 'error')
                return redirect(url_for('receive', current_view='registrar'))

            elif 'edit_oficio' in request.form:
                oficio_id = request.form.get('oficio_id')
                try:
                    fecha_enviado = datetime.strptime(request.form['fecha_enviado'], '%Y-%m-%d').isoformat()
                except ValueError:
                    flash('Formato de fecha inválido.', 'error')
                    return redirect(url_for('receive'))
                numero_oficio = escape(request.form['numero_oficio'])
                gad_parroquial = escape(request.form['gad_parroquial'])
                canton = escape(request.form['canton'])
                detalle = escape(request.form.get('detalle', ''))

                if not all([oficio_id, fecha_enviado, numero_oficio, gad_parroquial, canton]):
                    flash('Todos los campos obligatorios deben completarse.', 'error')
                    return redirect(url_for('receive'))
                if len(detalle) > 10000:
                    flash('Detalle excede longitud máxima.', 'error')
                    return redirect(url_for('receive'))

                update_data = {
                    'fecha_enviado': fecha_enviado,
                    'numero_oficio': numero_oficio,
                    'gad_parroquial': gad_parroquial,
                    'canton': canton,
                    'detalle': detalle
                }

                archivo = request.files.get('archivo')
                if archivo and archivo.filename:
                    if not archivo.filename.lower().endswith('.pdf'):
                        flash('Solo se permiten archivos PDF.', 'error')
                        return redirect(url_for('receive'))
                    old_oficio = oficios.find_one({'_id': ObjectId(oficio_id)})
                    if old_oficio.get('archivo_id'):
                        try:
                            fs.delete(old_oficio['archivo_id'])
                        except PyMongoError:
                            pass
                    archivo_id = fs.put(archivo, filename=secure_filename(archivo.filename))
                    update_data['archivo_id'] = archivo_id
                    update_data['archivo_nombre'] = secure_filename(archivo.filename)

                try:
                    result = oficios.update_one({'_id': ObjectId(oficio_id)}, {'$set': update_data})
                    if result.matched_count == 0:
                        flash('Oficio no encontrado.', 'error')
                    else:
                        flash('Oficio actualizado exitosamente.', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al actualizar oficio: {str(e)}', 'error')
                return redirect(url_for('receive', current_view='historial'))

            elif 'delete_oficio' in request.form:
                oficio_id = request.form.get('delete_oficio')
                try:
                    oficio = oficios.find_one({'_id': ObjectId(oficio_id)})
                    if not oficio:
                        flash('Oficio no encontrado.', 'error')
                        return redirect(url_for('receive'))
                    year = oficio['id_secuencial'].split('-')[0]
                    if oficio.get('archivo_id'):
                        try:
                            fs.delete(oficio['archivo_id'])
                        except PyMongoError:
                            pass
                    for assignment in oficio.get('assignments', []):
                        if assignment.get('anexo_id'):
                            try:
                                fs.delete(assignment['anexo_id'])
                            except PyMongoError:
                                pass
                    oficios.delete_one({'_id': ObjectId(oficio_id)})
                    reordenar_ids_secuenciales(year)
                    notifications.delete_many({'oficio_id': ObjectId(oficio_id)})
                    flash('Oficio eliminado y IDs reordenados exitosamente.', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al eliminar oficio: {str(e)}', 'error')
                return redirect(url_for('receive', current_view='historial'))

            elif 'actualizar' in request.form or 'entregar' in request.form:
                oficio_id = request.form.get('oficio_id')
                numero_oficio = escape(request.form.get('numero_oficio', ''))
                sub_estado = escape(request.form.get('sub_estado', ''))
                desarrollo_actividad = escape(request.form.get('desarrollo_actividad', ''))
                fecha_asesoria = escape(request.form.get('fecha_asesoria', ''))
                entrega_recepcion = escape(request.form.get('entrega_recepcion', 'No Aplica'))
                oficio_delegacion = escape(request.form.get('oficio_delegacion', '')) if entrega_recepcion == 'Aplica' else ''
                acta_entrega = escape(request.form.get('acta_entrega', '')) if entrega_recepcion == 'Aplica' else ''

                update_data = {
                    'sub_estado': sub_estado,
                    'desarrollo_actividad': desarrollo_actividad,
                    'fecha_asesoria': fecha_asesoria,
                    'entrega_recepcion': entrega_recepcion,
                    'oficio_delegacion': oficio_delegacion,
                    'acta_entrega': acta_entrega
                }

                anexo = request.files.get('anexo')
                if anexo and anexo.filename:
                    anexo_nombre = secure_filename(anexo.filename)
                    anexo_id = fs.put(anexo, filename=anexo_nombre)
                    update_data['anexo_nombre'] = anexo_nombre
                    update_data['anexo_id'] = anexo_id
                    
                update_set = {
                    'assignments.$.sub_estado': update_data['sub_estado'],
                    'assignments.$.desarrollo_actividad': update_data['desarrollo_actividad'],
                    'assignments.$.fecha_asesoria': update_data['fecha_asesoria'],
                    'assignments.$.entrega_recepcion': update_data['entrega_recepcion'],
                    'assignments.$.oficio_delegacion': update_data['oficio_delegacion'],
                    'assignments.$.acta_entrega': update_data['acta_entrega']
                }
                
                if 'anexo_nombre' in update_data:
                    update_set['assignments.$.anexo_nombre'] = update_data['anexo_nombre']
                    update_set['assignments.$.anexo_id'] = update_data['anexo_id']
                
                if 'entregar' in request.form and request.form.get('entregar') == '1':
                    if sub_estado == 'Concluido':
                        oficio_data = oficios.find_one({'_id': ObjectId(oficio_id)})
                        if oficio_data:
                            all_concluded = True
                            for assignment in oficio_data.get('assignments', []):
                                if assignment['tecnico'] == current_user.username:
                                    continue
                                if assignment.get('sub_estado') != 'Concluido':
                                    all_concluded = False
                                    break
                            if all_concluded:
                                update_set['estado'] = 'completado'
                    else:
                        flash('Debe marcar como Concluido antes de entregar', 'error')
                        return redirect(url_for('receive', current_view='tecnico'))
                
                try:
                    result = oficios.update_one(
                        {'_id': ObjectId(oficio_id), 'assignments.tecnico': current_user.username},
                        {'$set': update_set}
                    )
                    
                    if result.matched_count > 0:
                        if 'entregar' in request.form and request.form.get('entregar') == '1':
                            flash('Entregado correctamente', 'success')
                        else:
                            flash('Actualizado correctamente', 'success')
                    else:
                        flash('No se encontró el oficio', 'error')
                except Exception as e:
                    flash('Error al actualizar', 'error')

                return redirect(url_for('receive', current_view='tecnico'))
        asignados = []
        completados = []
        
        for oficio in oficios.find({'estado': {'$in': ['designado', 'completado']}}).sort('fecha_designacion', -1):
            for assignment in oficio.get('assignments', []):
                if assignment['tecnico'] == current_user.username:
                    assignment_data = {
                        '_id': str(oficio['_id']),
                        'id_secuencial': oficio['id_secuencial'],
                        'numero_oficio': oficio['numero_oficio'],
                        'gad_parroquial': oficio['gad_parroquial'],
                        'canton': oficio['canton'],
                        'detalle': oficio['detalle'],
                        'tipo_asesoria': assignment['tipo_asesoria'],
                        'fecha_designacion_formatted': format_date_for_traditional(oficio.get('fecha_designacion', '')),
                        'sub_estado': assignment.get('sub_estado', 'Asignado'),
                        'desarrollo_actividad': assignment.get('desarrollo_actividad', ''),
                        'fecha_asesoria': assignment.get('fecha_asesoria', ''),
                        'fecha_asesoria_traditional': format_date_for_traditional(assignment.get('fecha_asesoria', '')),
                        'entrega_recepcion': assignment.get('entrega_recepcion', 'No Aplica'),
                        'oficio_delegacion': assignment.get('oficio_delegacion', ''),
                        'acta_entrega': assignment.get('acta_entrega', ''),
                        'archivo_nombre': oficio.get('archivo_nombre', ''),
                        'anexo_nombre': assignment.get('anexo_nombre', '')
                    }
                    if assignment.get('sub_estado') == 'Concluido':
                        completados.append(assignment_data)
                    else:
                        asignados.append(assignment_data)

        completados = sorted(completados, key=lambda x: x['fecha_asesoria'] or '9999-12-31', reverse=True)

        return render_template('receive.html',
                               parroquias=parroquias_data,
                               historial=historial,
                               oficios=oficios_list,
                               users=users_list,
                               asignados=asignados,
                               completados=completados,
                               tipos_asesoria=get_tipos_asesoria(),
                               tipos_asesoria_full=list(tipos_asesoria_coll.find()),
                               current_view=current_view)

    except PyMongoError as e:
        log_error('DATABASE_ERROR', str(e), current_user.username if current_user.is_authenticated else None, 'receive', 'ERROR')
        flash(f'Error de base de datos: {str(e)}', 'error')
        print(f"Error in receive: {str(e)}")
        return render_template('receive.html',
                               parroquias=parroquias_data if 'parroquias_data' in locals() else [],
                               historial=historial if 'historial' in locals() else [],
                               oficios=oficios_list if 'oficios_list' in locals() else [],
                               users=users_list if 'users_list' in locals() else [],
                               tipos_asesoria=get_tipos_asesoria(),
                               current_view=current_view)
    except Exception as e:
        log_error('UNEXPECTED_ERROR', str(e), current_user.username if current_user.is_authenticated else None, 'receive', 'CRITICAL')
        flash(f'Error inesperado: {str(e)}', 'error')
        print(f"Unexpected error in receive: {str(e)}")
        return render_template('receive.html',
                               parroquias=parroquias_data if 'parroquias_data' in locals() else [],
                               historial=historial if 'historial' in locals() else [],
                               oficios=oficios_list if 'oficios_list' in locals() else [],
                               users=users_list if 'users_list' in locals() else [],
                               tipos_asesoria=get_tipos_asesoria(),
                               current_view=current_view)

@app.route('/seguimiento', methods=['GET'])
@login_required
def seguimiento():
    if current_user.role not in ['receiver', 'admin', 'designer', 'tecnico', 'coordinacion']:
        return redirect(url_for('login'))
    try:
        oficios_list = list(oficios.find().sort('fecha_recibido', -1))
        users_list = list(users.find({}, {'username': 1, 'nombre': 1, 'apellido': 1, 'role': 1, '_id': 0}))
        for user in users_list:
            user['full_name'] = f"{user.get('nombre', '')} {user.get('apellido', '')}".strip() or user['username']
        
        for oficio in oficios_list:
            oficio['fecha_recibido_formatted'] = format_date_for_traditional(oficio.get('fecha_recibido'))
            oficio['fecha_recibido_traditional'] = format_date_for_traditional(oficio.get('fecha_recibido', ''))
            oficio['fecha_enviado_traditional'] = format_date_for_traditional(oficio.get('fecha_enviado', ''))
            oficio['fecha_enviado_formatted'] = format_date_for_traditional(oficio.get('fecha_enviado'))
            oficio['fecha_designacion_formatted'] = format_date_for_traditional(oficio.get('fecha_designacion', ''))
            assignments = oficio.get('assignments', [])
            for assignment in assignments:
                if 'anexo_datos' in assignment:
                    del assignment['anexo_datos']
                if 'archivo_datos' in assignment:
                    del assignment['archivo_datos']
                for key, value in assignment.items():
                    if isinstance(value, ObjectId):
                        assignment[key] = str(value)
                assignment['fecha_asesoria_traditional'] = format_date_for_traditional(assignment.get('fecha_asesoria', ''))
                assignment['fecha_asesoria_formatted'] = format_date(assignment.get('fecha_asesoria', ''))
            oficio['assignments'] = assignments
            oficio['_id'] = str(oficio['_id'])

        return render_template('seguimiento.html',
                               oficios=oficios_list,
                               users=users_list,
                               parroquias=list(parroquias.find()))
    except PyMongoError as e:
        flash(f'Error de base de datos: {str(e)}', 'error')
        print(f"Database error in seguimiento: {str(e)}")
        return render_template('seguimiento.html', oficios=[], users=[], parroquias=[])
    except Exception as e:
        flash(f'Error inesperado: {str(e)}', 'error')
        print(f"Unexpected error in seguimiento: {str(e)}")
        return render_template('seguimiento.html', oficios=[], users=[], parroquias=[])

@app.route('/design', methods=['GET', 'POST'])
@login_required
def design():
    if current_user.role not in ['designer', 'admin']:
        return redirect(url_for('login'))
    current_view = request.args.get('default_view', 'pendientes')
    try:
        pendientes = list(oficios.find({'estado': 'pendiente'}).sort('id_secuencial', 1))
        designados = list(oficios.find({'estado': {'$in': ['designado', 'completado']}}).sort('id_secuencial', 1))
        completados = list(oficios.find({'estado': 'completado'}).sort('id_secuencial', 1))
        
        print(f"DEBUG: Pendientes count: {len(pendientes)}")
        print(f"DEBUG: Designados count: {len(designados)}")
        print(f"DEBUG: Completados count: {len(completados)}")
        
        all_estados = list(oficios.aggregate([{"$group": {"_id": "$estado", "count": {"$sum": 1}}}]))
        print(f"DEBUG: All estados in DB: {all_estados}")
        
        if designados:
            print(f"DEBUG: First designado: {designados[0].get('id_secuencial', 'No ID')}")
            print(f"DEBUG: First designado estado: {designados[0].get('estado', 'No estado')}")
            print(f"DEBUG: First designado assignments: {len(designados[0].get('assignments', []))}")

        for oficio in pendientes + designados + completados:
            oficio['fecha_enviado_traditional'] = format_date_for_traditional(oficio.get('fecha_enviado', ''))
            oficio['fecha_recibido_traditional'] = format_date_for_traditional(oficio.get('fecha_recibido', ''))
            oficio['fecha_designacion_formatted'] = format_date_for_traditional(oficio.get('fecha_designacion', ''))
            oficio['fecha_designacion_with_time'] = format_date_with_time(oficio.get('fecha_designacion', ''))
            if oficio.get('fecha_enviado'):
                try:
                    dt = datetime.fromisoformat(oficio['fecha_enviado'].replace('Z', '+00:00'))
                    oficio['fecha_enviado'] = dt.strftime('%Y-%m-%d')
                except ValueError:
                    oficio['fecha_enviado'] = ''
            assignments = oficio.get('assignments', [])

            for assignment in assignments:
                if 'anexo_datos' in assignment:
                    del assignment['anexo_datos']
                if 'archivo_datos' in assignment:
                    del assignment['archivo_datos']
                for key, value in assignment.items():
                    if isinstance(value, ObjectId):
                        assignment[key] = str(value)
                assignment['fecha_asesoria_formatted'] = format_date_for_traditional(assignment.get('fecha_asesoria', ''))
            oficio['assignments'] = assignments
            oficio['_id'] = str(oficio['_id'])

        users_list = list(users.find({}, {'username': 1, 'nombre': 1, 'apellido': 1, 'role': 1, '_id': 0}))
        for user in users_list:
            user['full_name'] = f"{user.get('nombre', '')} {user.get('apellido', '')}".strip() or user['username']

        if request.method == 'POST':
            if 'designar' in request.form:
                oficio_id = request.form.get('oficio_id')
                tecnicos = request.form.getlist('tecnico_asignado[]')
                tipos_asesoria = request.form.getlist('tipo_asesoria[]')
                
                if not oficio_id:
                    flash('ID de oficio requerido.', 'danger')
                    return redirect(url_for('design'))
                tecnicos = [t.strip() for t in tecnicos if t and t.strip()]
                tipos_asesoria = [ta.strip() for ta in tipos_asesoria if ta and ta.strip()]
                try:
                    ObjectId(oficio_id)
                except:
                    flash('ID de oficio inválido.', 'danger')
                    return redirect(url_for('design'))
                    
                assignments = [{
                    'tecnico': tecnicos[i],
                    'tipo_asesoria': tipos_asesoria[i],
                    'sub_estado': 'Asignado',
                    'desarrollo_actividad': '',
                    'fecha_asesoria': '',
                    'entrega_recepcion': 'No Aplica',
                    'oficio_delegacion': '',
                    'acta_entrega': ''
                } for i in range(len(tecnicos))]
                update_data = {
                    'assignments': assignments,
                    'estado': 'designado',
                    'fecha_designacion': datetime.now().isoformat()
                }
                try:
                    oficios.update_one({'_id': ObjectId(oficio_id)}, {'$set': update_data})
                    notifications.delete_many({'oficio_id': ObjectId(oficio_id)})
                    oficio_data = oficios.find_one({'_id': ObjectId(oficio_id)})
                    oficio_id_secuencial = oficio_data.get('id_secuencial', 'Desconocido') if oficio_data else 'Desconocido'
                    for assignment in assignments:
                        user_data = users.find_one({'username': assignment['tecnico']})
                        user_name = f"{user_data.get('nombre', '')} {user_data.get('apellido', '')}".strip() if user_data else assignment['tecnico']
                        notifications.insert_one({
                            'user': assignment['tecnico'],
                            'message': f'🔧 Asignación de {assignment["tipo_asesoria"]} para {oficio_data.get("gad_parroquial", "")}',
                            'details': f'Oficio: {oficio_data.get("numero_oficio", "")} | ID: {oficio_id_secuencial}',
                            'type': 'assignment',
                            'oficio_id': oficio_id_secuencial,
                            'priority': 'high',
                            'timestamp': datetime.now().isoformat(),
                            'read': False
                        })
                        if user_data and user_data.get('email'):
                            print(f"[EMAIL DEBUG] Sending assignment email to {assignment['tecnico']} at {user_data['email']}")
                            send_email_notification(
                                user_data['email'],
                                f'Nueva Asignación de {assignment["tipo_asesoria"]} - {oficio_id_secuencial}',
                                f'Se le ha asignado una nueva tarea de {assignment["tipo_asesoria"]} para {oficio_data.get("gad_parroquial", "")}.',
                                {
                                    'id_secuencial': oficio_id_secuencial,
                                    'numero_oficio': oficio_data.get('numero_oficio', ''),
                                    'gad_parroquial': oficio_data.get('gad_parroquial', ''),
                                    'canton': oficio_data.get('canton', ''),
                                    'detalle': oficio_data.get('detalle', '')
                                }
                            )
                        else:
                            print(f"[EMAIL DEBUG] No email configured for user {assignment['tecnico']}")
                    flash('Técnico asignado exitosamente.', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al asignar técnico: {str(e)}', 'danger')
                return redirect(url_for('design', current_view='pendientes'))

            elif 'edit_oficio' in request.form:
                oficio_id = request.form.get('oficio_id')
                tecnicos = request.form.getlist('tecnico_asignado[]')
                tipos = request.form.getlist('tipo_asesoria[]')
                tecnicos = [t.strip() for t in tecnicos if t and t.strip()]
                tipos = [ta.strip() for ta in tipos if ta and ta.strip()]
                
                try:
                    fecha_enviado = request.form['fecha_enviado']
                    datetime.fromisoformat(fecha_enviado)
                except ValueError:
                    flash('Formato de fecha inválido. Use YYYY-MM-DD.', 'error')
                    return redirect(url_for('design'))
                    
                numero_oficio = escape(request.form['numero_oficio'])
                gad_parroquial = escape(request.form['gad_parroquial'])
                canton = escape(request.form['canton'])
                detalle = escape(request.form.get('detalle', ''))
                
                if not oficio_id or not tecnicos or not tipos or len(tecnicos) != len(tipos):
                    flash('Debe completar todos los campos requeridos.', 'danger')
                    return redirect(url_for('design'))
                    
                try:
                    ObjectId(oficio_id)
                except:
                    flash('ID de oficio inválido.', 'danger')
                    return redirect(url_for('design'))
                    
                assignments = [{
                    'tecnico': tecnicos[i],
                    'tipo_asesoria': tipos[i],
                    'sub_estado': 'Asignado',
                    'desarrollo_actividad': '',
                    'fecha_asesoria': '',
                    'entrega_recepcion': 'No Aplica',
                    'oficio_delegacion': '',
                    'acta_entrega': ''
                } for i in range(len(tecnicos))]
                update_data = {
                    'fecha_enviado': fecha_enviado,
                    'numero_oficio': numero_oficio,
                    'gad_parroquial': gad_parroquial,
                    'canton': canton,
                    'detalle': detalle,
                    'assignments': assignments,
                    'fecha_designacion': datetime.now().isoformat()
                }
                try:
                    oficios.update_one({'_id': ObjectId(oficio_id)}, {'$set': update_data})
                    notifications.delete_many({'oficio_id': ObjectId(oficio_id)})
                    oficio_data = oficios.find_one({'_id': ObjectId(oficio_id)})
                    oficio_id_secuencial = oficio_data.get('id_secuencial', 'Desconocido') if oficio_data else 'Desconocido'
                    for assignment in assignments:
                        notifications.insert_one({
                            'user': assignment['tecnico'],
                            'message': f'Oficio actualizado: {oficio_id_secuencial}',
                            'timestamp': datetime.now().isoformat(),
                            'oficio_id': ObjectId(oficio_id),
                            'read': False
                        })
                    flash('Oficio actualizado exitosamente.', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al actualizar oficio: {str(e)}', 'danger')
                return redirect(url_for('design', current_view='designados'))

            elif 'delete_oficio' in request.form:
                oficio_id = request.form.get('oficio_id')
                try:
                    oficio = oficios.find_one({'_id': ObjectId(oficio_id)})
                    if not oficio:
                        flash('Oficio no encontrado.', 'danger')
                        return redirect(url_for('design'))
                    if oficio.get('archivo_id'):
                        try:
                            fs.delete(oficio['archivo_id'])
                        except PyMongoError:
                            pass
                    for assignment in oficio.get('assignments', []):
                        if assignment.get('anexo_id'):
                            try:
                                fs.delete(assignment['anexo_id'])
                            except PyMongoError:
                                pass
                    year = oficio['id_secuencial'].split('-')[0]
                    oficios.delete_one({'_id': ObjectId(oficio_id)})
                    notifications.delete_many({'oficio_id': ObjectId(oficio_id)})
                    reordenar_ids_secuenciales(year)
                    flash('Oficio eliminado y IDs reordenados exitosamente.', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al eliminar oficio: {str(e)}', 'danger')
                return redirect(url_for('design', current_view='designados'))

            elif 'actualizar' in request.form or 'entregar' in request.form:
                oficio_id = request.form.get('oficio_id')
                numero_oficio = escape(request.form.get('numero_oficio', ''))
                sub_estado = escape(request.form.get('sub_estado', ''))
                desarrollo_actividad = escape(request.form.get('desarrollo_actividad', ''))
                fecha_asesoria = escape(request.form.get('fecha_asesoria', ''))
                entrega_recepcion = escape(request.form.get('entrega_recepcion', 'No Aplica'))
                oficio_delegacion = escape(request.form.get('oficio_delegacion', '')) if entrega_recepcion == 'Aplica' else ''
                acta_entrega = escape(request.form.get('acta_entrega', '')) if entrega_recepcion == 'Aplica' else ''

                update_data = {
                    'sub_estado': sub_estado,
                    'desarrollo_actividad': desarrollo_actividad,
                    'fecha_asesoria': fecha_asesoria,
                    'entrega_recepcion': entrega_recepcion,
                    'oficio_delegacion': oficio_delegacion,
                    'acta_entrega': acta_entrega
                }

                anexo = request.files.get('anexo')
                if anexo and anexo.filename:
                    anexo_nombre = secure_filename(anexo.filename)
                    anexo_id = fs.put(anexo, filename=anexo_nombre)
                    update_data['anexo_nombre'] = anexo_nombre
                    update_data['anexo_id'] = anexo_id
                    
                update_set = {
                    'assignments.$.sub_estado': update_data['sub_estado'],
                    'assignments.$.desarrollo_actividad': update_data['desarrollo_actividad'],
                    'assignments.$.fecha_asesoria': update_data['fecha_asesoria'],
                    'assignments.$.entrega_recepcion': update_data['entrega_recepcion'],
                    'assignments.$.oficio_delegacion': update_data['oficio_delegacion'],
                    'assignments.$.acta_entrega': update_data['acta_entrega']
                }
                
                if 'anexo_nombre' in update_data:
                    update_set['assignments.$.anexo_nombre'] = update_data['anexo_nombre']
                    update_set['assignments.$.anexo_id'] = update_data['anexo_id']
                
                if 'entregar' in request.form and request.form.get('entregar') == '1':
                    if sub_estado == 'Concluido':
                        oficio_data = oficios.find_one({'_id': ObjectId(oficio_id)})
                        if oficio_data:
                            all_concluded = True
                            for assignment in oficio_data.get('assignments', []):
                                if assignment['tecnico'] == current_user.username:
                                    continue
                                if assignment.get('sub_estado') != 'Concluido':
                                    all_concluded = False
                                    break
                            if all_concluded:
                                update_set['estado'] = 'completado'
                    else:
                        flash('Debe marcar como Concluido antes de entregar', 'error')
                        return redirect(url_for('design', current_view='tecnico'))
                
                try:
                    result = oficios.update_one(
                        {'_id': ObjectId(oficio_id), 'assignments.tecnico': current_user.username},
                        {'$set': update_set}
                    )
                    
                    if result.matched_count > 0:
                        if 'entregar' in request.form and request.form.get('entregar') == '1':
                            flash('Entregado correctamente', 'success')
                        else:
                            flash('Actualizado correctamente', 'success')
                    else:
                        flash('No se encontró el oficio', 'error')
                except Exception as e:
                    flash('Error al actualizar', 'error')

                return redirect(url_for('design', current_view='tecnico'))

        all_oficios = list(oficios.find().sort('id_secuencial', 1))
        for oficio in all_oficios:
            oficio['fecha_enviado_traditional'] = format_date_for_traditional(oficio.get('fecha_enviado', ''))
            oficio['fecha_recibido_traditional'] = format_date_for_traditional(oficio.get('fecha_recibido', ''))
            oficio['fecha_designacion_formatted'] = format_date_for_traditional(oficio.get('fecha_designacion', ''))
            oficio['fecha_designacion_with_time'] = format_date_with_time(oficio.get('fecha_designacion', ''))
            assignments = oficio.get('assignments', [])
            for assignment in assignments:
                if 'anexo_datos' in assignment:
                    del assignment['anexo_datos']
                if 'archivo_datos' in assignment:
                    del assignment['archivo_datos']
                for key, value in assignment.items():
                    if isinstance(value, ObjectId):
                        assignment[key] = str(value)
                assignment['fecha_asesoria_formatted'] = format_date_for_traditional(assignment.get('fecha_asesoria', ''))
            oficio['assignments'] = assignments
            oficio['_id'] = str(oficio['_id'])
        asignados_tecnico = []
        completados_tecnico = []
        
        for oficio in oficios.find({'estado': {'$in': ['designado', 'completado']}}).sort('fecha_designacion', -1):
            for assignment in oficio.get('assignments', []):
                if assignment['tecnico'] == current_user.username:
                    assignment_data = {
                        '_id': str(oficio['_id']),
                        'id_secuencial': oficio['id_secuencial'],
                        'numero_oficio': oficio['numero_oficio'],
                        'gad_parroquial': oficio['gad_parroquial'],
                        'canton': oficio['canton'],
                        'detalle': oficio['detalle'],
                        'tipo_asesoria': assignment['tipo_asesoria'],
                        'fecha_designacion_formatted': format_date_for_traditional(oficio.get('fecha_designacion', '')),
                        'sub_estado': assignment.get('sub_estado', 'Asignado'),
                        'desarrollo_actividad': assignment.get('desarrollo_actividad', ''),
                        'fecha_asesoria': assignment.get('fecha_asesoria', ''),
                        'fecha_asesoria_traditional': format_date_for_traditional(assignment.get('fecha_asesoria', '')),
                        'entrega_recepcion': assignment.get('entrega_recepcion', 'No Aplica'),
                        'oficio_delegacion': assignment.get('oficio_delegacion', ''),
                        'acta_entrega': assignment.get('acta_entrega', ''),
                        'archivo_nombre': oficio.get('archivo_nombre', ''),
                        'anexo_nombre': assignment.get('anexo_nombre', '')
                    }
                    if assignment.get('sub_estado') == 'Concluido':
                        completados_tecnico.append(assignment_data)
                    else:
                        asignados_tecnico.append(assignment_data)

        completados_tecnico = sorted(completados_tecnico, key=lambda x: x['fecha_asesoria'] or '9999-12-31', reverse=True)

        return render_template('design.html',
                               pendientes=pendientes,
                               designados=designados,
                               completados=completados,
                               oficios=all_oficios,
                               users=users_list,
                               asignados=asignados_tecnico,
                               completados_tecnico=completados_tecnico,
                               tipos_asesoria=get_tipos_asesoria(),
                               tipos_asesoria_full=list(tipos_asesoria_coll.find()),
                               parroquias=list(parroquias.find()),
                               current_view=current_view)

    except PyMongoError as e:
        log_error('DATABASE_ERROR', str(e), current_user.username if current_user.is_authenticated else None, 'design', 'ERROR')
        flash(f'Error de base de datos: {str(e)}', 'danger')
        print(f"Error in design: {str(e)}")
        return render_template('design.html',
                               pendientes=[],
                               designados=[],
                               completados=[],
                               oficios=[],
                               users=[],
                               tipos_asesoria=get_tipos_asesoria(),
                               parroquias=[],
                               current_view=current_view)
    except Exception as e:
        log_error('UNEXPECTED_ERROR', str(e), current_user.username if current_user.is_authenticated else None, 'design', 'CRITICAL')
        flash(f'Error inesperado: {str(e)}', 'danger')
        print(f"Unexpected error in design: {str(e)}")
        return render_template('design.html',
                               pendientes=[],
                               designados=[],
                               completados=[],
                               oficios=[],
                               users=[],
                               tipos_asesoria=get_tipos_asesoria(),
                               parroquias=[],
                               current_view=current_view)

@app.route('/tecnico', methods=['GET', 'POST'])
@login_required
def tecnico():
    if current_user.role not in ['tecnico', 'admin']:
        return redirect(url_for('login'))
    current_view = request.args.get('default_view', 'asignados')
    try:
        anexos_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'anexos')
        os.makedirs(anexos_folder, exist_ok=True)
        if request.method == 'POST':
            if 'actualizar' in request.form or 'entregar' in request.form:
                oficio_id = request.form.get('oficio_id')
                numero_oficio = escape(request.form.get('numero_oficio', ''))
                sub_estado = escape(request.form.get('sub_estado', ''))
                desarrollo_actividad = escape(request.form.get('desarrollo_actividad', ''))
                fecha_asesoria = escape(request.form.get('fecha_asesoria', ''))
                entrega_recepcion = escape(request.form.get('entrega_recepcion', 'No Aplica'))
                oficio_delegacion = escape(request.form.get('oficio_delegacion', '')) if entrega_recepcion == 'Aplica' else ''
                acta_entrega = escape(request.form.get('acta_entrega', '')) if entrega_recepcion == 'Aplica' else ''

                update_data = {
                    'sub_estado': sub_estado,
                    'desarrollo_actividad': desarrollo_actividad,
                    'fecha_asesoria': fecha_asesoria,
                    'entrega_recepcion': entrega_recepcion,
                    'oficio_delegacion': oficio_delegacion,
                    'acta_entrega': acta_entrega
                }

                anexo = request.files.get('anexo')
                if anexo and anexo.filename:
                    anexo_nombre = secure_filename(anexo.filename)
                    anexo_id = fs.put(anexo, filename=anexo_nombre)
                    update_data['anexo_nombre'] = anexo_nombre
                    update_data['anexo_id'] = anexo_id
                update_set = {
                    'assignments.$.sub_estado': update_data['sub_estado'],
                    'assignments.$.desarrollo_actividad': update_data['desarrollo_actividad'],
                    'assignments.$.fecha_asesoria': update_data['fecha_asesoria'],
                    'assignments.$.entrega_recepcion': update_data['entrega_recepcion'],
                    'assignments.$.oficio_delegacion': update_data['oficio_delegacion'],
                    'assignments.$.acta_entrega': update_data['acta_entrega']
                }
                
                if 'anexo_nombre' in update_data:
                    update_set['assignments.$.anexo_nombre'] = update_data['anexo_nombre']
                    update_set['assignments.$.anexo_id'] = update_data['anexo_id']
                
                if 'entregar' in request.form and request.form.get('entregar') == '1':
                    if sub_estado == 'Concluido':
                        oficio_data = oficios.find_one({'_id': ObjectId(oficio_id)})
                        if oficio_data:
                            all_concluded = True
                            for assignment in oficio_data.get('assignments', []):
                                if assignment['tecnico'] == current_user.username:
                                    continue
                                if assignment.get('sub_estado') != 'Concluido':
                                    all_concluded = False
                                    break
                            if all_concluded:
                                update_set['estado'] = 'completado'
                    else:
                        flash('Debe marcar como Concluido antes de entregar', 'error')
                        return redirect(url_for('tecnico', current_view='asignados'))
                
                try:
                    result = oficios.update_one(
                        {'_id': ObjectId(oficio_id), 'assignments.tecnico': current_user.username},
                        {'$set': update_set}
                    )
                    
                    if result.matched_count > 0:
                        oficio_data = oficios.find_one({'_id': ObjectId(oficio_id)})
                        user_data = users.find_one({'username': current_user.username})
                        user_name = f"{user_data.get('nombre', '')} {user_data.get('apellido', '')}".strip() if user_data else current_user.username
                        
                        # Enviar notificaciones a receive
                        designers = users.find({'role': 'designer'})
                        for designer in designers:
                            print(f"[EMAIL DEBUG] Processing designer notification: {designer['username']}, email: {designer.get('email', 'NO EMAIL')}")
                            if designer.get('email'):
                                if 'entregar' in request.form and request.form.get('entregar') == '1':
                                    print(f"[EMAIL DEBUG] Sending delivery notification to {designer['username']}")
                                    send_email_notification(
                                        designer['email'],
                                        f'Oficio Entregado por Técnico - {oficio_data.get("id_secuencial", "")}',
                                        f'El técnico {user_name} ha entregado el oficio de {oficio_data.get("gad_parroquial", "")} ({oficio_data.get("canton", "")}) con estado: {sub_estado}.',
                                        {
                                            'id_secuencial': oficio_data.get('id_secuencial', ''),
                                            'numero_oficio': oficio_data.get('numero_oficio', ''),
                                            'gad_parroquial': oficio_data.get('gad_parroquial', ''),
                                            'canton': oficio_data.get('canton', ''),
                                            'detalle': f'Técnico: {user_name} | Estado: {sub_estado}'
                                        }
                                        
                                    )
                                else:
                                    # Notificación de actualización
                                    print(f"[EMAIL DEBUG] Sending update notification to {designer['username']}")
                                    send_email_notification(
                                        designer['email'],
                                        f'Actualización de Técnico - {oficio_data.get("id_secuencial", "")}',
                                        f'El técnico {user_name} ha actualizado el oficio de {oficio_data.get("gad_parroquial", "")} ({oficio_data.get("canton", "")}) con estado: {sub_estado}.',
                                        {
                                            'id_secuencial': oficio_data.get('id_secuencial', ''),
                                            'numero_oficio': oficio_data.get('numero_oficio', ''),
                                            'gad_parroquial': oficio_data.get('gad_parroquial', ''),
                                            'canton': oficio_data.get('canton', ''),
                                            'detalle': f'Técnico: {user_name} | Estado: {sub_estado} | Desarrollo: {desarrollo_actividad[:100]}...'
                                        }
                                    )
                            else:
                                print(f"[EMAIL DEBUG] No email configured for designer {designer['username']}")
                        
                        if 'entregar' in request.form and request.form.get('entregar') == '1':
                            flash('Entregado correctamente', 'success')
                        else:
                            flash('Actualizado correctamente', 'success')
                    else:
                        flash('No se encontro el oficio', 'error')
                except Exception as e:
                    flash('Error al actualizar', 'error')

                return redirect(url_for('tecnico', current_view='asignados'))

        asignados = []
        completados = []
        
        for oficio in oficios.find({'estado': {'$in': ['designado', 'completado']}}).sort('fecha_designacion', -1):
            for assignment in oficio.get('assignments', []):
                if assignment['tecnico'] == current_user.username:
                    assignment_data = {
                        '_id': str(oficio['_id']),
                        'id_secuencial': oficio['id_secuencial'],
                        'numero_oficio': oficio['numero_oficio'],
                        'gad_parroquial': oficio['gad_parroquial'],
                        'canton': oficio['canton'],
                        'detalle': oficio['detalle'],
                        'tipo_asesoria': assignment['tipo_asesoria'],
                        'fecha_designacion': oficio.get('fecha_designacion', ''),
                        'fecha_designacion_formatted': format_date_for_traditional(oficio.get('fecha_designacion', '')),
                        'sub_estado': assignment.get('sub_estado', 'Asignado'),
                        'desarrollo_actividad': assignment.get('desarrollo_actividad', ''),
                        'fecha_asesoria': assignment.get('fecha_asesoria', ''),
                        'fecha_asesoria_traditional': format_date_for_traditional(assignment.get('fecha_asesoria', '')),
                        'entrega_recepcion': assignment.get('entrega_recepcion', 'No Aplica'),
                        'oficio_delegacion': assignment.get('oficio_delegacion', ''),
                        'acta_entrega': assignment.get('acta_entrega', ''),
                        'archivo_nombre': oficio.get('archivo_nombre', ''),
                        'anexo_nombre': assignment.get('anexo_nombre', '')
                    }
                    if assignment.get('sub_estado') == 'Concluido':
                        completados.append(assignment_data)
                    else:
                        asignados.append(assignment_data)

        completados = sorted(completados, key=lambda x: x['fecha_asesoria'] or '9999-12-31', reverse=True)

        return render_template('tecnico.html',
                               asignados=asignados,
                               completados=completados,
                               users=list(users.find()) if current_user.role == 'admin' else [],
                               parroquias=list(parroquias.find()),
                               current_view=current_view)
    except PyMongoError as e:
        flash(f'Error de base de datos: {str(e)}', 'error')
        print(f"Database error in tecnico: {str(e)}")
        return redirect(url_for('tecnico', current_view=current_view))
    except Exception as e:
        flash(f'Error inesperado: {str(e)}', 'error')
        print(f"Unexpected error in tecnico: {str(e)}")
        return redirect(url_for('tecnico', current_view=current_view))

@app.route('/download_anexo/<oficio_id>/<tecnico>')
@login_required
def download_anexo(oficio_id, tecnico):
    try:
        if not ObjectId.is_valid(oficio_id):
            return "Invalid oficio ID", 400
        oficio = oficios.find_one({
            '_id': ObjectId(oficio_id),
            'assignments.tecnico': tecnico
        })
        if not oficio:
            return "Oficio not found or not assigned to the specified tecnico", 404
        anexo_nombre = None
        anexo_id = None
        for assignment in oficio.get('assignments', []):
            if assignment['tecnico'] == tecnico and assignment.get('anexo_id'):
                anexo_nombre = assignment['anexo_nombre']
                anexo_id = assignment['anexo_id']
                break
        if not anexo_nombre or not anexo_id:
            return "Anexo not found for this tecnico", 404
        anexo_file = fs.get(anexo_id)
        file_data = anexo_file.read()
        
        if anexo_nombre.lower().endswith('.pdf'):
            content_type = 'application/pdf'
            disposition = 'inline'
        else:
            content_type = 'application/octet-stream'
            disposition = 'attachment'
        
        response = make_response(file_data)
        response.headers['Content-Type'] = content_type
        response.headers['Content-Disposition'] = f'{disposition}; filename="{anexo_nombre}"'
        return response
    except PyMongoError as e:
        return f"Error de base de datos: {str(e)}", 500
    except Exception as e:
        return f"Error retrieving anexo: {str(e)}", 500

@app.route('/preview_anexo/<oficio_id>/<int:assignment_index>')
@login_required
def preview_anexo(oficio_id, assignment_index):
    try:
        if not ObjectId.is_valid(oficio_id):
            return "Invalid oficio ID", 400
        oficio = oficios.find_one({'_id': ObjectId(oficio_id)})
        if not oficio:
            return "Oficio not found", 404
        assignments = oficio.get('assignments', [])
        if assignment_index >= len(assignments):
            return "Assignment index out of range", 404
        assignment = assignments[assignment_index]
        if not assignment.get('anexo_id') or not assignment.get('anexo_nombre'):
            return "Anexo not found for this assignment", 404
        anexo_file = fs.get(assignment['anexo_id'])
        file_data = anexo_file.read()
        anexo_nombre = assignment['anexo_nombre']
        if anexo_nombre.lower().endswith('.pdf'):
            content_type = 'application/pdf'
            disposition = 'inline'
        else:
            content_type = 'application/octet-stream'
            disposition = 'attachment'
        
        response = make_response(file_data)
        response.headers['Content-Type'] = content_type
        response.headers['Content-Disposition'] = f'{disposition}; filename="{anexo_nombre}"'
        return response
    except PyMongoError as e:
        return f"Error de base de datos: {str(e)}", 500
    except Exception as e:
        return f"Error retrieving anexo: {str(e)}", 500

@app.route('/download_anexo_by_index/<oficio_id>/<int:assignment_index>')
@login_required
def download_anexo_by_index(oficio_id, assignment_index):
    try:
        if not ObjectId.is_valid(oficio_id):
            return "Invalid oficio ID", 400
        oficio = oficios.find_one({'_id': ObjectId(oficio_id)})
        if not oficio:
            return "Oficio not found", 404
        assignments = oficio.get('assignments', [])
        if assignment_index >= len(assignments):
            return "Assignment index out of range", 404
        assignment = assignments[assignment_index]
        if not assignment.get('anexo_id') or not assignment.get('anexo_nombre'):
            return "Anexo not found for this assignment", 404
        anexo_file = fs.get(assignment['anexo_id'])
        file_data = anexo_file.read()
        anexo_nombre = assignment['anexo_nombre']
        
        response = make_response(file_data)
        response.headers['Content-Type'] = 'application/octet-stream'
        response.headers['Content-Disposition'] = f'attachment; filename="{anexo_nombre}"'
        return response
    except PyMongoError as e:
        return f"Error de base de datos: {str(e)}", 500
    except Exception as e:
        return f"Error retrieving anexo: {str(e)}", 500

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    try:
        current_view = request.args.get('default_view', request.args.get('current_section', request.form.get('current_section', 'oficios')))
        current_section = current_view
        if request.method == 'POST':
            if 'create_user' in request.form:
                try:
                    username = escape(request.form['username'])
                    password = request.form['password'].encode('utf-8')
                    hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
                    users.insert_one({
                        'nombre': escape(request.form['nombre']),
                        'apellido': escape(request.form['apellido']),
                        'username': username,
                        'password': hashed_password,
                        'role': request.form['role'],
                        'email': escape(request.form.get('email', ''))
                    })
                    flash('Usuario creado exitosamente', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al crear usuario: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al crear usuario: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'edit_user' in request.form:
                user_id = request.form['user_id']
                update_data = {
                    'nombre': escape(request.form['nombre']),
                    'apellido': escape(request.form['apellido']),
                    'username': escape(request.form['username']),
                    'role': request.form['role'],
                    'email': escape(request.form.get('email', ''))
                }
                if request.form['password']:
                    password = request.form['password'].encode('utf-8')
                    update_data['password'] = bcrypt.hashpw(password, bcrypt.gensalt())
                try:
                    users.update_one({'_id': ObjectId(user_id)}, {'$set': update_data})
                    flash('Usuario actualizado exitosamente', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al actualizar usuario: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al actualizar usuario: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'delete_user' in request.form:
                user_id = request.form['user_id']
                try:
                    users.delete_one({'_id': ObjectId(user_id)})
                    flash('Usuario eliminado exitosamente', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al eliminar usuario: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al eliminar usuario: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'add_tipo_asesoria' in request.form:
                try:
                    nombre = escape(request.form['nombre'])
                    tecnico_asignado = escape(request.form.get('tecnico_asignado', ''))
                    tipos_asesoria_coll.insert_one({
                        'nombre': nombre,
                        'tecnico_asignado': tecnico_asignado if tecnico_asignado else None
                    })
                    flash('Tipo de asesoría añadido exitosamente', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al añadir tipo de asesoría: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al añadir tipo de asesoría: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'edit_tipo_asesoria' in request.form:
                tipo_id = request.form['tipo_id']
                try:
                    nombre = escape(request.form['edit_nombre'])
                    tecnico_asignado = escape(request.form.get('edit_tecnico_asignado', ''))
                    tipos_asesoria_coll.update_one({'_id': ObjectId(tipo_id)}, {
                        '$set': {
                            'nombre': nombre,
                            'tecnico_asignado': tecnico_asignado if tecnico_asignado else None
                        }
                    })
                    flash('Tipo de asesoría actualizado exitosamente', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al actualizar tipo de asesoría: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al actualizar tipo de asesoría: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'delete_tipo_asesoria' in request.form:
                tipo_id = request.form['tipo_id']
                try:
                    tipos_asesoria_coll.delete_one({'_id': ObjectId(tipo_id)})
                    flash('Tipo de asesoría eliminado exitosamente', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al eliminar tipo de asesoría: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al eliminar tipo de asesoría: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'add_parroquia' in request.form:
                try:
                    parroquias.insert_one({
                        'parroquia': escape(request.form['parroquia']),
                        'canton': escape(request.form['canton'])
                    })
                    flash('Parroquia añadida exitosamente', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al añadir parroquia: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al añadir parroquia: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'delete_parroquia' in request.form:
                parroquia_id = request.form['parroquia_id']
                try:
                    result = parroquias.delete_one({'_id': ObjectId(parroquia_id)})
                    if result.deleted_count > 0:
                        flash('Parroquia eliminada exitosamente', 'success')
                    else:
                        flash('No se encontró la parroquia para eliminar', 'error')
                except PyMongoError as e:
                    flash(f'Error de base de datos al eliminar parroquia: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al eliminar parroquia: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'edit_parroquia' in request.form:
                parroquia_id = request.form['parroquia_id']
                try:
                    parroquias.update_one({'_id': ObjectId(parroquia_id)}, {
                        '$set': {
                            'parroquia': escape(request.form['edit_parroquia']),
                            'canton': escape(request.form['edit_canton'])
                        }
                    })
                    flash('Parroquia actualizada exitosamente', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al actualizar parroquia: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al actualizar parroquia: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'edit_oficio' in request.form:
                oficio_id = request.form['oficio_id']
                try:
                    fecha_enviado = datetime.strptime(request.form['fecha_enviado'], '%d/%m/%y').isoformat()
                except ValueError:
                    flash('Formato de fecha inválido. Use dd/mm/aa.', 'error')
                    return redirect(url_for('admin', current_section=current_section))
                numero_oficio = escape(request.form.get('numero_oficio', ''))
                gad_parroquial = escape(request.form.get('gad_parroquial', ''))
                canton = escape(request.form.get('canton', ''))
                detalle = escape(request.form.get('detalle', ''))
                tecnicos = request.form.getlist('tecnico[]')
                tipos = request.form.getlist('tipo_asesoria[]')
                assignments = [{'tecnico': t, 'tipo_asesoria': tipos[i], 'sub_estado': 'Asignado', 'desarrollo_actividad': '', 'fecha_asesoria': '', 'entrega_recepcion': 'No Aplica', 'oficio_delegacion': '', 'acta_entrega': ''} for i, t in enumerate(tecnicos) if t]

                try:
                    update = {
                        'fecha_enviado': fecha_enviado,
                        'numero_oficio': numero_oficio,
                        'gad_parroquial': gad_parroquial,
                        'canton': canton,
                        'detalle': detalle,
                        'assignments': assignments
                    }

                    archivo = request.files.get('archivo')
                    if archivo and archivo.filename:
                        update['archivo_nombre'] = secure_filename(archivo.filename)
                        update['archivo_id'] = fs.put(archivo, filename=update['archivo_nombre'])

                    oficios.update_one({'_id': ObjectId(oficio_id)}, {'$set': update})
                    flash('Oficio actualizado exitosamente', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al actualizar oficio: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al actualizar oficio: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'delete_oficio' in request.form:
                oficio_id = request.form['oficio_id']
                try:
                    deleted_oficio = oficios.find_one({'_id': ObjectId(oficio_id)})
                    if deleted_oficio:
                        year = deleted_oficio['id_secuencial'].split('-')[0]
                        if deleted_oficio.get('archivo_id'):
                            try:
                                fs.delete(deleted_oficio['archivo_id'])
                            except PyMongoError:
                                pass
                        for assignment in deleted_oficio.get('assignments', []):
                            if assignment.get('anexo_id'):
                                try:
                                    fs.delete(assignment['anexo_id'])
                                except PyMongoError:
                                    pass
                        oficios.delete_one({'_id': ObjectId(oficio_id)})
                        reordenar_ids_secuenciales(year)
                        notifications.delete_many({'oficio_id': ObjectId(oficio_id)})
                        flash('Oficio eliminado y IDs reordenados exitosamente', 'success')
                    else:
                        flash('Oficio no encontrado.', 'error')
                except PyMongoError as e:
                    flash(f'Error de base de datos al eliminar oficio: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al eliminar oficio: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'clear_oficios' in request.form:
                try:
                    for oficio in oficios.find():
                        if oficio.get('archivo_id'):
                            try:
                                fs.delete(oficio['archivo_id'])
                            except:
                                pass
                        for assignment in oficio.get('assignments', []):
                            if assignment.get('anexo_id'):
                                try:
                                    fs.delete(assignment['anexo_id'])
                                except:
                                    pass
                    result = oficios.delete_many({})
                    flash(f'Se eliminaron {result.deleted_count} oficios exitosamente', 'success')
                except Exception as e:
                    flash(f'Error al limpiar oficios: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'clear_notifications' in request.form:
                try:
                    result = notifications.delete_many({})
                    flash(f'Se eliminaron {result.deleted_count} notificaciones exitosamente', 'success')
                except Exception as e:
                    flash(f'Error al limpiar notificaciones: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'clear_orphan_files' in request.form:
                try:
                    referenced_files = set()
                    for oficio in oficios.find():
                        if oficio.get('archivo_id'):
                            referenced_files.add(oficio['archivo_id'])
                        for assignment in oficio.get('assignments', []):
                            if assignment.get('anexo_id'):
                                referenced_files.add(assignment['anexo_id'])
                    deleted_count = 0
                    for file_doc in fs.find():
                        if file_doc._id not in referenced_files:
                            try:
                                fs.delete(file_doc._id)
                                deleted_count += 1
                            except:
                                pass
                    flash(f'Se eliminaron {deleted_count} archivos huérfanos exitosamente', 'success')
                except Exception as e:
                    flash(f'Error al limpiar archivos huérfanos: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'reset_sequential_ids' in request.form:
                try:
                    current_year = datetime.now().year
                    reordenar_ids_secuenciales(current_year)
                    flash(f'IDs secuenciales reiniciados para el año {current_year}', 'success')
                except Exception as e:
                    flash(f'Error al reiniciar IDs secuenciales: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'clear_logs' in request.form:
                try:
                    result = logs.delete_many({})
                    flash(f'Se eliminaron {result.deleted_count} logs exitosamente', 'success')
                except Exception as e:
                    flash(f'Error al limpiar logs: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'clear_errors' in request.form:
                try:
                    result = errors.delete_many({})
                    flash(f'Se eliminaron {result.deleted_count} errores exitosamente', 'success')
                except Exception as e:
                    flash(f'Error al limpiar errores: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'backup_year' in request.form:
                year = request.form.get('backup_year')
                try:
                    if not year or not year.isdigit():
                        flash('Año inválido', 'error')
                        return redirect(url_for('admin', current_section=current_section))
                    
                    backup_collection = db_oficios[f'backup_oficios_{year}']
                    oficios_year = list(oficios.find({'id_secuencial': {'$regex': f'^{year}-'}}))
                    
                    if not oficios_year:
                        flash(f'No se encontraron oficios para el año {year}', 'warning')
                        return redirect(url_for('admin', current_section=current_section))
                    
                    backup_collection.delete_many({})
                    backup_collection.insert_many(oficios_year)
                    
                    flash(f'Respaldo creado exitosamente: {len(oficios_year)} oficios del año {year}', 'success')
                except Exception as e:
                    flash(f'Error al crear respaldo: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

            elif 'restore_year' in request.form:
                year = request.form.get('restore_year')
                try:
                    if not year or not year.isdigit():
                        flash('Año inválido', 'error')
                        return redirect(url_for('admin', current_section=current_section))
                    
                    backup_collection = db_oficios[f'backup_oficios_{year}']
                    backup_data = list(backup_collection.find())
                    
                    if not backup_data:
                        flash(f'No se encontró respaldo para el año {year}', 'warning')
                        return redirect(url_for('admin', current_section=current_section))
                    
                    oficios.delete_many({'id_secuencial': {'$regex': f'^{year}-'}})
                    oficios.insert_many(backup_data)
                    
                    flash(f'Datos restaurados exitosamente: {len(backup_data)} oficios del año {year}', 'success')
                except Exception as e:
                    flash(f'Error al restaurar datos: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section, current_view=current_section))

        stats = {
            'pendientes': oficios.count_documents({'estado': 'pendiente'}),
            'designados': oficios.count_documents({'estado': 'designado'}),
            'completados': oficios.count_documents({'estado': 'completado'})
        }
        all_oficios = list(oficios.find().sort('fecha_recibido', -1))
        for oficio in all_oficios:
            oficio['fecha_recibido_formatted'] = format_date_for_traditional(oficio.get('fecha_recibido'))
            oficio['fecha_recibido_traditional'] = format_date_for_traditional(oficio.get('fecha_recibido', ''))
            oficio['fecha_enviado_formatted'] = format_date_for_traditional(oficio.get('fecha_enviado'))
            oficio['fecha_enviado_traditional'] = format_date_for_traditional(oficio.get('fecha_enviado', ''))
            oficio['fecha_designacion_formatted'] = format_date_for_traditional(oficio.get('fecha_designacion', ''))
            assignments = oficio.get('assignments', [])
            for assignment in assignments:
                if 'anexo_datos' in assignment:
                    del assignment['anexo_datos']
                if 'archivo_datos' in assignment:
                    del assignment['archivo_datos']
                for key, value in assignment.items():
                    if isinstance(value, ObjectId):
                        assignment[key] = str(value)
                assignment['fecha_asesoria_traditional'] = format_date_for_traditional(assignment.get('fecha_asesoria', ''))
            oficio['assignments'] = assignments

        users_list = list(users.find({}, {'username': 1, 'nombre': 1, 'apellido': 1, 'role': 1, '_id': 0}))
        for user in users_list:
            user['full_name'] = f"{user.get('nombre', '')} {user.get('apellido', '')}".strip() or user['username']

        logs_data = list(logs.find().sort('timestamp', -1).limit(100))
        for log in logs_data:
            log['timestamp_formatted'] = format_date_with_time(log['timestamp'])
        
        errors_data = list(errors.find().sort('timestamp', -1).limit(50))
        for error in errors_data:
            error['timestamp_formatted'] = format_date_with_time(error['timestamp'])
        
        available_years = set()
        for oficio in oficios.find({}, {'id_secuencial': 1}):
            year = oficio['id_secuencial'].split('-')[0]
            if year.isdigit():
                available_years.add(year)
        
        backup_collections = []
        for collection_name in db_oficios.list_collection_names():
            if collection_name.startswith('backup_oficios_'):
                year = collection_name.replace('backup_oficios_', '')
                count = db_oficios[collection_name].count_documents({})
                backup_collections.append({'year': year, 'count': count})

        return render_template('admin.html',
                               stats=stats,
                               oficios=all_oficios,
                               users=list(users.find()),
                               roles=roles_list,
                               tipos_asesoria=list(tipos_asesoria_coll.find()),
                               parroquias=list(parroquias.find()),
                               tecnicos=users_list,
                               logs=logs_data,
                               errors=errors_data,
                               available_years=sorted(available_years, reverse=True),
                               backup_collections=backup_collections,
                               current_section=current_section)
    except PyMongoError as e:
        flash(f'Error de base de datos: {str(e)}', 'error')
        print(f"Database error in admin: {str(e)}")
        return redirect(url_for('admin', current_section=current_section, current_view=current_section))
    except Exception as e:
        flash(f'Error inesperado: {str(e)}', 'error')
        print(f"Unexpected error in admin: {str(e)}")
        return redirect(url_for('admin', current_section=current_section, current_view=current_section))

@app.route('/download_backup/<year>')
@login_required
def download_backup(year):
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    try:
        backup_collection = db_oficios[f'backup_oficios_{year}']
        backup_data = list(backup_collection.find())
        
        if not backup_data:
            flash(f'No se encontró respaldo para el año {year}', 'error')
            return redirect(url_for('admin', current_section='mantenimiento'))
        
        for item in backup_data:
            item['_id'] = str(item['_id'])
            for assignment in item.get('assignments', []):
                if 'anexo_id' in assignment:
                    assignment['anexo_id'] = str(assignment['anexo_id'])
                if 'archivo_id' in assignment:
                    assignment['archivo_id'] = str(assignment['archivo_id'])
            if 'archivo_id' in item:
                item['archivo_id'] = str(item['archivo_id'])
        
        json_data = json.dumps(backup_data, indent=2, ensure_ascii=False)
        
        response = make_response(json_data)
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = f'attachment; filename="backup_oficios_{year}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'
        return response
        
    except Exception as e:
        flash(f'Error al descargar respaldo: {str(e)}', 'error')
        return redirect(url_for('admin', current_section='mantenimiento'))

@app.route('/preview/<oficio_id>')
@login_required
def preview(oficio_id):
    try:
        if not ObjectId.is_valid(oficio_id):
            print(f"Invalid oficio_id: {oficio_id}")
            return "Invalid oficio ID", 400
        oficio = oficios.find_one({"_id": ObjectId(oficio_id)})
        if not oficio or not oficio.get('archivo_id'):
            print(f"File not found for oficio_id: {oficio_id}")
            return "File not found", 404
        archivo_nombre = oficio.get('archivo_nombre', '')
        if not archivo_nombre.lower().endswith('.pdf'):
            print(f"Non-PDF file attempted for preview: {archivo_nombre}")
            return "Preview only available for PDF files", 400
        archivo_file = fs.get(oficio['archivo_id'])
        file_data = archivo_file.read()
        if not file_data:
            print(f"Empty file retrieved from GridFS for archivo_id: {oficio['archivo_id']}")
            return "File is empty or corrupted", 500

        response = make_response(file_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename="{archivo_nombre}"'
        response.headers['Content-Length'] = len(file_data)
        print(f"Serving preview for {archivo_nombre} with Content-Disposition: inline")
        return response
    except PyMongoError as e:
        print(f"Database error in preview for oficio_id {oficio_id}: {str(e)}")
        return f"Error de base de datos: {str(e)}", 500
    except Exception as e:
        print(f"Unexpected error in preview for oficio_id {oficio_id}: {str(e)}")
        return f"Error retrieving file: {str(e)}", 500

@app.route('/download/<oficio_id>')
@login_required
def download(oficio_id):
    try:
        if not ObjectId.is_valid(oficio_id):
            return "Invalid oficio ID", 400
        oficio = oficios.find_one({"_id": ObjectId(oficio_id)})
        if not oficio or not oficio.get('archivo_id'):
            return "File not found", 404
        archivo_file = fs.get(oficio['archivo_id'])
        return send_file(
            BytesIO(archivo_file.read()),
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=oficio.get('archivo_nombre', 'file')
        )
    except PyMongoError as e:
        return f"Error de base de datos: {str(e)}", 500
    except Exception as e:
        return f"Error retrieving file: {str(e)}", 500

@app.route('/sistemas', methods=['GET', 'POST'])
@login_required
def sistemas():
    if current_user.role not in ['admin', 'sistemas']:
        return redirect(url_for('login'))
    current_view = request.args.get('default_view', 'add-product')
    try:
        if request.method == 'POST':
            if 'add_product' in request.form:
                codigo = escape(request.form.get('codigo', ''))
                tipo = escape(request.form.get('tipo', ''))
                color = escape(request.form.get('color', ''))
                marca = escape(request.form.get('marca', ''))
                modelo = escape(request.form.get('modelo', ''))
                estado = escape(request.form.get('estado', ''))
                detalle = escape(request.form.get('detalle', ''))
                asignar_tecnico = request.form.get('asignar_tecnico', 'no')
                tecnico = escape(request.form.get('tecnico', '')) if asignar_tecnico == 'sí' else None

                if not all([codigo, tipo, color, marca, modelo, estado]):
                    flash('Todos los campos obligatorios deben ser completados.', 'error')
                    return redirect(url_for('sistemas'))

                imagen = None
                if 'imagen' in request.files:
                    file = request.files['imagen']
                    allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif'}
                    if file and file.filename:
                        if os.path.splitext(file.filename)[1].lower() in allowed_extensions:
                            filename = secure_filename(file.filename)
                            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                            imagen = filename
                        else:
                            flash('Solo se permiten imágenes (PNG, JPG, JPEG, GIF).', 'error')
                            return redirect(url_for('sistemas'))

                if len(codigo) > 50 or len(marca) > 100 or len(modelo) > 100 or len(detalle) > 500:
                    flash('Los campos exceden los límites de longitud.', 'error')
                    return redirect(url_for('sistemas'))

                if not re.match(r'^[A-Za-z0-9\-]+$', codigo):
                    flash('El código solo puede contener letras, números y guiones.', 'error')
                    return redirect(url_for('sistemas'))

                product = {
                    'codigo': codigo,
                    'tipo': tipo,
                    'color': color,
                    'marca': marca,
                    'modelo': modelo,
                    'estado': estado,
                    'detalle': detalle,
                    'tecnico': tecnico,
                    'imagen': imagen
                }
                try:
                    db_oficios.inventarios.insert_one(product)
                    flash('Producto agregado exitosamente', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al agregar producto: {str(e)}', 'error')
                return redirect(url_for('sistemas', current_view='add-product'))

            elif 'edit_product' in request.form:
                product_id = request.form.get('product_id', '')
                codigo = escape(request.form.get('codigo', ''))
                tipo = escape(request.form.get('tipo', ''))
                color = escape(request.form.get('color', ''))
                marca = escape(request.form.get('marca', ''))
                modelo = escape(request.form.get('modelo', ''))
                estado = escape(request.form.get('estado', ''))
                detalle = escape(request.form.get('detalle', ''))
                asignar_tecnico = request.form.get('asignar_tecnico', 'no')
                tecnico = escape(request.form.get('tecnico', '')) if asignar_tecnico == 'sí' else None

                if not all([product_id, codigo, tipo, color, marca, modelo, estado]):
                    flash('Todos los campos obligatorios deben ser completados.', 'error')
                    return redirect(url_for('sistemas'))

                update_data = {
                    'codigo': codigo,
                    'tipo': tipo,
                    'color': color,
                    'marca': marca,
                    'modelo': modelo,
                    'estado': estado,
                    'detalle': detalle,
                    'tecnico': tecnico
                }

                if 'imagen' in request.files:
                    file = request.files['imagen']
                    allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif'}
                    if file and file.filename:
                        if os.path.splitext(file.filename)[1].lower() in allowed_extensions:
                            filename = secure_filename(file.filename)
                            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                            update_data['imagen'] = filename
                        else:
                            flash('Solo se permiten imágenes (PNG, JPG, JPEG, GIF).', 'error')
                            return redirect(url_for('sistemas'))

                try:
                    db_oficios.inventarios.update_one({'_id': ObjectId(product_id)}, {'$set': update_data})
                    flash('Producto actualizado exitosamente', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al actualizar producto: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al actualizar producto: {str(e)}', 'error')
                return redirect(url_for('sistemas', current_view='inventory'))

            elif 'delete_product' in request.form:
                product_id = request.form.get('product_id', '')
                try:
                    result = db_oficios.inventarios.delete_one({'_id': ObjectId(product_id)})
                    if result.deleted_count > 0:
                        flash('Producto eliminado exitosamente', 'success')
                    else:
                        flash('No se encontró el producto para eliminar', 'error')
                except PyMongoError as e:
                    flash(f'Error de base de datos al eliminar producto: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al eliminar producto: {str(e)}', 'error')
                return redirect(url_for('sistemas', current_view='inventory'))

        inventarios = list(db_oficios.inventarios.find())
        for product in inventarios:
            product['_id'] = str(product['_id'])
        tecnicos = list(users.find({'role': 'tecnico'}, {'username': 1, 'nombre': 1, 'apellido': 1, '_id': 0}))
        for user in tecnicos:
            user['full_name'] = f"{user.get('nombre', '')} {user.get('apellido', '')}".strip() or user['username']

        return render_template('sistemas.html',
                               inventarios=inventarios,
                               tecnicos=tecnicos,
                               current_view=current_view)
    except PyMongoError as e:
        flash(f'Error de base de datos: {str(e)}', 'error')
        print(f"Database error in sistemas: {str(e)}")
        return redirect(url_for('sistemas', current_view=current_view))
    except Exception as e:
        flash(f'Error inesperado: {str(e)}', 'error')
        print(f"Unexpected error in sistemas: {str(e)}")
        return redirect(url_for('sistemas', current_view=current_view))

@app.route('/generate_report/<format>')
@login_required
def generate_report(format):
    if current_user.role not in ['receiver', 'designer', 'admin']:
        flash('Acceso no autorizado.', 'error')
        return redirect(url_for('login'))
    
    try:
        oficios_list = list(oficios.find().sort('id_secuencial', 1))
        users_list = list(users.find({'role': 'tecnico'}, {'username': 1, 'nombre': 1, 'apellido': 1, '_id': 0}))
        user_lookup = {user['username']: f"{user.get('nombre', '')} {user.get('apellido', '')}".strip() or user['username'] for user in users_list}
        
        if format == 'pdf':
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
            elements = []
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, spaceAfter=30, alignment=1)
            
            title = Paragraph("Informe de Seguimiento de Oficios", title_style)
            elements.append(title)
            elements.append(Spacer(1, 12))
            
            data = [['ID', 'Número Oficio', 'Parroquia', 'Cantón', 'Estado', 'Técnico', 'Tipo Asesoría', 'Sub-Estado']]
            
            for oficio in oficios_list:
                assignments = oficio.get('assignments', [])
                if assignments:
                    for assignment in assignments:
                        tecnico_name = user_lookup.get(assignment['tecnico'], assignment['tecnico'])
                        data.append([oficio['id_secuencial'], oficio['numero_oficio'], oficio['gad_parroquial'], oficio['canton'], oficio['estado'].capitalize(), tecnico_name, assignment['tipo_asesoria'], assignment.get('sub_estado', 'Asignado')])
                else:
                    data.append([oficio['id_secuencial'], oficio['numero_oficio'], oficio['gad_parroquial'], oficio['canton'], oficio['estado'].capitalize(), '-', '-', '-'])
            
            table = Table(data, colWidths=[0.8*inch, 1.2*inch, 1.2*inch, 1*inch, 0.8*inch, 1.2*inch, 1.2*inch, 0.8*inch])
            table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, 0), 8), ('BOTTOMPADDING', (0, 0), (-1, 0), 12), ('BACKGROUND', (0, 1), (-1, -1), colors.beige), ('FONTSIZE', (0, 1), (-1, -1), 7), ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
            
            elements.append(table)
            doc.build(elements)
            buffer.seek(0)
            return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=f'informe_seguimiento_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
            
        elif format == 'excel':
            import pandas as pd
            
            excel_data = []
            for oficio in oficios_list:
                assignments = oficio.get('assignments', [])
                if assignments:
                    for assignment in assignments:
                        tecnico_name = user_lookup.get(assignment['tecnico'], assignment['tecnico'])
                        excel_data.append({'ID Secuencial': oficio['id_secuencial'], 'Número Oficio': oficio['numero_oficio'], 'Parroquia': oficio['gad_parroquial'], 'Cantón': oficio['canton'], 'Estado': oficio['estado'].capitalize(), 'Técnico': tecnico_name, 'Tipo Asesoría': assignment['tipo_asesoria'], 'Sub-Estado': assignment.get('sub_estado', 'Asignado'), 'Fecha Asesoría': format_date_for_traditional(assignment.get('fecha_asesoria', '')), 'Desarrollo Actividad': assignment.get('desarrollo_actividad', ''), 'Entrega Recepción': assignment.get('entrega_recepcion', 'No Aplica'), 'Anexos': 'Sí' if assignment.get('anexo_nombre') else 'No'})
                else:
                    excel_data.append({'ID Secuencial': oficio['id_secuencial'], 'Número Oficio': oficio['numero_oficio'], 'Parroquia': oficio['gad_parroquial'], 'Cantón': oficio['canton'], 'Estado': oficio['estado'].capitalize(), 'Técnico': '-', 'Tipo Asesoría': '-', 'Sub-Estado': '-', 'Fecha Asesoría': '-', 'Desarrollo Actividad': '-', 'Entrega Recepción': '-', 'Anexos': 'No'})
            
            df = pd.DataFrame(excel_data)
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Seguimiento', index=False)
            
            buffer.seek(0)
            return send_file(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=f'informe_seguimiento_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')
        
        else:
            flash('Formato no válido.', 'error')
            return redirect(url_for('index'))
            
    except ImportError as e:
        flash(f'Librería requerida no instalada: {str(e)}', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error al generar informe: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/get_oficio_informe/<oficio_id>')
@login_required
def get_oficio_informe(oficio_id):
    try:
        if not ObjectId.is_valid(oficio_id):
            return jsonify({'success': False, 'error': 'Invalid oficio ID'})
        
        oficio = oficios.find_one({'_id': ObjectId(oficio_id)})
        if not oficio or not oficio.get('assignments'):
            return jsonify({'success': False, 'error': 'Oficio not found or no assignments'})
        
        users_list = list(users.find({}, {'username': 1, 'nombre': 1, 'apellido': 1, '_id': 0}))
        user_lookup = {user['username']: f"{user.get('nombre', '')} {user.get('apellido', '')}".strip() or user['username'] for user in users_list}
        
        assignments_data = []
        for assignment in oficio['assignments']:
            assignment_data = {
                'tecnico_name': user_lookup.get(assignment['tecnico'], assignment['tecnico']),
                'tipo_asesoria': assignment.get('tipo_asesoria', ''),
                'sub_estado': assignment.get('sub_estado', 'Asignado'),
                'fecha_asesoria_formatted': format_date_for_traditional(assignment.get('fecha_asesoria', '')),
                'desarrollo_actividad': assignment.get('desarrollo_actividad', ''),
                'entrega_recepcion': assignment.get('entrega_recepcion', 'No Aplica'),
                'oficio_delegacion': assignment.get('oficio_delegacion', ''),
                'acta_entrega': assignment.get('acta_entrega', ''),
                'anexo_nombre': assignment.get('anexo_nombre', '')
            }
            assignments_data.append(assignment_data)
        
        return jsonify({
            'success': True,
            'assignments': assignments_data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/informe_imprimible/<oficio_id>')
@login_required
def informe_imprimible(oficio_id):
    try:
        if not ObjectId.is_valid(oficio_id):
            flash('ID de oficio inválido', 'error')
            return redirect(url_for('index'))
        
        oficio = oficios.find_one({'_id': ObjectId(oficio_id)})
        if not oficio:
            flash('Oficio no encontrado', 'error')
            return redirect(url_for('index'))
        
        users_list = list(users.find({}, {'username': 1, 'nombre': 1, 'apellido': 1, '_id': 0}))
        user_lookup = {user['username']: f"{user.get('nombre', '')} {user.get('apellido', '')}".strip() or user['username'] for user in users_list}
        
        oficio['fecha_enviado_traditional'] = format_date_for_traditional(oficio.get('fecha_enviado', ''))
        oficio['fecha_recibido_traditional'] = format_date_for_traditional(oficio.get('fecha_recibido', ''))
        
        assignments = oficio.get('assignments', [])
        for assignment in assignments:
            assignment['tecnico_name'] = user_lookup.get(assignment['tecnico'], assignment['tecnico'])
            assignment['fecha_asesoria_formatted'] = format_date_for_traditional(assignment.get('fecha_asesoria', ''))
        
        return render_template('informe_imprimible.html', oficio=oficio, assignments=assignments)
    except Exception as e:
        flash(f'Error al generar informe: {str(e)}', 'error')
        return redirect(url_for('index'))
    

@app.route('/coordinacion', methods=['GET', 'POST'])
@login_required
def coordinacion():
    if current_user.role not in ['coordinacion', 'admin']:
        return redirect(url_for('login'))
    current_view = request.args.get('current_view', 'asignados')
    try:
        if request.method == 'POST':
            if 'actualizar' in request.form or 'entregar' in request.form:
                oficio_id = request.form.get('oficio_id')
                sub_estado = escape(request.form.get('sub_estado', ''))
                desarrollo_actividad = escape(request.form.get('desarrollo_actividad', ''))
                fecha_asesoria = escape(request.form.get('fecha_asesoria', ''))
                entrega_recepcion = escape(request.form.get('entrega_recepcion', 'No Aplica'))
                oficio_delegacion = escape(request.form.get('oficio_delegacion', '')) if entrega_recepcion == 'Aplica' else ''
                acta_entrega = escape(request.form.get('acta_entrega', '')) if entrega_recepcion == 'Aplica' else ''

                update_data = {
                    'sub_estado': sub_estado,
                    'desarrollo_actividad': desarrollo_actividad,
                    'fecha_asesoria': fecha_asesoria,
                    'entrega_recepcion': entrega_recepcion,
                    'oficio_delegacion': oficio_delegacion,
                    'acta_entrega': acta_entrega
                }

                anexo = request.files.get('anexo')
                if anexo and anexo.filename:
                    anexo_nombre = secure_filename(anexo.filename)
                    anexo_id = fs.put(anexo, filename=anexo_nombre)
                    update_data['anexo_nombre'] = anexo_nombre
                    update_data['anexo_id'] = anexo_id
                    
                update_set = {
                    'assignments.$.sub_estado': update_data['sub_estado'],
                    'assignments.$.desarrollo_actividad': update_data['desarrollo_actividad'],
                    'assignments.$.fecha_asesoria': update_data['fecha_asesoria'],
                    'assignments.$.entrega_recepcion': update_data['entrega_recepcion'],
                    'assignments.$.oficio_delegacion': update_data['oficio_delegacion'],
                    'assignments.$.acta_entrega': update_data['acta_entrega']
                }
                
                if 'anexo_nombre' in update_data:
                    update_set['assignments.$.anexo_nombre'] = update_data['anexo_nombre']
                    update_set['assignments.$.anexo_id'] = update_data['anexo_id']
                
                if 'entregar' in request.form and request.form.get('entregar') == '1':
                    if sub_estado == 'Concluido':
                        oficio_data = oficios.find_one({'_id': ObjectId(oficio_id)})
                        if oficio_data:
                            all_concluded = True
                            for assignment in oficio_data.get('assignments', []):
                                if assignment['tecnico'] == current_user.username:
                                    continue
                                if assignment.get('sub_estado') != 'Concluido':
                                    all_concluded = False
                                    break
                            if all_concluded:
                                update_set['estado'] = 'completado'
                    else:
                        flash('Debe marcar como Concluido antes de entregar', 'error')
                        return redirect(url_for('coordinacion', current_view=current_view))
                
                try:
                    result = oficios.update_one(
                        {'_id': ObjectId(oficio_id), 'assignments.tecnico': current_user.username},
                        {'$set': update_set}
                    )
                    
                    if result.matched_count > 0:
                        oficio_data = oficios.find_one({'_id': ObjectId(oficio_id)})
                        user_data = users.find_one({'username': current_user.username})
                        user_name = f"{user_data.get('nombre', '')} {user_data.get('apellido', '')}".strip() if user_data else current_user.username
                        
                        if 'entregar' in request.form and request.form.get('entregar') == '1':
                            designers = users.find({'role': 'designer'})
                            for designer in designers:
                                print(f"[EMAIL DEBUG] Processing coordinator notification: {designer['username']}, email: {designer.get('email', 'NO EMAIL')}")
                                if designer.get('email'):
                                    print(f"[EMAIL DEBUG] Sending coordinator delivery notification to {designer['username']}")
                                    send_email_notification(
                                        designer['email'],
                                        f'Oficio Entregado por Coordinación - {oficio_data.get("id_secuencial", "")}',
                                        f'El coordinador {user_name} ha entregado el oficio de {oficio_data.get("gad_parroquial", "")} ({oficio_data.get("canton", "")}) con estado: {sub_estado}.',
                                        {
                                            'id_secuencial': oficio_data.get('id_secuencial', ''),
                                            'numero_oficio': oficio_data.get('numero_oficio', ''),
                                            'gad_parroquial': oficio_data.get('gad_parroquial', ''),
                                            'canton': oficio_data.get('canton', ''),
                                            'detalle': f'Coordinador: {user_name} | Estado: {sub_estado}'
                                        }
                                    )
                                else:
                                    print(f"[EMAIL DEBUG] No email configured for designer {designer['username']}")
                        
                        if 'entregar' in request.form and request.form.get('entregar') == '1':
                            flash('Entregado correctamente', 'success')
                        else:
                            flash('Actualizado correctamente', 'success')
                    else:
                        flash('No se encontró el oficio', 'error')
                except Exception as e:
                    flash('Error al actualizar', 'error')

                return redirect(url_for('coordinacion', current_view=current_view))
        asignados = []
        completados = []
        
        for oficio in oficios.find({'estado': {'$in': ['designado', 'completado']}}).sort('fecha_designacion', -1):
            for assignment in oficio.get('assignments', []):
                if assignment['tecnico'] == current_user.username:
                    assignment_data = {
                        '_id': str(oficio['_id']),
                        'id_secuencial': oficio['id_secuencial'],
                        'numero_oficio': oficio['numero_oficio'],
                        'gad_parroquial': oficio['gad_parroquial'],
                        'canton': oficio['canton'],
                        'detalle': oficio['detalle'],
                        'tipo_asesoria': assignment['tipo_asesoria'],
                        'tecnico': assignment['tecnico'],
                        'fecha_designacion': oficio.get('fecha_designacion', ''),
                        'fecha_designacion_formatted': format_date_for_traditional(oficio.get('fecha_designacion', '')),
                        'sub_estado': assignment.get('sub_estado', 'Asignado'),
                        'desarrollo_actividad': assignment.get('desarrollo_actividad', ''),
                        'fecha_asesoria': assignment.get('fecha_asesoria', ''),
                        'fecha_asesoria_traditional': format_date_for_traditional(assignment.get('fecha_asesoria', '')),
                        'entrega_recepcion': assignment.get('entrega_recepcion', 'No Aplica'),
                        'oficio_delegacion': assignment.get('oficio_delegacion', ''),
                        'acta_entrega': assignment.get('acta_entrega', ''),
                        'archivo_nombre': oficio.get('archivo_nombre', ''),
                        'anexo_nombre': assignment.get('anexo_nombre', '')
                    }
                    if assignment.get('sub_estado') == 'Concluido':
                        completados.append(assignment_data)
                    else:
                        asignados.append(assignment_data)
        users_list = list(users.find({}, {'username': 1, 'nombre': 1, 'apellido': 1, 'role': 1, '_id': 0}))
        for user in users_list:
            user['full_name'] = f"{user.get('nombre', '')} {user.get('apellido', '')}".strip() or user['username']
        user_lookup = {user['username']: user['full_name'] for user in users_list}
        
        # Agregar nombres de técnicos a las asignaciones
        for assignment_data in asignados + completados:
            assignment_data['tecnico_name'] = user_lookup.get(assignment_data['tecnico'], assignment_data['tecnico'])
        
        oficios_list = list(oficios.find().sort('id_secuencial', 1))
        
        for oficio in oficios_list:
            oficio['fecha_enviado_traditional'] = format_date_for_traditional(oficio.get('fecha_enviado', ''))
            oficio['fecha_recibido_traditional'] = format_date_for_traditional(oficio.get('fecha_recibido', ''))
            oficio['fecha_designacion_formatted'] = format_date_for_traditional(oficio.get('fecha_designacion', ''))
            assignments = oficio.get('assignments', [])
            for assignment in assignments:
                if 'anexo_datos' in assignment:
                    del assignment['anexo_datos']
                if 'archivo_datos' in assignment:
                    del assignment['archivo_datos']
                for key, value in assignment.items():
                    if isinstance(value, ObjectId):
                        assignment[key] = str(value)
                assignment['fecha_asesoria_formatted'] = format_date(assignment.get('fecha_asesoria', ''))
                assignment['fecha_asesoria_traditional'] = format_date_for_traditional(assignment.get('fecha_asesoria', ''))
                assignment['tecnico_name'] = user_lookup.get(assignment['tecnico'], assignment['tecnico'])
            oficio['assignments'] = assignments
            oficio['_id'] = str(oficio['_id'])

        completados = sorted(completados, key=lambda x: x['fecha_asesoria_traditional'] or '9999-12-31', reverse=True)

        return render_template('coordinacion.html',
                               asignados=asignados,
                               completados=completados,
                               oficios=oficios_list,
                               users=users_list,
                               parroquias=list(parroquias.find()),
                               current_view=current_view)
    except PyMongoError as e:
        log_error('DATABASE_ERROR', str(e), current_user.username if current_user.is_authenticated else None, 'coordinacion', 'ERROR')
        flash(f'Error de base de datos: {str(e)}', 'error')
        return render_template('coordinacion.html', asignados=[], completados=[], oficios=[], users=[], parroquias=[], current_view=current_view)
    except Exception as e:
        log_error('UNEXPECTED_ERROR', str(e), current_user.username if current_user.is_authenticated else None, 'coordinacion', 'CRITICAL')
        flash(f'Error inesperado: {str(e)}', 'error')
        return render_template('coordinacion.html', asignados=[], completados=[], oficios=[], users=[], parroquias=[], current_view=current_view)
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)), debug=True)
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

app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv('SECRET_KEY', 'a1eb8b7d4c7a96ea202923296486a51c')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
app.permanent_session_lifetime = timedelta(minutes=15)
app.config['SESSION_PERMANENT'] = False

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

client = MongoClient('mongodb+srv://ogmoscosoj:KcB4gSO579gBCSzY@conagoparedb.vwmlbqg.mongodb.net/?retryWrites=true&w=majority&appName=conagoparedb')
db_oficios = client['conagoparedb']
oficios = db_oficios['oficios']
parroquias = db_oficios['parroquias']
users = db_oficios['users_db']
notifications = db_oficios['notifications']
tipos_asesoria_coll = db_oficios['tipos_asesoria']
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
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(f"MongoDB connection error: {e}")

try:
    oficios.create_index([('id_secuencial', 1)], unique=True)
    print("Índice único creado para id_secuencial.")
except Exception as e:
    print(f"Error al crear índice: {e}")

def get_tipos_asesoria():
    return [t['nombre'] for t in tipos_asesoria_coll.find()] or ['Asesoría Técnica', 'Inspección', 'Consultoría']
roles_list = ['receiver', 'designer', 'tecnico', 'admin', 'sistemas']

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

def reordenar_ids_secuenciales(year):
    prefix = f"{year}-"
    all_in_year = list(oficios.find({'id_secuencial': {'$regex': f"^{re.escape(prefix)}"}}).sort('id_secuencial', 1))
    for i, doc in enumerate(all_in_year, 1):
        new_id = f"{prefix}{i:04d}"
        oficios.update_one({'_id': doc['_id']}, {'$set': {'id_secuencial': new_id}})

# Migrate existing assignments
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
        last_activity = session.get('last_activity')
        if last_activity:
            try:
                last_activity_time = datetime.fromisoformat(last_activity)
                if (datetime.now() - last_activity_time).total_seconds() > 900:
                    logout_user()
                    session.clear()
                    flash('Sesión cerrada por inactividad.', 'info')
                    return redirect(url_for('login'))
            except ValueError:
                logout_user()
                session.clear()
                flash('Error en la sesión. Por favor, inicia sesión nuevamente.', 'error')
                return redirect(url_for('login'))
        session['last_activity'] = datetime.now().isoformat()

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
        endpoint = role_to_endpoint.get(current_user.role, 'login')
        try:
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
                    user_obj = User(username=user['username'], role=user['role'])
                    login_user(user_obj)
                    session['full_name'] = f"{user.get('nombre', '')} {user.get('apellido', '')}".strip() or username
                    return redirect(url_for('index'))
                else:
                    flash('Contraseña incorrecta.', 'error')
            except Exception as e:
                flash(f'Error al verificar contraseña: {str(e)}', 'error')
        else:
            flash('Usuario no encontrado.', 'error')
    return render_template('login.html')

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    session.clear()
    flash('Has cerrado sesión exitosamente.', 'success')
    return redirect(url_for('login'))

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    old_password = request.form.get('old_password').encode('utf-8')
    new_password = request.form.get('new_password').encode('utf-8')
    confirm_password = request.form.get('confirm_password').encode('utf-8')
    
    if not old_password or not new_password or not confirm_password:
        flash('Todos los campos son obligatorios', 'error')
        return redirect(url_for('index'))
    
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
        user_notifications = list(notifications.find({'user': current_user.username, 'read': False}))
        count = len(user_notifications)
        formatted_notifications = [
            {
                'message': escape(n['message']),
                'timestamp': format_date_for_traditional(n['timestamp'])
            } for n in user_notifications
        ]
        return jsonify({'notifications': formatted_notifications, 'count': count})
    except PyMongoError as e:
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

@app.route('/notificaciones/count')
def notificaciones_count():
    if not current_user.is_authenticated:
        return jsonify({'count': 0})
    try:
        count = notifications.count_documents({'user': current_user.username, 'read': False})
        return jsonify({'count': count})
    except PyMongoError as e:
        return jsonify({'count': 0, 'error': str(e)})

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

@app.route('/receive', methods=['GET', 'POST'])
@login_required
def receive():
    if current_user.role not in ['receiver', 'admin']:
        flash('Acceso no autorizado.', 'error')
        return redirect(url_for('login'))

    try:
        parroquias_data = list(parroquias.find())
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

        users_list = list(users.find({'role': 'tecnico'}, {'username': 1, 'nombre': 1, 'apellido': 1, '_id': 0}))
        for user in users_list:
            user['full_name'] = f"{user.get('nombre', '')} {user.get('apellido', '')}".strip() or user['username']

        if request.method == 'POST':
            if 'register_oficio' in request.form:
                try:
                    # Parsear el formato YYYY-MM-DD del input type="date"
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
                if len(numero_oficio) > 50 or len(detalle) > 10000:
                    flash('Número de oficio o detalle exceden longitud máxima.', 'error')
                    return redirect(url_for('receive'))
                if not re.match(r'^[A-Za-z0-9\-/]+$', numero_oficio):
                    flash('Número de oficio solo puede contener letras, números, guiones y barras.', 'error')
                    return redirect(url_for('receive'))

                year = datetime.strptime(request.form['fecha_enviado'], '%Y-%m-%d').year
                max_id_doc = oficios.find_one({'id_secuencial': {'$regex': f'^{year}-'}}, sort=[('id_secuencial', -1)])
                count = int(max_id_doc['id_secuencial'].split('-')[1]) + 1 if max_id_doc else 1
                id_secuencial = f"{year}-{count:04d}"

                # Calcular fecha_recibido en formato ISO para almacenamiento, pero formatear para visualización
                fecha_recibido_iso = datetime.now().isoformat()
                fecha_recibido_traditional = datetime.now().strftime('%d/%m/%y')

                oficio_data = {
                    'id_secuencial': id_secuencial,
                    'fecha_enviado': fecha_enviado,
                    'fecha_recibido': fecha_recibido_iso,
                    'fecha_recibido_traditional': fecha_recibido_traditional,  # Almacenar formato tradicional para visualización
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
                    oficios.insert_one(oficio_data)
                    reordenar_ids_secuenciales(year)
                    designers = users.find({'role': 'designer'})
                    for designer in designers:
                        notifications.insert_one({
                            'user': designer['username'],
                            'message': f'Tienes una nueva designación pendiente: Oficio {id_secuencial}',
                            'timestamp': datetime.now().isoformat(),
                            'read': False
                        })
                    flash('Oficio registrado exitosamente.', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al registrar oficio: {str(e)}', 'error')
                return redirect(url_for('receive'))

            elif 'edit_oficio' in request.form:
                oficio_id = request.form.get('oficio_id')
                try:
                    # Parsear el formato YYYY-MM-DD del input type="date"
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
                if len(numero_oficio) > 50 or len(detalle) > 10000:
                    flash('Número de oficio o detalle exceden longitud máxima.', 'error')
                    return redirect(url_for('receive'))
                if not re.match(r'^[A-Za-z0-9\-/]+$', numero_oficio):
                    flash('Número de oficio solo puede contener letras, números, guiones y barras.', 'error')
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
                return redirect(url_for('receive'))

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
                return redirect(url_for('receive'))

        return render_template('receive.html',
                               parroquias=parroquias_data,
                               historial=historial,
                               oficios=oficios_list,
                               users=users_list,
                               tipos_asesoria=get_tipos_asesoria())

    except PyMongoError as e:
        flash(f'Error de base de datos: {str(e)}', 'error')
        print(f"Error in receive: {str(e)}")
        return render_template('receive.html',
                               parroquias=parroquias_data if 'parroquias_data' in locals() else [],
                               historial=historial if 'historial' in locals() else [],
                               oficios=oficios_list if 'oficios_list' in locals() else [],
                               users=users_list if 'users_list' in locals() else [],
                               tipos_asesoria=get_tipos_asesoria())
    except Exception as e:
        flash(f'Error inesperado: {str(e)}', 'error')
        print(f"Unexpected error in receive: {str(e)}")
        return render_template('receive.html',
                               parroquias=parroquias_data if 'parroquias_data' in locals() else [],
                               historial=historial if 'historial' in locals() else [],
                               oficios=oficios_list if 'oficios_list' in locals() else [],
                               users=users_list if 'users_list' in locals() else [],
                               tipos_asesoria=get_tipos_asesoria())

@app.route('/seguimiento', methods=['GET'])
@login_required
def seguimiento():
    if current_user.role not in ['receiver', 'admin', 'designer', 'tecnico']:
        return redirect(url_for('login'))
    try:
        oficios_list = list(oficios.find().sort('fecha_recibido', -1))
        users_list = list(users.find({'role': 'tecnico'}, {'username': 1, 'nombre': 1, 'apellido': 1, '_id': 0}))
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
            oficio['assignments'] = assignments

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
    try:
        pendientes = list(oficios.find({'estado': 'pendiente'}).sort('id_secuencial', 1))
        designados = list(oficios.find({'estado': 'designado'}).sort('id_secuencial', 1))
        completados = list(oficios.find({'estado': 'completado'}).sort('id_secuencial', 1))

        for oficio in pendientes + designados + completados:
            oficio['fecha_enviado_traditional'] = format_date_for_traditional(oficio.get('fecha_enviado', ''))
            oficio['fecha_recibido_traditional'] = format_date_for_traditional(oficio.get('fecha_recibido', ''))
            oficio['fecha_designacion_formatted'] = format_date_for_traditional(oficio.get('fecha_designacion', ''))
            if oficio.get('fecha_enviado'):
                try:
                    dt = datetime.fromisoformat(oficio['fecha_enviado'].replace('Z', '+00:00'))
                    oficio['fecha_enviado'] = dt.strftime('%Y-%m-%d')  # ISO for <input type="date">
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

        users_list = list(users.find({'role': 'tecnico'}, {'username': 1, 'nombre': 1, 'apellido': 1, '_id': 0}))
        for user in users_list:
            user['full_name'] = f"{user.get('nombre', '')} {user.get('apellido', '')}".strip() or user['username']

        if request.method == 'POST':
            if 'designar' in request.form:
                oficio_id = request.form.get('oficio_id')
                tecnicos = request.form.getlist('tecnico_asignado[]')
                tipos_asesoria = request.form.getlist('tipo_asesoria[]')
                
                # Filtrar valores vacíos y validar
                tecnicos = [t.strip() for t in tecnicos if t and t.strip()]
                tipos_asesoria = [ta.strip() for ta in tipos_asesoria if ta and ta.strip()]
                
                if not oficio_id or not tecnicos or not tipos_asesoria or len(tecnicos) != len(tipos_asesoria):
                    flash('Debe seleccionar técnicos y tipos de asesoría válidos.', 'danger')
                    return redirect(url_for('design'))
                    
                # Validar que el oficio_id sea un ObjectId válido
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
                    for assignment in assignments:
                        notifications.insert_one({
                            'user': assignment['tecnico'],
                            'message': f'Oficio asignado: {escape(request.form.get("numero_oficio", "Desconocido"))}',
                            'timestamp': datetime.now().isoformat(),
                            'oficio_id': ObjectId(oficio_id),
                            'read': False
                        })
                    flash('Técnico asignado exitosamente.', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al asignar técnico: {str(e)}', 'danger')
                return redirect(url_for('design'))

            elif 'edit_oficio' in request.form:
                oficio_id = request.form.get('oficio_id')
                tecnicos = request.form.getlist('tecnico_asignado[]')
                tipos = request.form.getlist('tipo_asesoria[]')
                
                # Filtrar valores vacíos y validar
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
                    
                # Validar que el oficio_id sea un ObjectId válido
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
                    for assignment in assignments:
                        notifications.insert_one({
                            'user': assignment['tecnico'],
                            'message': f'Oficio actualizado: {escape(request.form.get("numero_oficio", "Desconocido"))}',
                            'timestamp': datetime.now().isoformat(),
                            'oficio_id': ObjectId(oficio_id),
                            'read': False
                        })
                    flash('Oficio actualizado exitosamente.', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al actualizar oficio: {str(e)}', 'danger')
                return redirect(url_for('design'))

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
                return redirect(url_for('design'))

        # Create sorted oficios list for seguimiento
        all_oficios = list(oficios.find().sort('id_secuencial', 1))
        for oficio in all_oficios:
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
                assignment['fecha_asesoria_formatted'] = format_date_for_traditional(assignment.get('fecha_asesoria', ''))
            oficio['assignments'] = assignments
            oficio['_id'] = str(oficio['_id'])

        return render_template('design.html',
                               pendientes=pendientes,
                               designados=designados,
                               completados=completados,
                               oficios=all_oficios,
                               tecnicos=users_list,
                               tipos_asesoria=get_tipos_asesoria(),
                               parroquias=list(parroquias.find()),
                               users=users_list)

    except PyMongoError as e:
        flash(f'Error de base de datos: {str(e)}', 'danger')
        print(f"Error in design: {str(e)}")
        return render_template('design.html',
                               pendientes=[],
                               designados=[],
                               completados=[],
                               oficios=[],
                               tecnicos=users_list if 'users_list' in locals() else [],
                               tipos_asesoria=get_tipos_asesoria(),
                               parroquias=[],
                               users=[])
    except Exception as e:
        flash(f'Error inesperado: {str(e)}', 'danger')
        print(f"Unexpected error in design: {str(e)}")
        return render_template('design.html',
                               pendientes=[],
                               designados=[],
                               completados=[],
                               oficios=[],
                               tecnicos=users_list if 'users_list' in locals() else [],
                               tipos_asesoria=get_tipos_asesoria(),
                               parroquias=[],
                               users=[])

@app.route('/tecnico', methods=['GET', 'POST'])
@login_required
def tecnico():
    if current_user.role not in ['tecnico', 'admin']:
        return redirect(url_for('login'))
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

                if 'anexo' in request.files and request.files['anexo'].filename != '':
                    anexo = request.files['anexo']
                    anexo_nombre = secure_filename(anexo.filename)
                    anexo_id = fs.put(anexo, filename=anexo_nombre)
                    update_data['anexo_nombre'] = anexo_nombre
                    update_data['anexo_id'] = anexo_id

                oficio = oficios.find_one({
                    '_id': ObjectId(oficio_id),
                    'assignments.tecnico': current_user.username
                })
                if not oficio:
                    flash('Oficio no encontrado o no asignado al técnico.', 'danger')
                    return redirect(url_for('tecnico'))

                for assignment in oficio.get('assignments', []):
                    if assignment['tecnico'] == current_user.username:
                        assignment.update(update_data)
                        break

                try:
                    if 'entregar' in request.form:
                        oficios.update_one(
                            {'_id': ObjectId(oficio_id)},
                            {'$set': {'assignments': oficio['assignments'], 'estado': 'completado'}}
                        )
                        flash(f'Asignación {numero_oficio} entregada con éxito.', 'success')
                    else:
                        oficios.update_one(
                            {'_id': ObjectId(oficio_id)},
                            {'$set': {'assignments': oficio['assignments']}}
                        )
                        flash(f'Asignación {numero_oficio} actualizada con éxito.', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al actualizar asignación: {str(e)}', 'danger')

                return redirect(url_for('tecnico'))

        asignados = []
        completados = []
        for oficio in oficios.find({'estado': 'designado'}).sort('fecha_designacion', -1):
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
                               parroquias=list(parroquias.find()))
    except PyMongoError as e:
        flash(f'Error de base de datos: {str(e)}', 'error')
        print(f"Database error in tecnico: {str(e)}")
        return redirect(url_for('tecnico'))
    except Exception as e:
        flash(f'Error inesperado: {str(e)}', 'error')
        print(f"Unexpected error in tecnico: {str(e)}")
        return redirect(url_for('tecnico'))

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
        return send_file(
            BytesIO(anexo_file.read()),
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=anexo_nombre
        )
    except PyMongoError as e:
        return f"Error de base de datos: {str(e)}", 500
    except Exception as e:
        return f"Error retrieving anexo: {str(e)}", 500

@app.route('/download_anexo/<oficio_id>/<int:assignment_index>')
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
        return send_file(
            BytesIO(anexo_file.read()),
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=assignment['anexo_nombre']
        )
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
        current_section = request.args.get('current_section', request.form.get('current_section', 'oficios'))
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
                        'role': request.form['role']
                    })
                    flash('Usuario creado exitosamente', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al crear usuario: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al crear usuario: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section))

            elif 'edit_user' in request.form:
                user_id = request.form['user_id']
                update_data = {
                    'nombre': escape(request.form['nombre']),
                    'apellido': escape(request.form['apellido']),
                    'username': escape(request.form['username']),
                    'role': request.form['role']
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
                return redirect(url_for('admin', current_section=current_section))

            elif 'delete_user' in request.form:
                user_id = request.form['user_id']
                try:
                    users.delete_one({'_id': ObjectId(user_id)})
                    flash('Usuario eliminado exitosamente', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al eliminar usuario: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al eliminar usuario: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section))

            elif 'add_tipo_asesoria' in request.form:
                try:
                    tipos_asesoria_coll.insert_one({'nombre': escape(request.form['nombre'])})
                    flash('Tipo de asesoría añadido exitosamente', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al añadir tipo de asesoría: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al añadir tipo de asesoría: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section))

            elif 'edit_tipo_asesoria' in request.form:
                tipo_id = request.form['tipo_id']
                try:
                    tipos_asesoria_coll.update_one({'_id': ObjectId(tipo_id)}, {'$set': {'nombre': escape(request.form['edit_nombre'])}})
                    flash('Tipo de asesoría actualizado exitosamente', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al actualizar tipo de asesoría: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al actualizar tipo de asesoría: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section))

            elif 'delete_tipo_asesoria' in request.form:
                tipo_id = request.form['tipo_id']
                try:
                    tipos_asesoria_coll.delete_one({'_id': ObjectId(tipo_id)})
                    flash('Tipo de asesoría eliminado exitosamente', 'success')
                except PyMongoError as e:
                    flash(f'Error de base de datos al eliminar tipo de asesoría: {str(e)}', 'error')
                except Exception as e:
                    flash(f'Error al eliminar tipo de asesoría: {str(e)}', 'error')
                return redirect(url_for('admin', current_section=current_section))

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
                return redirect(url_for('admin', current_section=current_section))

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
                return redirect(url_for('admin', current_section=current_section))

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
                return redirect(url_for('admin', current_section=current_section))

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
                return redirect(url_for('admin', current_section=current_section))

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
                return redirect(url_for('admin', current_section=current_section))

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

        users_list = list(users.find({'role': 'tecnico'}, {'username': 1, 'nombre': 1, 'apellido': 1, '_id': 0}))
        for user in users_list:
            user['full_name'] = f"{user.get('nombre', '')} {user.get('apellido', '')}".strip() or user['username']

        return render_template('admin.html',
                               stats=stats,
                               oficios=all_oficios,
                               users=list(users.find()),
                               roles=roles_list,
                               tipos_asesoria=list(tipos_asesoria_coll.find()),
                               parroquias=list(parroquias.find()),
                               tecnicos=users_list,
                               current_section=current_section)
    except PyMongoError as e:
        flash(f'Error de base de datos: {str(e)}', 'error')
        print(f"Database error in admin: {str(e)}")
        return redirect(url_for('admin', current_section=current_section))
    except Exception as e:
        flash(f'Error inesperado: {str(e)}', 'error')
        print(f"Unexpected error in admin: {str(e)}")
        return redirect(url_for('admin', current_section=current_section))

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
                return redirect(url_for('sistemas'))

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
                return redirect(url_for('sistemas'))

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
                return redirect(url_for('sistemas'))

        inventarios = list(db_oficios.inventarios.find())
        for product in inventarios:
            product['_id'] = str(product['_id'])
        tecnicos = list(users.find({'role': 'tecnico'}, {'username': 1, 'nombre': 1, 'apellido': 1, '_id': 0}))
        for user in tecnicos:
            user['full_name'] = f"{user.get('nombre', '')} {user.get('apellido', '')}".strip() or user['username']

        return render_template('sistemas.html',
                               inventarios=inventarios,
                               tecnicos=tecnicos)
    except PyMongoError as e:
        flash(f'Error de base de datos: {str(e)}', 'error')
        print(f"Database error in sistemas: {str(e)}")
        return redirect(url_for('sistemas'))
    except Exception as e:
        flash(f'Error inesperado: {str(e)}', 'error')
        print(f"Unexpected error in sistemas: {str(e)}")
        return redirect(url_for('sistemas'))

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
        
        users_list = list(users.find({'role': 'tecnico'}, {'username': 1, 'nombre': 1, 'apellido': 1, '_id': 0}))
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
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)), debug=True)
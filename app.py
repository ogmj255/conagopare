from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
from datetime import timedelta
from dotenv import load_dotenv
import re
import os
import bcrypt

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

#try:
    #oficios.create_index([('id_secuencial', 1)], unique=True)
    #print("Índice único creado para id_secuencial.")
#except Exception as e:
    #print(f"Error al crear índice: {e}")

try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

def get_tipos_asesoria():
    return [t['nombre'] for t in tipos_asesoria_coll.find()] or ['Asesoría Técnica', 'Inspección', 'Consultoría']
roles_list = ['receiver', 'designer', 'tecnico', 'admin', 'sistemas']

def format_date(iso_date):
    """Format ISO date to a readable string."""
    if iso_date:
        try:
            dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
            return dt.strftime('%d/%m/%Y %I:%M:%S %p')
        except ValueError:
            return iso_date
    return ''

def reordenar_ids_secuenciales(year):
    prefix = f"{year}-"
    all_in_year = list(oficios.find({'id_secuencial': {'$regex': f"^{re.escape(prefix)}"}}).sort('id_secuencial', 1))
    for i, doc in enumerate(all_in_year, 1):
        new_id = f"{prefix}{i:04d}"
        oficios.update_one({'_id': doc['_id']}, {'$set': {'id_secuencial': new_id}})

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

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'receiver':
            return redirect(url_for('receive'))
        elif current_user.role == 'designer':
            return redirect(url_for('design'))
        elif current_user.role == 'tecnico':
            return redirect(url_for('tecnico'))
        elif current_user.role == 'admin':
            return redirect(url_for('admin'))
        elif current_user.role == 'sistemas':
            return redirect(url_for('sistemas'))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
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

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    old_password = request.form.get('old_password').encode('utf-8')
    new_password = request.form.get('new_password').encode('utf-8')
    confirm_password = request.form.get('confirm_password').encode('utf-8')
    
    if not old_password or not new_password or not confirm_password:
        flash('Todos los campos son obligatorios', 'error')
        return redirect(url_for('index'))
    
    user = users.find_one({'username': current_user.username})
    if not user or not bcrypt.checkpw(old_password, user['password']):
        flash('La contraseña anterior es incorrecta', 'error')
    elif new_password != confirm_password:
        flash('Las nuevas contraseñas no coinciden', 'error')
    else:
        hashed_password = bcrypt.hashpw(new_password, bcrypt.gensalt())
        try:
            users.update_one({'username': current_user.username}, {'$set': {'password': hashed_password}})
            flash('Contraseña actualizada exitosamente', 'success')
        except Exception as e:
            flash(f'Error al actualizar contraseña: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/get_notifications', methods=['GET'])
def get_notifications():
    if not current_user.is_authenticated:
        return jsonify({'notifications': [], 'count': 0})
    user_notifications = list(notifications.find({'user': current_user.username, 'read': False}))
    count = len(user_notifications)
    formatted_notifications = [
        {
            'message': n['message'],
            'timestamp': format_date(n['timestamp'])
        } for n in user_notifications
    ]
    return jsonify({'notifications': formatted_notifications, 'count': count})

@app.route('/clear_notifications', methods=['POST'])
def clear_notifications():
    if not current_user.is_authenticated:
        return jsonify({'success': False})
    try:
        notifications.update_many({'user': current_user.username, 'read': False}, {'$set': {'read': True}})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/notificaciones/count')
def notificaciones_count():
    if not current_user.is_authenticated:
        return jsonify({'count': 0})
    count = notifications.count_documents({'user': current_user.username, 'read': False})
    return jsonify({'count': count})

@app.route('/get_canton', methods=['POST'])
def get_canton():
    data = request.get_json()
    parroquia = data.get('parroquia')
    if parroquia:
        parroquia_data = parroquias.find_one({'parroquia': parroquia})
        if parroquia_data:
            return jsonify({'canton': parroquia_data.get('canton', '')})
    return jsonify({'canton': ''})

@app.route('/receive', methods=['GET', 'POST'])
@login_required
def receive():
    if current_user.role not in ['receiver', 'admin']:
        return redirect(url_for('login'))
    parroquias_data = list(parroquias.find())
    if not parroquias_data:
        flash('No se encontraron parroquias en la base de datos. Contacte al administrador.', 'warning')
        print("Advertencia: la colección 'parroquias' está vacía.")
    
    historial = list(oficios.find({'fecha_recibido': {'$exists': True}}).sort('fecha_recibido', -1))
    for oficio in historial:
        oficio['fecha_enviado_formatted'] = format_date(oficio.get('fecha_enviado'))
        oficio['fecha_recibido_formatted'] = format_date(oficio.get('fecha_recibido'))
    users_list = list(users.find())
    
    if request.method == 'POST':
        if 'register_oficio' in request.form:
            fecha_enviado = request.form.get('fecha_enviado')
            numero_oficio = request.form.get('numero_oficio')
            gad_parroquial = request.form.get('gad_parroquial')
            canton = request.form.get('canton')
            detalle = request.form.get('detalle', '')

            if not all([fecha_enviado, numero_oficio, gad_parroquial, canton]):
                flash('Todos los campos obligatorios deben completarse.', 'error')
                return redirect(url_for('receive'))
            if len(numero_oficio) > 50 or len(detalle) > 10000:
                flash('Número de oficio o detalle exceden longitud máxima.', 'error')
                return redirect(url_for('receive'))
            if not re.match(r'^[A-Za-z0-9\-/]+$', numero_oficio):
                flash('Número de oficio solo puede contener letras, números, guiones y barras.', 'error')
                return redirect(url_for('receive'))

            try:
                year = fecha_enviado.split('-')[0]
                max_id_doc = oficios.find_one({'id_secuencial': {'$regex': f'^{year}-'}}, sort=[('id_secuencial', -1)])
                count = int(max_id_doc['id_secuencial'].split('-')[1]) + 1 if max_id_doc else 1
                id_secuencial = f"{year}-{str(count).zfill(4)}"

                oficio = {
                    'id_secuencial': id_secuencial,
                    'fecha_enviado': fecha_enviado,
                    'numero_oficio': numero_oficio,
                    'gad_parroquial': gad_parroquial,
                    'canton': canton,
                    'detalle': detalle,
                    'fecha_recibido': datetime.now().isoformat(),
                    'estado': 'pendiente',
                    'assignments': [],
                    'fecha_designacion': None,
                    'desarrollo_actividad': None,
                    'fecha_asesoria': None,
                    'sub_estado': None,
                    'entrega_recepcion': None
                }
                oficios.insert_one(oficio)
                
                designers = users.find({'role': 'designer'})
                for designer in designers:
                    notifications.insert_one({
                        'user': designer['username'],
                        'message': f'Tienes una nueva designación pendiente: Oficio {id_secuencial}',
                        'timestamp': datetime.now().isoformat(),
                        'read': False
                    })
                
                flash('Oficio registrado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al registrar oficio: {str(e)}', 'error')
            return redirect(url_for('receive'))

        elif 'edit_oficio' in request.form:
            oficio_id = request.form.get('oficio_id')
            fecha_enviado = request.form.get('fecha_enviado')
            numero_oficio = request.form.get('numero_oficio')
            gad_parroquial = request.form.get('gad_parroquial')
            canton = request.form.get('canton')
            detalle = request.form.get('detalle', '')

            if not all([oficio_id, fecha_enviado, numero_oficio, gad_parroquial, canton]):
                flash('Todos los campos obligatorios deben completarse.', 'error')
                return redirect(url_for('receive'))
            if len(numero_oficio) > 50 or len(detalle) > 1000:
                flash('Número de oficio o detalle exceden longitud máxima.', 'error')
                return redirect(url_for('receive'))
            if not re.match(r'^[A-Za-z0-9\-/]+$', numero_oficio):
                flash('Número de oficio solo puede contener letras, números, guiones y barras.', 'error')
                return redirect(url_for('receive'))

            try:
                tecnicos = request.form.getlist('tecnico_asignado[]')
                tipos = request.form.getlist('tipo_asesoria[]')
                assignments = []
                for tec, tipo in zip(tecnicos, tipos):
                    if tec and tipo:
                        assignments.append({'tecnico': tec, 'tipo_asesoria': tipo})

                result = oficios.update_one(
                    {'_id': ObjectId(oficio_id)},
                    {'$set': {
                        'fecha_enviado': fecha_enviado,
                        'numero_oficio': numero_oficio,
                        'gad_parroquial': gad_parroquial,
                        'canton': canton,
                        'detalle': detalle,
                        'assignments': assignments
                    }}
                )
                if result.matched_count == 0:
                    flash('Oficio no encontrado.', 'error')
                else:
                    flash('Oficio actualizado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al actualizar oficio: {str(e)}', 'error')
            return redirect(url_for('receive'))

        elif 'delete_oficio' in request.form:
            oficio_id = request.form.get('delete_oficio')
            try:
                deleted_oficio = oficios.find_one({'_id': ObjectId(oficio_id)})
                if deleted_oficio:
                    year = deleted_oficio['id_secuencial'].split('-')[0]
                    oficios.delete_one({'_id': ObjectId(oficio_id)})
                    reordenar_ids_secuenciales(year)
                    flash('Oficio eliminado y IDs reordenados exitosamente', 'success')
                else:
                    flash('Oficio no encontrado.', 'error')
            except Exception as e:
                flash(f'Error al eliminar oficio: {str(e)}', 'error')
            return redirect(url_for('receive'))

    return render_template('receive.html',
        parroquias=parroquias_data,
        historial=historial,
        users=users_list)

@app.route('/design', methods=['GET', 'POST'])
@login_required
def design():
    if current_user.role not in ['designer', 'admin']:
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'designar_oficio' in request.form:
            oficio_id = request.form.get('oficio_id')
            tecnicos = request.form.getlist('tecnico_asignado[]')
            tipos = request.form.getlist('tipo_asesoria[]')

            if not oficio_id or not tecnicos or not tipos:
                flash('Debe completar todos los campos requeridos.', 'error')
                return redirect(url_for('design'))
            if len(tecnicos) != len(tipos):
                flash('El número de técnicos y tipos de asesoría no coincide.', 'error')
                return redirect(url_for('design'))
            if any(not t or not tipo for t, tipo in zip(tecnicos, tipos)):
                flash('Seleccione un técnico y tipo de asesoría válidos.', 'error')
                return redirect(url_for('design'))

            try:
                numero_oficio = request.form.get('numero_oficio', 'Desconocido')
                assignments = [{'tecnico': t, 'tipo_asesoria': tipos[i]} for i, t in enumerate(tecnicos) if t]
                oficios.update_one(
                    {'_id': ObjectId(oficio_id)},
                    {
                        '$set': {
                            'assignments': assignments,
                            'estado': 'designado',
                            'fecha_designacion': datetime.now().isoformat()
                        }
                    }
                )
                for assignment in assignments:
                    notifications.insert_one({
                        'user': assignment['tecnico'],
                        'message': f'Nuevo oficio asignado: {numero_oficio}',
                        'timestamp': datetime.now().isoformat(),
                        'oficio_id': ObjectId(oficio_id),
                        'read': False
                    })
                flash('Oficio designado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al designar oficio: {str(e)}', 'error')
            return redirect(url_for('design'))
        
        elif 'edit_oficio' in request.form:
            oficio_id = request.form.get('oficio_id')
            tecnicos = request.form.getlist('tecnico_asignado[]')
            tipos = request.form.getlist('tipo_asesoria[]')

            if not oficio_id or not tecnicos or not tipos:
                flash('Debe completar todos los campos requeridos.', 'error')
                return redirect(url_for('design'))
            if len(tecnicos) != len(tipos):
                flash('El número de técnicos y tipos de asesoría no coincide.', 'error')
                return redirect(url_for('design'))
            if any(not t or not tipo for t, tipo in zip(tecnicos, tipos)):
                flash('Seleccione un técnico y tipo de asesoría válidos.', 'error')
                return redirect(url_for('design'))

            try:
                numero_oficio = request.form.get('numero_oficio', 'Desconocido')
                assignments = [{'tecnico': t, 'tipo_asesoria': tipos[i]} for i, t in enumerate(tecnicos) if t]
                oficios.update_one({'_id': ObjectId(oficio_id)}, {
                    '$set': {
                        'assignments': assignments,
                        'fecha_designacion': datetime.now().isoformat()
                    }
                })
                notifications.delete_many({'oficio_id': ObjectId(oficio_id)})
                for assignment in assignments:
                    notifications.insert_one({
                        'user': assignment['tecnico'],
                        'message': f'Oficio actualizado: {numero_oficio}',
                        'timestamp': datetime.now().isoformat(),
                        'oficio_id': ObjectId(oficio_id),
                        'read': False
                    })
                flash('Oficio actualizado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al actualizar oficio: {str(e)}', 'error')
            return redirect(url_for('design'))
        
        elif 'delete_oficio' in request.form:
            oficio_id = request.form.get('oficio_id')
            try:
                deleted_oficio = oficios.find_one({'_id': ObjectId(oficio_id)})
                if deleted_oficio:
                    year = deleted_oficio['id_secuencial'].split('-')[0]
                    oficios.delete_one({'_id': ObjectId(oficio_id)})
                    reordenar_ids_secuenciales(year)
                    notifications.delete_many({'oficio_id': ObjectId(oficio_id)})
                    flash('Oficio eliminado y IDs reordenados exitosamente', 'success')
                else:
                    flash('Oficio no encontrado.', 'error')
            except Exception as e:
                flash(f'Error al eliminar oficio: {str(e)}', 'error')
            return redirect(url_for('design'))

    pendientes = list(oficios.find({'estado': 'pendiente'}).sort('fecha_enviado', -1))
    designados = list(oficios.find({'estado': 'designado'}).sort('fecha_designacion', -1))
    for oficio in pendientes + designados:
        oficio['fecha_enviado_formatted'] = format_date(oficio.get('fecha_enviado'))
        oficio['fecha_designacion'] = oficio.get('fecha_designacion', '')
        oficio['fecha_designacion_formatted'] = format_date(oficio.get('fecha_designacion', ''))

    return render_template('design.html',
        pendientes=pendientes,
        designados=designados,
        tecnicos=[u['username'] for u in users.find({'role': 'tecnico'})],
        tipos=get_tipos_asesoria(),
        parroquias=list(parroquias.find()))

@app.route('/tecnico', methods=['GET', 'POST'])
@login_required
def tecnico():
    if current_user.role not in ['tecnico', 'admin']:
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'actualizar' in request.form:
            oficio_id = request.form['oficio_id']
            try:
                oficios.update_one(
                    {'_id': ObjectId(oficio_id), 'assignments.tecnico': current_user.username},
                    {
                        '$set': {
                            'assignments.$.sub_estado': request.form['sub_estado'],
                            'assignments.$.desarrollo_actividad': request.form['desarrollo_actividad'],
                            'assignments.$.fecha_asesoria': request.form['fecha_asesoria'],
                            'assignments.$.entrega_recepcion': request.form['entrega_recepcion'],
                            'assignments.$.oficio_delegacion': request.form.get('oficio_delegacion', ''),
                            'assignments.$.acta_entrega': request.form.get('acta_entrega', '')
                        }
                    }
                )
                flash('Asignación actualizada exitosamente', 'success')
            except Exception as e:
                flash(f'Error al actualizar asignación: {str(e)}', 'error')

        elif 'entregar' in request.form:
            oficio_id = request.form['oficio_id']
            try:
                oficios.update_one(
                    {'_id': ObjectId(oficio_id), 'assignments.tecnico': current_user.username},
                    {
                        '$set': {
                            'assignments.$.sub_estado': 'Concluido',
                            'assignments.$.desarrollo_actividad': request.form['desarrollo_actividad'],
                            'assignments.$.fecha_asesoria': request.form['fecha_asesoria'],
                            'assignments.$.entrega_recepcion': request.form['entrega_recepcion'],
                            'assignments.$.oficio_delegacion': request.form.get('oficio_delegacion', ''),
                            'assignments.$.acta_entrega': request.form.get('acta_entrega', '')
                        }
                    }
                )
                notifications.insert_one({
                    'user': 'admin',
                    'message': f'Oficio entregado por {current_user.username}: {request.form["numero_oficio"]}',
                    'timestamp': datetime.now().isoformat(),
                    'oficio_id': ObjectId(oficio_id),
                    'read': False
                })
                flash('Oficio entregado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al entregar oficio: {str(e)}', 'error')

        elif 'create_user' in request.form and current_user.role == 'admin':
            try:
                users.insert_one({
                    'username': request.form['new_username'],
                    'password': request.form['new_password'],
                    'role': 'tecnico',
                    'full_name': request.form['new_username']
                })
                flash('Usuario creado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al crear usuario: {str(e)}', 'error')

        elif 'edit_user' in request.form and current_user.role == 'admin':
            user_id = request.form['user_id']
            update_data = {'username': request.form['edit_username']}
            if request.form['edit_password']:
                update_data['password'] = request.form['edit_password']
            try:
                users.update_one({'_id': ObjectId(user_id)}, {'$set': update_data})
                flash('Usuario actualizado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al actualizar usuario: {str(e)}', 'error')

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
                    'fecha_designacion_formatted': format_date(oficio.get('fecha_designacion', '')),
                    'sub_estado': assignment.get('sub_estado', 'Asignado'),
                    'desarrollo_actividad': assignment.get('desarrollo_actividad', ''),
                    'fecha_asesoria': assignment.get('fecha_asesoria', ''),
                    'fecha_asesoria_formatted': format_date(assignment.get('fecha_asesoria', '')),
                    'entrega_recepcion': assignment.get('entrega_recepcion', 'No Aplica'),
                    'oficio_delegacion': assignment.get('oficio_delegacion', ''),
                    'acta_entrega': assignment.get('acta_entrega', '')
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

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'create_user' in request.form:
            try:
                username = request.form['username']
                password = request.form['password'].encode('utf-8')
                hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
                users.insert_one({
                    'nombre': request.form['nombre'],
                    'apellido': request.form['apellido'],
                    'username': username,
                    'password': hashed_password,
                    'role': request.form['role']
                })
                flash('Usuario creado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al crear usuario: {str(e)}', 'error')
        
        elif 'edit_user' in request.form:
            user_id = request.form['user_id']
            update_data = {
                'nombre': request.form['nombre'],
                'apellido': request.form['apellido'],
                'username': request.form['username'],
                'role': request.form['role']
            }
            if request.form['password']:
                password = request.form['password'].encode('utf-8')
                update_data['password'] = bcrypt.hashpw(password, bcrypt.gensalt())
            try:
                users.update_one({'_id': ObjectId(user_id)}, {'$set': update_data})
                flash('Usuario actualizado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al actualizar usuario: {str(e)}', 'error')
        
        elif 'delete_user' in request.form:
            user_id = request.form['user_id']
            try:
                users.delete_one({'_id': ObjectId(user_id)})
                flash('Usuario eliminado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al eliminar usuario: {str(e)}', 'error')
        
        elif 'add_tipo_asesoria' in request.form:
            try:
                tipos_asesoria_coll.insert_one({'nombre': request.form['nombre']})
                flash('Tipo de asesoría añadido exitosamente', 'success')
            except Exception as e:
                flash(f'Error al añadir tipo de asesoría: {str(e)}', 'error')
        
        elif 'edit_tipo_asesoria' in request.form:
            tipo_id = request.form['tipo_id']
            try:
                tipos_asesoria_coll.update_one({'_id': ObjectId(tipo_id)}, {'$set': {'nombre': request.form['edit_nombre']}})
                flash('Tipo de asesoría actualizado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al actualizar tipo de asesoría: {str(e)}', 'error')
        
        elif 'delete_tipo_asesoria' in request.form:
            tipo_id = request.form['tipo_id']
            try:
                tipos_asesoria_coll.delete_one({'_id': ObjectId(tipo_id)})
                flash('Tipo de asesoría eliminado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al eliminar tipo de asesoría: {str(e)}', 'error')
        
        elif 'add_parroquia' in request.form:
            try:
                parroquias.insert_one({
                    'parroquia': request.form['parroquia'],
                    'canton': request.form['canton']
                })
                flash('Parroquia añadida exitosamente', 'success')
            except Exception as e:
                flash(f'Error al añadir parroquia: {str(e)}', 'error')
        
        elif 'delete_parroquia' in request.form:
            parroquia_id = request.form['parroquia_id']
            try:
                result = parroquias.delete_one({'_id': ObjectId(parroquia_id)})
                if result.deleted_count > 0:
                    flash('Parroquia eliminada exitosamente', 'success')
                else:
                    flash('No se encontró la parroquia para eliminar', 'error')
            except Exception as e:
                flash(f'Error al eliminar parroquia: {str(e)}', 'error')

        elif 'edit_parroquia' in request.form:
            parroquia_id = request.form['parroquia_id']
            try:
                parroquias.update_one({'_id': ObjectId(parroquia_id)}, {
                    '$set': {
                        'parroquia': request.form['edit_parroquia'],
                        'canton': request.form['edit_canton']
                    }
                })
                flash('Parroquia actualizada exitosamente', 'success')
            except Exception as e:
                flash(f'Error al actualizar parroquia: {str(e)}', 'error')
                
        elif 'edit_oficio' in request.form:
            oficio_id = request.form['oficio_id']
            tecnicos = request.form.getlist('tecnico_asignado[]')
            tipos = request.form.getlist('tipo_asesoria[]')
            assignments = [{'tecnico': t, 'tipo_asesoria': tipos[i]} for i, t in enumerate(tecnicos) if t]
            
            try:
                oficios.update_one({'_id': ObjectId(oficio_id)}, {
                    '$set': {
                        'assignments': assignments
                    }
                })
                flash('Oficio actualizado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al actualizar oficio: {str(e)}', 'error')
        
        elif 'delete_oficio' in request.form:
            oficio_id = request.form['oficio_id']
            try:
                deleted_oficio = oficios.find_one({'_id': ObjectId(oficio_id)})
                if deleted_oficio:
                    year = deleted_oficio['id_secuencial'].split('-')[0]
                    oficios.delete_one({'_id': ObjectId(oficio_id)})
                    reordenar_ids_secuenciales(year)
                    notifications.delete_many({'oficio_id': ObjectId(oficio_id)})
                    flash('Oficio eliminado y IDs reordenados exitosamente', 'success')
                else:
                    flash('Oficio no encontrado.', 'error')
            except Exception as e:
                flash(f'Error al eliminar oficio: {str(e)}', 'error')
    
    stats = {
        'pendientes': oficios.count_documents({'estado': 'pendiente'}),
        'designados': oficios.count_documents({'estado': 'designado'}),
        'completados': oficios.count_documents({'estado': 'completado'})
    }
    all_oficios = list(oficios.find().sort('fecha_recibido', -1))
    for oficio in all_oficios:
        oficio['fecha_recibido_formatted'] = format_date(oficio.get('fecha_recibido'))
        oficio['fecha_enviado_formatted'] = format_date(oficio.get('fecha_enviado'))
        oficio['fecha_designacion_formatted'] = format_date(oficio.get('fecha_designacion', ''))
        oficio['assignments'] = oficio.get('assignments', [])
    
    return render_template('admin.html',
        stats=stats,
        oficios=all_oficios,
        users=list(users.find()),
        roles=roles_list,
        tipos_asesoria=list(tipos_asesoria_coll.find()),
        parroquias=list(parroquias.find()))

@app.route('/sistemas', methods=['GET', 'POST'])
@login_required
def sistemas():
    if current_user.role not in ['admin', 'sistemas']:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'add_product' in request.form:
            codigo = request.form.get('codigo', '')
            tipo = request.form.get('tipo', '')
            color = request.form.get('color', '')
            marca = request.form.get('marca', '')
            modelo = request.form.get('modelo', '')
            estado = request.form.get('estado', '')
            detalle = request.form.get('detalle', '')
            asignar_tecnico = request.form.get('asignar_tecnico', 'no')
            tecnico = None
            if asignar_tecnico == 'sí':
                tecnico = request.form.get('tecnico', '')
            
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
            db_oficios.inventarios.insert_one(product)
            flash('Producto agregado exitosamente', 'success')

        elif 'edit_product' in request.form:
            product_id = request.form.get('product_id', '')
            codigo = request.form.get('codigo', '')
            tipo = request.form.get('tipo', '')
            color = request.form.get('color', '')
            marca = request.form.get('marca', '')
            modelo = request.form.get('modelo', '')
            estado = request.form.get('estado', '')
            detalle = request.form.get('detalle', '')
            asignar_tecnico = request.form.get('asignar_tecnico', 'no')
            tecnico = None
            if asignar_tecnico == 'sí':
                tecnico = request.form.get('tecnico', '')

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
            if len(codigo) > 50 or len(marca) > 100 or len(modelo) > 100 or len(detalle) > 500:
                flash('Los campos exceden los límites de longitud.', 'error')
                return redirect(url_for('sistemas'))

            if not re.match(r'^[A-Za-z0-9\-]+$', codigo):
                flash('El código solo puede contener letras, números y guiones.', 'error')
                return redirect(url_for('sistemas'))

            if 'imagen' in request.files:
                file = request.files['imagen']
                if file and file.filename:
                    allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif'}
                    if os.path.splitext(file.filename)[1].lower() in allowed_extensions:
                        filename = secure_filename(file.filename)
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                        update_data['imagen'] = filename
                    else:
                        flash('Solo se permiten imágenes (PNG, JPG, JPEG, GIF).', 'error')
                        return redirect(url_for('sistemas'))

            db_oficios.inventarios.update_one({'_id': ObjectId(product_id)}, {'$set': update_data})
            flash('Producto actualizado exitosamente', 'success')

        elif 'delete_product' in request.form:
            product_id = request.form.get('product_id', '')
            product = db_oficios.inventarios.find_one({'_id': ObjectId(product_id)})
            if product and product.get('imagen'):
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], product['imagen']))
                except OSError:
                    pass
            db_oficios.inventarios.delete_one({'_id': ObjectId(product_id)})
            flash('Producto eliminado exitosamente', 'success')

    inventarios = list(db_oficios.inventarios.find())
    for product in inventarios:
        product['_id'] = str(product['_id'])
    tecnicos = list(db_oficios.users_db.find({'role': 'tecnico'}, {'username': 1, 'nombre': 1, 'apellido': 1}))

    return render_template('sistemas.html', inventarios=inventarios, tecnicos=tecnicos)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)), debug=True)
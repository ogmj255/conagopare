from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId
import re

app = Flask(__name__)
app.secret_key = 'your_secret_key'

client = MongoClient('mongodb://localhost:27017/')
db_oficios = client['conagoparedb']
oficios = db_oficios['oficios']
parroquias = db_oficios['parroquias']
users = db_oficios['users_db']
notifications = db_oficios['notifications']

tipos_asesoria = ['Asesoría Técnica', 'Inspección', 'Consultoría']
roles_list = ['receiver', 'designer', 'tecnico', 'admin']

def format_date(iso_date):
    """Format ISO date to a readable string."""
    if iso_date:
        try:
            dt = datetime.fromisoformat(iso_date)
            return dt.strftime('%m/%d/%Y %I:%M:%S %p')
        except ValueError:
            return iso_date
    return ''

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users.find_one({'username': username, 'password': password})
        if user:
            session['user'] = username
            session['role'] = user['role']
            flash('Login exitoso', 'success')
            if session['role'] == 'receiver':
                return redirect(url_for('receive'))
            elif session['role'] == 'designer':
                return redirect(url_for('design'))
            elif session['role'] == 'tecnico':
                return redirect(url_for('tecnico'))
            elif session['role'] == 'admin':
                return redirect(url_for('admin'))
        else:
            flash('Login fallido. Usuario o contraseña incorrectos.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('role', None)
    flash('Sesión cerrada exitosamente', 'success')
    return redirect(url_for('login'))

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    old_password = request.form.get('old_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not old_password or not new_password or not confirm_password:
        flash('Todos los campos son obligatorios', 'error')
        role = session['role']
        if role == 'receiver':
            return redirect(url_for('receive'))
        elif role == 'designer':
            return redirect(url_for('design'))
        elif role == 'tecnico':
            return redirect(url_for('tecnico'))
        elif role == 'admin':
            return redirect(url_for('admin'))
    
    user = users.find_one({'username': session['user'], 'password': old_password})
    if not user:
        flash('La contraseña anterior es incorrecta', 'error')
    elif new_password != confirm_password:
        flash('Las nuevas contraseñas no coinciden', 'error')
    else:
        try:
            users.update_one({'username': session['user']}, {'$set': {'password': new_password}})
            flash('Contraseña actualizada exitosamente', 'success')
        except Exception as e:
            flash(f'Error al actualizar contraseña: {str(e)}', 'error')
    
    role = session['role']
    if role == 'receiver':
        return redirect(url_for('receive'))
    elif role == 'designer':
        return redirect(url_for('design'))
    elif role == 'tecnico':
        return redirect(url_for('tecnico'))
    elif role == 'admin':
        return redirect(url_for('admin'))

@app.route('/get_notifications', methods=['GET'])
def get_notifications():
    if 'user' not in session:
        return jsonify({'notifications': [], 'count': 0})
    user_notifications = list(notifications.find({'user': session['user'], 'read': False}))
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
    if 'user' not in session:
        return jsonify({'success': False})
    try:
        notifications.update_many({'user': session['user'], 'read': False}, {'$set': {'read': True}})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get_canton', methods=['POST'])
def get_canton():
    parroquia = request.json.get('parroquia', '')
    mapping = parroquias.find_one({'parroquia': parroquia})
    canton = mapping['canton'] if mapping else 'Desconocido'
    return jsonify({'canton': canton})

@app.route('/receive', methods=['GET', 'POST'])
def receive():
    if 'role' not in session or session['role'] != 'receiver':
        return redirect(url_for('login'))
    
    historial = list(oficios.find().sort('id_secuencial', -1))
    for h in historial:
        h['fecha_recibido_formatted'] = format_date(h.get('fecha_recibido'))
        h['fecha_enviado_formatted'] = format_date(h.get('fecha_enviado'))
    parroquias_list = sorted([p['parroquia'] for p in parroquias.find()])
    users_list = list(users.find())
    
    if request.method == 'POST':
        if 'create_user' in request.form:
            username = request.form['new_username']
            password = request.form['new_password']
            if users.find_one({'username': username}):
                flash('Usuario ya existe', 'error')
            else:
                try:
                    users.insert_one({'username': username, 'password': password, 'role': 'tecnico'})
                    flash('Usuario creado exitosamente', 'success')
                except Exception as e:
                    flash(f'Error al crear usuario: {str(e)}', 'error')
        elif 'edit_user' in request.form:
            user_id = ObjectId(request.form['user_id'])
            update = {'$set': {'username': request.form['edit_username']}}
            if request.form.get('edit_password'):
                update['$set']['password'] = request.form['edit_password']
            try:
                users.update_one({'_id': user_id}, update)
                flash('Usuario actualizado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al actualizar usuario: {str(e)}', 'error')
        elif 'delete_oficio' in request.form:
            oficio_id = ObjectId(request.form['oficio_id'])
            oficio = oficios.find_one({'_id': oficio_id})
            if oficio:
                try:
                    prefix = oficio['id_secuencial'].split('-')[0] + '-'
                    oficios.delete_one({'_id': oficio_id})
                    all_in_year = list(oficios.find({'id_secuencial': {'$regex': f"^{re.escape(prefix)}"}}).sort('id_secuencial', 1))
                    for i, doc in enumerate(all_in_year, 1):
                        new_id = f"{prefix}{i:04d}"
                        oficios.update_one({'_id': doc['_id']}, {'$set': {'id_secuencial': new_id}})
                    flash('Registro eliminado y IDs actualizados exitosamente', 'success')
                except Exception as e:
                    flash(f'Error al eliminar registro o actualizar IDs: {str(e)}', 'error')
        elif 'edit_oficio' in request.form:
            oficio_id = ObjectId(request.form['oficio_id'])
            update_data = {
                '$set': {
                    'fecha_enviado': request.form['edit_fecha_enviado'],
                    'numero_oficio': request.form['edit_numero_oficio'],
                    'gad_parroquial': request.form['edit_gad_parroquial'],
                    'canton': request.form['edit_canton'],
                    'detalle': request.form['edit_detalle']
                }
            }
            try:
                oficios.update_one({'_id': oficio_id}, update_data)
                flash('Registro actualizado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al actualizar registro: {str(e)}', 'error')
        else:
            current_year = datetime.now().year
            prefix = f"{current_year}-"
            max_oficio = oficios.find_one({'id_secuencial': {'$regex': f"^{re.escape(prefix)}"}}, sort=[('id_secuencial', -1)])
            if max_oficio:
                num = int(max_oficio['id_secuencial'].split('-')[1]) + 1
            else:
                num = 1
            next_id = f"{prefix}{num:04d}"
            data = {
                'id_secuencial': next_id,
                'fecha_enviado': request.form['fecha_oficio'],
                'fecha_recibido': datetime.now().isoformat(),
                'numero_oficio': request.form['numero_oficio'],
                'gad_parroquial': request.form['gad_parroquial'],
                'canton': request.form['canton'],
                'detalle': request.form['detalle'],
                'estado': 'pendiente',
                'tecnico_asignado': None,
                'tipo_asesoria': None,
                'fecha_designacion': None,
                'desarrollo_actividad': None,
                'fecha_asesoria': None,
                'sub_estado': None,
                'entrega_recepcion': None
            }
            try:
                oficios.insert_one(data)
                # Notify all designers
                designers = users.find({'role': 'designer'})
                for designer in designers:
                    notifications.insert_one({
                        'user': designer['username'],
                        'message': f'Tienes una nueva designación pendiente: Oficio {next_id}',
                        'timestamp': datetime.now().isoformat(),
                        'read': False
                    })
                flash('Registro creado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al crear registro: {str(e)}', 'error')
        return redirect(url_for('receive'))
    return render_template('receive.html', historial=historial, parroquias=parroquias_list, users=users_list)

@app.route('/design', methods=['GET', 'POST'])
def design():
    if 'role' not in session or session['role'] != 'designer':
        return redirect(url_for('login'))
    pendientes = list(oficios.find({'estado': 'pendiente'}))
    designados = list(oficios.find({'estado': 'designado'}))
    for p in pendientes + designados:
        p['fecha_designacion_formatted'] = format_date(p.get('fecha_designacion'))
        # Ensure tecnico_asignado is a list for display
        if isinstance(p.get('tecnico_asignado'), str):
            p['tecnico_asignado'] = [p['tecnico_asignado']] if p['tecnico_asignado'] else []
        elif p.get('tecnico_asignado') is None:
            p['tecnico_asignado'] = []
    tecnicos_list = sorted([u['username'] for u in users.find({'role': 'tecnico'})])
    users_list = list(users.find())
    if request.method == 'POST':
        if 'create_user' in request.form:
            username = request.form['new_username']
            password = request.form['new_password']
            if users.find_one({'username': username}):
                flash('Usuario ya existe', 'error')
            else:
                try:
                    users.insert_one({'username': username, 'password': password, 'role': 'tecnico'})
                    flash('Usuario creado exitosamente', 'success')
                except Exception as e:
                    flash(f'Error al crear usuario: {str(e)}', 'error')
        elif 'edit_user' in request.form:
            user_id = ObjectId(request.form['user_id'])
            update = {'$set': {'username': request.form['edit_username']}}
            if request.form.get('edit_password'):
                update['$set']['password'] = request.form['edit_password']
            try:
                users.update_one({'_id': user_id}, update)
                flash('Usuario actualizado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al actualizar usuario: {str(e)}', 'error')
        elif 'delete_oficio' in request.form:
            oficio_id = ObjectId(request.form['oficio_id'])
            oficio = oficios.find_one({'_id': oficio_id})
            if oficio:
                try:
                    prefix = oficio['id_secuencial'].split('-')[0] + '-'
                    oficios.delete_one({'_id': oficio_id})
                    all_in_year = list(oficios.find({'id_secuencial': {'$regex': f"^{re.escape(prefix)}"}}).sort('id_secuencial', 1))
                    for i, doc in enumerate(all_in_year, 1):
                        new_id = f"{prefix}{i:04d}"
                        oficios.update_one({'_id': doc['_id']}, {'$set': {'id_secuencial': new_id}})
                    flash('Registro eliminado y IDs actualizados exitosamente', 'success')
                except Exception as e:
                    flash(f'Error al eliminar registro o actualizar IDs: {str(e)}', 'error')
        elif 'edit_oficio' in request.form:
            oficio_id = ObjectId(request.form['oficio_id'])
            tecnicos = request.form.getlist('edit_tecnico_asignado[]')
            tipo_asesoria = request.form.get('edit_tipo_asesoria')
            update_data = {
                '$set': {
                    'tecnico_asignado': tecnicos if tecnicos and 'Ninguno' not in tecnicos else [],
                    'tipo_asesoria': tipo_asesoria if tipo_asesoria != 'Ninguno' else None
                }
            }
            try:
                oficios.update_one({'_id': oficio_id}, update_data)
                flash('Registro actualizado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al actualizar registro: {str(e)}', 'error')
        else:
            oficio_id = ObjectId(request.form['oficio_id'])
            tecnicos = request.form.getlist('tecnico_asignado[]')
            tipo = request.form['tipo_asesoria']
            if tecnicos and 'Ninguno' not in tecnicos and tipo != 'Ninguno':
                update_data = {
                    '$set': {
                        'tecnico_asignado': tecnicos,
                        'tipo_asesoria': tipo,
                        'fecha_designacion': datetime.now().isoformat(),
                        'estado': 'designado',
                        'sub_estado': 'en_proceso'
                    }
                }
                try:
                    oficios.update_one({'_id': oficio_id}, update_data)
                    # Notify all assigned tecnicos
                    oficio = oficios.find_one({'_id': oficio_id})
                    for tecnico in tecnicos:
                        notifications.insert_one({
                            'user': tecnico,
                            'message': f'Tienes una nueva asignación pendiente: Oficio {oficio["id_secuencial"]}',
                            'timestamp': datetime.now().isoformat(),
                            'read': False
                        })
                    flash('Designación exitosa', 'success')
                except Exception as e:
                    flash(f'Error al designar: {str(e)}', 'error')
            else:
                flash('Seleccione al menos un técnico y tipo de asesoría', 'error')
        return redirect(url_for('design'))
    return render_template('design.html', pendientes=pendientes, designados=designados, tecnicos=tecnicos_list, tipos=tipos_asesoria, users=users_list)

@app.route('/tecnico', methods=['GET', 'POST'])
def tecnico():
    if 'role' not in session or session['role'] != 'tecnico':
        return redirect(url_for('login'))
    username = session['user']
    asignados = list(oficios.find({'tecnico_asignado': {'$in': [username]}, 'sub_estado': 'en_proceso'}))
    completados = list(oficios.find({'tecnico_asignado': {'$in': [username]}, 'sub_estado': 'finalizado'}))
    for c in completados:
        c['fecha_asesoria_formatted'] = format_date(c.get('fecha_asesoria'))
    users_list = list(users.find())
    if request.method == 'POST':
        if 'create_user' in request.form:
            username = request.form['new_username']
            password = request.form['new_password']
            if users.find_one({'username': username}):
                flash('Usuario ya existe', 'error')
            else:
                try:
                    users.insert_one({'username': username, 'password': password, 'role': 'tecnico'})
                    flash('Usuario creado exitosamente', 'success')
                except Exception as e:
                    flash(f'Error al crear usuario: {str(e)}', 'error')
        elif 'edit_user' in request.form:
            user_id = ObjectId(request.form['user_id'])
            update = {'$set': {'username': request.form['edit_username']}}
            if request.form.get('edit_password'):
                update['$set']['password'] = request.form['edit_password']
            try:
                users.update_one({'_id': user_id}, update)
                flash('Usuario actualizado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al actualizar usuario: {str(e)}', 'error')
        else:
            oficio_id = ObjectId(request.form['oficio_id'])
            update_data = {
                '$set': {
                    'desarrollo_actividad': request.form['desarrollo_actividad'],
                    'fecha_asesoria': request.form['fecha_asesoria'],
                    'sub_estado': request.form['sub_estado'],
                    'entrega_recepcion': request.form['entrega_recepcion']
                }
            }
            try:
                oficios.update_one({'_id': oficio_id}, update_data)
                flash('Actualización exitosa', 'success')
            except Exception as e:
                flash(f'Error al actualizar: {str(e)}', 'error')
        return redirect(url_for('tecnico'))
    return render_template('tecnico.html', asignados=asignados, completados=completados, users=users_list)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    all_oficios = list(oficios.find())
    for o in all_oficios:
        o['fecha_recibido_formatted'] = format_date(o.get('fecha_recibido'))
        o['fecha_enviado_formatted'] = format_date(o.get('fecha_enviado'))
        o['fecha_designacion_formatted'] = format_date(o.get('fecha_designacion'))
        if isinstance(o.get('tecnico_asignado'), str):
            o['tecnico_asignado'] = [o['tecnico_asignado']] if o['tecnico_asignado'] else []
        elif o.get('tecnico_asignado') is None:
            o['tecnico_asignado'] = []
    users_list = list(users.find())
    parroquias_list = list(parroquias.find())
    tecnicos_list = sorted([u['username'] for u in users.find({'role': 'tecnico'})])
    if request.method == 'POST':
        if 'create_user' in request.form:
            username = request.form['new_username']
            password = request.form['new_password']
            role = request.form['role']
            if users.find_one({'username': username}):
                flash('Usuario ya existe', 'error')
            else:
                try:
                    users.insert_one({'username': username, 'password': password, 'role': role})
                    flash('Usuario creado exitosamente', 'success')
                except Exception as e:
                    flash(f'Error al crear usuario: {str(e)}', 'error')
        elif 'edit_user' in request.form:
            user_id = ObjectId(request.form['user_id'])
            update = {'$set': {'username': request.form['edit_username'], 'role': request.form['edit_role']}}
            if request.form.get('edit_password'):
                update['$set']['password'] = request.form['edit_password']
            try:
                users.update_one({'_id': user_id}, update)
                flash('Usuario actualizado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al actualizar usuario: {str(e)}', 'error')
        elif 'add_parroquia' in request.form:
            parroquia = request.form['parroquia']
            canton = request.form['canton']
            if parroquias.find_one({'parroquia': parroquia}):
                flash('Parroquia ya existe', 'error')
            else:
                try:
                    parroquias.insert_one({'parroquia': parroquia, 'canton': canton})
                    flash('Parroquia añadida exitosamente', 'success')
                except Exception as e:
                    flash(f'Error al añadir parroquia: {str(e)}', 'error')
        elif 'edit_parroquia' in request.form:
            parroquia_id = ObjectId(request.form['parroquia_id'])
            update = {'$set': {'parroquia': request.form['edit_parroquia'], 'canton': request.form['edit_canton']}}
            try:
                parroquias.update_one({'_id': parroquia_id}, update)
                flash('Parroquia actualizada exitosamente', 'success')
            except Exception as e:
                flash(f'Error al actualizar parroquia: {str(e)}', 'error')
        elif 'delete_oficio' in request.form:
            oficio_id = ObjectId(request.form['oficio_id'])
            oficio = oficios.find_one({'_id': oficio_id})
            if oficio:
                try:
                    prefix = oficio['id_secuencial'].split('-')[0] + '-'
                    oficios.delete_one({'_id': oficio_id})
                    all_in_year = list(oficios.find({'id_secuencial': {'$regex': f"^{re.escape(prefix)}"}}).sort('id_secuencial', 1))
                    for i, doc in enumerate(all_in_year, 1):
                        new_id = f"{prefix}{i:04d}"
                        oficios.update_one({'_id': doc['_id']}, {'$set': {'id_secuencial': new_id}})
                    flash('Registro eliminado y IDs actualizados exitosamente', 'success')
                except Exception as e:
                    flash(f'Error al eliminar registro o actualizar IDs: {str(e)}', 'error')
        elif 'edit_oficio' in request.form:
            oficio_id = ObjectId(request.form['oficio_id'])
            tecnicos = request.form.getlist('edit_tecnico_asignado[]')
            update_data = {
                '$set': {
                    'fecha_enviado': request.form['edit_fecha_enviado'],
                    'numero_oficio': request.form['edit_numero_oficio'],
                    'gad_parroquial': request.form['edit_gad_parroquial'],
                    'canton': request.form['edit_canton'],
                    'detalle': request.form['edit_detalle'],
                    'tecnico_asignado': tecnicos if tecnicos and 'Ninguno' not in tecnicos else [],
                    'tipo_asesoria': request.form.get('edit_tipo_asesoria') if request.form.get('edit_tipo_asesoria') != 'Ninguno' else None
                }
            }
            try:
                oficios.update_one({'_id': oficio_id}, update_data)
                flash('Registro actualizado exitosamente', 'success')
            except Exception as e:
                flash(f'Error al actualizar registro: {str(e)}', 'error')
        return redirect(url_for('admin'))
    return render_template('admin.html', oficios=all_oficios, users=users_list, parroquias=parroquias_list, roles=roles_list, tecnicos=tecnicos_list, tipos=tipos_asesoria)

if __name__ == '__main__':
    app.run(debug=True)
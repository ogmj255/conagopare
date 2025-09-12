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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)), debug=True)
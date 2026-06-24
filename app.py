import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'clave_segura_por_defecto')

def get_db_connection():
    # Conexión directa a PostgreSQL en la nube de forma segura
    return psycopg2.connect(os.getenv('DATABASE_URL'))

@app.route('/')
def index():
    if 'usuario_id' in session:
        return redirect(url_for('alertas'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        password = request.form['password']
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Buscar usuario e interceptar sus credenciales seguras
        cur.execute("""
            SELECT u.id_usuario, u.nombre, c.password_hash 
            FROM usuarios u
            JOIN credenciales c ON u.id_usuario = c.id_usuario
            WHERE u.correo = %s
        """, (correo,))
        usuario = cur.fetchone()
        
        cur.close()
        conn.close()
        
        # Validar la contraseña de forma encriptada
        if usuario and check_password_hash(usuario['password_hash'], password):
            session['usuario_id'] = usuario['id_usuario']
            session['usuario_nombre'] = usuario['nombre']
            flash(f"¡Bienvenido de nuevo, {usuario['nombre']}!", "success")
            return redirect(url_for('alertas'))
        else:
            flash("Credenciales incorrectas. Inténtalo de nuevo.", "danger")
            
    return render_template('login.html')

@app.route('/alertas')
def alertas():
    # Seguridad: Si no ha iniciado sesión, lo regresa al login
    if 'usuario_id' not in session:
        flash("Por favor, inicia sesión para acceder.", "warning")
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Consumir la vista avanzada de alertas que creamos en la base de datos
    cur.execute("SELECT * FROM vista_alertas_prestamos ORDER BY fecha_devolucion_esperada ASC;")
    alertas_list = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('alertas.html', alertas=alertas_list)

@app.route('/logout')
def logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
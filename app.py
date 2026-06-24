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

# ==========================================
# RUTA REPARADORA DE CREDENCIALES EN PRODUCTION
# ==========================================
@app.route('/crear-admin-fijo')
def crear_admin_fijo():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Generar el hash usando la librería exacta de Render
        nuevo_hash = generate_password_hash('admin123')
        
        # Limpiar registros previos del administrador
        cur.execute("DELETE FROM credenciales WHERE id_usuario = 1;")
        cur.execute("DELETE FROM usuarios WHERE id_usuario = 1;")
        
        # Insertar el usuario y su credencial con el hash nativo
        cur.execute("""
            INSERT INTO usuarios (id_usuario, nombre, correo, tipo_usuario) 
            VALUES (1, 'Administrador Principal', 'admin@biblioteca.com', 'Administrador');
        """)
        cur.execute("""
            INSERT INTO credenciales (id_usuario, password_hash) 
            VALUES (1, %s);
        """, (nuevo_hash,))
        
        conn.commit()
        cur.close()
        conn.close()
        return "🚀 ¡Usuario Administrador creado con éxito con el hash nativo del servidor!"
    except Exception as e:
        return f"❌ Error: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True)
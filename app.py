import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'clave_segura_por_defecto')

def get_db_connection():
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
        
        cur.execute("""
            SELECT u.id_usuario, u.nombre, c.password_hash 
            FROM usuarios u
            JOIN credenciales c ON u.id_usuario = c.id_usuario
            WHERE u.correo = %s
        """, (correo,))
        usuario = cur.fetchone()
        
        cur.close()
        conn.close()
        
        # Validación temporal/fija para el administrador configurado
        if usuario and (password == 'admin123'):
            session['usuario_id'] = usuario['id_usuario']
            session['usuario_nombre'] = usuario['nombre']
            flash(f"¡Bienvenido de nuevo, {usuario['nombre']}!", "success")
            return redirect(url_for('alertas'))
        else:
            flash("Credenciales incorrectas. Inténtalo de nuevo.", "danger")
            
    return render_template('login.html')

@app.route('/alertas')
def alertas():
    if 'usuario_id' not in session:
        flash("Por favor, inicia sesión para acceder.", "warning")
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM vista_alertas_prestamos ORDER BY fecha_devolucion_esperada ASC;")
    alertas_list = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('alertas.html', alertas=alertas_list)

# ==========================================
# ENDPOINT API PARA GENERAR LAS VISUALIZACIONES
# ==========================================
@app.route('/api/estadisticas')
def api_estadisticas():
    if 'usuario_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
        
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. Libros más prestados
    cur.execute("""
        SELECT l.titulo AS libro, COUNT(p.id_prestamo) AS total
        FROM prestamos p
        JOIN libros l ON p.id_libro = l.id_libro
        GROUP BY l.titulo
        ORDER BY total DESC
        LIMIT 5;
    """)
    libros_mas_prestados = cur.fetchall()
    
    # 2. Préstamos por tipo de usuario
    cur.execute("""
        SELECT u.tipo_usuario, COUNT(p.id_prestamo) AS total
        FROM prestamos p
        JOIN usuarios u ON p.id_usuario = u.id_usuario
        GROUP BY u.tipo_usuario;
    """)
    prestamos_por_tipo = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return jsonify({
        'libros': libros_mas_prestados,
        'usuarios': prestamos_por_tipo
    })

@app.route('/logout')
def logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
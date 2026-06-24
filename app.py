import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime, timedelta

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
    
    # Obtener alertas de la vista
    cur.execute("SELECT * FROM vista_alertas_prestamos ORDER BY fecha_entregado IS NOT NULL, fecha_devolucion_esperada ASC;")
    alertas_list = cur.fetchall()
    
    # Obtener listas para los desplegables del formulario modal
    cur.execute("SELECT id_libro, titulo FROM libros WHERE stock > 0 ORDER BY titulo ASC;")
    libros_list = cur.fetchall()
    
    cur.execute("SELECT id_usuario, nombre FROM usuarios ORDER BY nombre ASC;")
    usuarios_list = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('alertas.html', alertas=alertas_list, libros=libros_list, usuarios=usuarios_list)

# ==========================================
# ACCIÓN: REGISTRAR NUEVO PRÉSTAMO (INSERT)
# ==========================================
@app.route('/registrar_prestamo', methods=['POST'])
def registrar_prestamo():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    id_libro = request.form['id_libro']
    id_usuario = request.form['id_usuario']
    dias_prestamo = int(request.form['dias_prestamo'])
    
    fecha_prestamo = datetime.now().date()
    fecha_devolucion = fecha_prestamo + timedelta(days=dias_prestamo)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Insertar préstamo
        cur.execute("""
            INSERT INTO prestamos (id_libro, id_usuario, fecha_prestamo, fecha_devolucion_esperada, fecha_entregado)
            VALUES (%s, %s, %s, %s, NULL);
        """, (id_libro, id_usuario, fecha_prestamo, fecha_devolucion))
        
        # Restar 1 al stock del libro
        cur.execute("UPDATE libros SET stock = stock - 1 WHERE id_libro = %s;", (id_libro,))
        
        conn.commit()
        cur.close()
        conn.close()
        flash("🚀 Préstamo registrado con éxito y stock actualizado.", "success")
    except Exception as e:
        flash(f"❌ Error al registrar préstamo: {str(e)}", "danger")
        
    return redirect(url_for('alertas'))

# ==========================================
# ACCIÓN: MARCAR COMO ENTREGADO (UPDATE)
# ==========================================
@app.route('/entregar_prestamo/<int:id_prestamo>')
def entregar_prestamo(id_prestamo):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Obtener el id_libro antes de actualizar para devolverlo al stock
        cur.execute("SELECT id_libro FROM prestamos WHERE id_prestamo = %s;", (id_prestamo,))
        res = cur.fetchone()
        
        if res:
            id_libro = res[0]
            # Colocar fecha de entrega (hoy)
            cur.execute("UPDATE prestamos SET fecha_entregado = CURRENT_DATE WHERE id_prestamo = %s;", (id_prestamo,))
            # Devolver 1 al stock del libro
            cur.execute("UPDATE libros SET stock = stock + 1 WHERE id_libro = %s;", (id_libro,))
            conn.commit()
            flash("✔ Libro devuelto correctamente. El stock ha sido restaurado.", "success")
            
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"❌ Error al devolver libro: {str(e)}", "danger")
        
    return redirect(url_for('alertas'))

@app.route('/api/estadisticas')
def api_estadisticas():
    if 'usuario_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
        
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT l.titulo AS libro, COUNT(p.id_prestamo) AS total
        FROM prestamos p
        JOIN libros l ON p.id_libro = l.id_libro
        GROUP BY l.titulo
        ORDER BY total DESC
        LIMIT 5;
    """)
    libros_mas_prestados = cur.fetchall()
    
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
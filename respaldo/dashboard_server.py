# -*- coding: utf-8 -*-
import sys
import io
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

"""
GREY BARK ADVISORS - DASHBOARD WEB INTERACTIVO
Servidor Flask para gestión completa de clientes
"""

from flask import Flask, render_template_string, request, jsonify, redirect, url_for
import json
import os
from datetime import datetime
from client_manager import (
    load_database, 
    save_database, 
    add_client, 
    remove_client,
    update_client_reports,
    get_recipients_for_report,
    AVAILABLE_REPORTS,
    CLIENT_TYPES
)

app = Flask(__name__)

# ============================================================================
# HTML TEMPLATE
# ============================================================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Grey Bark Advisors - Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #000000 0%, #1e3a8a 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.4);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #000000 0%, #1e3a8a 100%);
            color: white;
            padding: 30px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            font-size: 32px;
        }
        
        .header p {
            font-size: 16px;
            opacity: 0.9;
            margin-top: 5px;
        }
        
        .refresh-btn {
            background: rgba(255,255,255,0.2);
            border: 2px solid white;
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
        }
        
        .refresh-btn:hover {
            background: white;
            color: #000;
        }
        
        .tabs {
            display: flex;
            background: #f3f4f6;
            border-bottom: 2px solid #e5e7eb;
        }
        
        .tab {
            flex: 1;
            padding: 15px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 600;
            color: #6b7280;
            border: none;
            background: none;
        }
        
        .tab:hover {
            background: #e5e7eb;
        }
        
        .tab.active {
            background: white;
            color: #1e40af;
            border-bottom: 3px solid #3b82f6;
        }
        
        .content {
            padding: 40px;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
            animation: fadeIn 0.3s;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%);
            padding: 25px;
            border-radius: 12px;
            text-align: center;
        }
        
        .stat-card .number {
            font-size: 42px;
            font-weight: bold;
            color: #1e40af;
            margin-bottom: 8px;
        }
        
        .stat-card .label {
            font-size: 14px;
            color: #6b7280;
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        
        .client-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .client-card {
            border: 2px solid #e5e7eb;
            border-radius: 12px;
            padding: 20px;
            transition: all 0.3s;
            position: relative;
        }
        
        .client-card:hover {
            border-color: #3b82f6;
            box-shadow: 0 8px 24px rgba(59, 130, 246, 0.2);
            transform: translateY(-4px);
        }
        
        .client-card.professional {
            border-left: 5px solid #10b981;
        }
        
        .client-card.retail {
            border-left: 5px solid #f59e0b;
        }
        
        .client-card.internal {
            border-left: 5px solid #8b5cf6;
        }
        
        .client-card.inactive {
            opacity: 0.5;
            background: #f9fafb;
        }
        
        .client-card h3 {
            font-size: 18px;
            color: #111827;
            margin-bottom: 8px;
        }
        
        .client-card .email {
            color: #6b7280;
            font-size: 13px;
            margin-bottom: 12px;
            word-break: break-all;
        }
        
        .type-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            margin-bottom: 12px;
        }
        
        .type-badge.professional {
            background: #d1fae5;
            color: #065f46;
        }
        
        .type-badge.retail {
            background: #fed7aa;
            color: #92400e;
        }
        
        .type-badge.internal {
            background: #ddd6fe;
            color: #5b21b6;
        }
        
        .reports-list {
            list-style: none;
            font-size: 12px;
            color: #4b5563;
            margin-bottom: 15px;
        }
        
        .reports-list li {
            padding: 4px 0;
        }
        
        .reports-list li:before {
            content: "✓ ";
            color: #10b981;
            font-weight: bold;
            margin-right: 5px;
        }
        
        .actions {
            display: flex;
            gap: 8px;
        }
        
        .btn {
            padding: 8px 16px;
            border-radius: 6px;
            border: none;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.2s;
            flex: 1;
        }
        
        .btn-edit {
            background: #3b82f6;
            color: white;
        }
        
        .btn-edit:hover {
            background: #2563eb;
        }
        
        .btn-toggle {
            background: #6b7280;
            color: white;
        }
        
        .btn-toggle:hover {
            background: #4b5563;
        }
        
        .btn-toggle.activate {
            background: #10b981;
        }
        
        .btn-toggle.activate:hover {
            background: #059669;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            font-weight: 600;
            color: #374151;
            margin-bottom: 8px;
        }
        
        .form-group input,
        .form-group select,
        .form-group textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s;
            font-family: inherit;
        }
        
        .form-group input:focus,
        .form-group select:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: #3b82f6;
        }
        
        .checkbox-group {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 12px;
        }
        
        .checkbox-item {
            display: flex;
            align-items: flex-start;
            padding: 12px;
            background: #f9fafb;
            border-radius: 8px;
            border: 2px solid transparent;
            transition: all 0.2s;
        }
        
        .checkbox-item:hover {
            border-color: #3b82f6;
            background: #eff6ff;
        }
        
        .checkbox-item input[type="checkbox"] {
            width: 20px;
            height: 20px;
            margin-right: 10px;
            margin-top: 2px;
            cursor: pointer;
        }
        
        .checkbox-item label {
            cursor: pointer;
            font-size: 14px;
            line-height: 1.4;
        }
        
        .button {
            background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
            color: white;
            padding: 14px 28px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }
        
        .button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(59, 130, 246, 0.4);
        }
        
        .button:active {
            transform: translateY(0);
        }
        
        .distribution-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-radius: 8px;
            overflow: hidden;
        }
        
        .distribution-table th,
        .distribution-table td {
            padding: 16px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }
        
        .distribution-table th {
            background: #f9fafb;
            font-weight: 700;
            color: #374151;
            text-transform: uppercase;
            font-size: 12px;
            letter-spacing: 0.5px;
        }
        
        .distribution-table tr:hover {
            background: #f9fafb;
        }
        
        .recipient-list {
            list-style: none;
            font-size: 13px;
            color: #6b7280;
        }
        
        .recipient-list li {
            padding: 4px 0;
        }
        
        .alert {
            padding: 16px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-weight: 500;
        }
        
        .alert-success {
            background: #d1fae5;
            color: #065f46;
            border-left: 4px solid #10b981;
        }
        
        .alert-info {
            background: #dbeafe;
            color: #1e40af;
            border-left: 4px solid #3b82f6;
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        
        .modal.active {
            display: flex;
        }
        
        .modal-content {
            background: white;
            padding: 40px;
            border-radius: 16px;
            max-width: 600px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }
        
        .modal-header {
            margin-bottom: 24px;
        }
        
        .modal-header h2 {
            color: #111827;
            font-size: 24px;
        }
        
        .close-modal {
            float: right;
            font-size: 28px;
            cursor: pointer;
            color: #6b7280;
            line-height: 1;
        }
        
        .close-modal:hover {
            color: #111827;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>🏦 Grey Bark Advisors</h1>
                <p>Sistema de Gestión de Clientes</p>
            </div>
            <button class="refresh-btn" onclick="location.reload()">🔄 Recargar</button>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('overview')">📊 Resumen</button>
            <button class="tab" onclick="showTab('clients')">👥 Clientes</button>
            <button class="tab" onclick="showTab('add')">➕ Agregar</button>
            <button class="tab" onclick="showTab('distribution')">📧 Distribución</button>
        </div>
        
        <div class="content">
            <!-- RESUMEN TAB -->
            <div id="overview" class="tab-content active">
                <h2 style="margin-bottom: 20px;">Resumen del Sistema</h2>
                
                <div class="stats">
                    <div class="stat-card">
                        <div class="number">{{ stats.total }}</div>
                        <div class="label">Total Activos</div>
                    </div>
                    <div class="stat-card">
                        <div class="number">{{ stats.professional }}</div>
                        <div class="label">Profesionales</div>
                    </div>
                    <div class="stat-card">
                        <div class="number">{{ stats.retail }}</div>
                        <div class="label">Retail</div>
                    </div>
                    <div class="stat-card">
                        <div class="number">{{ stats.internal }}</div>
                        <div class="label">Internos</div>
                    </div>
                </div>
                
                <div class="alert alert-success">
                    <strong>✅ Sistema Operativo</strong><br>
                    Base de datos: <code>clients_database.json</code> | 
                    Última actualización: {{ metadata.last_updated }}
                </div>
            </div>
            
            <!-- CLIENTES TAB -->
            <div id="clients" class="tab-content">
                <h2 style="margin-bottom: 20px;">Clientes Activos ({{ stats.total }})</h2>
                <div class="client-grid">
                    {% for client in active_clients %}
                    <div class="client-card {{ client.type }} {% if not client.active %}inactive{% endif %}">
                        <h3>{{ client.name }}</h3>
                        <div class="email">{{ client.email }}</div>
                        <div class="type-badge {{ client.type }}">{{ client.type }}</div>
                        <ul class="reports-list">
                            {% for report in client.reports %}
                            <li>{{ report_names[report] }}</li>
                            {% endfor %}
                        </ul>
                        {% if client.notes %}
                        <div style="font-size: 12px; color: #9ca3af; margin-bottom: 12px;">
                            📝 {{ client.notes }}
                        </div>
                        {% endif %}
                        <div class="actions">
                            <button class="btn btn-edit" onclick="editClient({{ client.id }})">✏️ Editar</button>
                            <button class="btn btn-toggle" onclick="toggleClient({{ client.id }}, '{{ client.email }}')">
                                🔴 Desactivar
                            </button>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                
                {% if inactive_clients %}
                <h2 style="margin: 40px 0 20px 0;">Clientes Inactivos ({{ inactive_clients|length }})</h2>
                <div class="client-grid">
                    {% for client in inactive_clients %}
                    <div class="client-card {{ client.type }} inactive">
                        <h3>{{ client.name }}</h3>
                        <div class="email">{{ client.email }}</div>
                        <div class="type-badge {{ client.type }}">{{ client.type }}</div>
                        <div class="actions">
                            <button class="btn btn-toggle activate" onclick="reactivateClient({{ client.id }}, '{{ client.email }}')">
                                🟢 Reactivar
                            </button>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
            
            <!-- AGREGAR TAB -->
            <div id="add" class="tab-content">
                <h2 style="margin-bottom: 20px;">Agregar Nuevo Cliente</h2>
                
                <form method="POST" action="/add_client">
                    <div class="form-group">
                        <label>Nombre Completo *</label>
                        <input type="text" name="name" required placeholder="Ej: Juan Pérez">
                    </div>
                    
                    <div class="form-group">
                        <label>Email *</label>
                        <input type="email" name="email" required placeholder="juan.perez@empresa.cl">
                    </div>
                    
                    <div class="form-group">
                        <label>Tipo de Cliente *</label>
                        <select name="client_type" required>
                            <option value="professional">Professional</option>
                            <option value="retail">Retail</option>
                            <option value="internal">Internal</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label>Reportes a Recibir *</label>
                        <div class="checkbox-group">
                            {% for key, desc in report_types.items() %}
                            <div class="checkbox-item">
                                <input type="checkbox" name="reports" value="{{ key }}" id="report_{{ key }}">
                                <label for="report_{{ key }}">
                                    <strong>{{ desc }}</strong><br>
                                    <span style="font-size: 11px; color: #6b7280;">{{ key }}</span>
                                </label>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label>Notas (Opcional)</label>
                        <textarea name="notes" rows="3" placeholder="Notas sobre el cliente..."></textarea>
                    </div>
                    
                    <button type="submit" class="button">➕ Agregar Cliente</button>
                </form>
            </div>
            
            <!-- DISTRIBUCIÓN TAB -->
            <div id="distribution" class="tab-content">
                <h2 style="margin-bottom: 20px;">Distribución de Reportes</h2>
                
                <div class="alert alert-info">
                    <strong>📧 Vista de distribución actual</strong><br>
                    Aquí puedes ver qué clientes reciben cada tipo de reporte.
                </div>
                
                <table class="distribution-table">
                    <thead>
                        <tr>
                            <th>Tipo de Reporte</th>
                            <th>Destinatarios</th>
                            <th style="text-align: center;">Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for report_key, report_name in report_types.items() %}
                        <tr>
                            <td><strong>{{ report_name }}</strong><br><small style="color: #9ca3af;">{{ report_key }}</small></td>
                            <td>
                                {% if distribution[report_key] %}
                                <ul class="recipient-list">
                                    {% for recipient in distribution[report_key] %}
                                    <li>{{ recipient.name }} &lt;{{ recipient.email }}&gt;</li>
                                    {% endfor %}
                                </ul>
                                {% else %}
                                <em style="color: #9ca3af;">Sin destinatarios</em>
                                {% endif %}
                            </td>
                            <td style="text-align: center;">
                                <strong style="font-size: 18px; color: #3b82f6;">
                                    {{ distribution[report_key]|length if distribution[report_key] else 0 }}
                                </strong>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    
    <!-- MODAL EDIT -->
    <div id="editModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <span class="close-modal" onclick="closeEditModal()">&times;</span>
                <h2>Editar Cliente</h2>
            </div>
            <form method="POST" action="/edit_client" id="editForm">
                <input type="hidden" name="client_id" id="edit_client_id">
                
                <div class="form-group">
                    <label>Email</label>
                    <input type="text" id="edit_email" readonly style="background: #f3f4f6;">
                </div>
                
                <div class="form-group">
                    <label>Reportes a Recibir</label>
                    <div class="checkbox-group" id="edit_reports_container">
                        <!-- Se llena dinámicamente -->
                    </div>
                </div>
                
                <button type="submit" class="button">💾 Guardar Cambios</button>
            </form>
        </div>
    </div>
    
    <script>
        function showTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
        }
        
        function editClient(clientId) {
            fetch(`/get_client/${clientId}`)
                .then(r => r.json())
                .then(client => {
                    document.getElementById('edit_client_id').value = client.id;
                    document.getElementById('edit_email').value = client.email;
                    
                    const container = document.getElementById('edit_reports_container');
                    container.innerHTML = '';
                    
                    const reportTypes = {{ report_types|tojson }};
                    
                    for (const [key, desc] of Object.entries(reportTypes)) {
                        const checked = client.reports.includes(key) ? 'checked' : '';
                        container.innerHTML += `
                            <div class="checkbox-item">
                                <input type="checkbox" name="reports" value="${key}" id="edit_report_${key}" ${checked}>
                                <label for="edit_report_${key}">
                                    <strong>${desc}</strong><br>
                                    <span style="font-size: 11px; color: #6b7280;">${key}</span>
                                </label>
                            </div>
                        `;
                    }
                    
                    document.getElementById('editModal').classList.add('active');
                });
        }
        
        function closeEditModal() {
            document.getElementById('editModal').classList.remove('active');
        }
        
        function toggleClient(clientId, email) {
            if (confirm(`¿Desactivar cliente: ${email}?`)) {
                window.location.href = `/toggle_client/${clientId}/false`;
            }
        }
        
        function reactivateClient(clientId, email) {
            if (confirm(`¿Reactivar cliente: ${email}?`)) {
                window.location.href = `/toggle_client/${clientId}/true`;
            }
        }
    </script>
</body>
</html>
"""

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    """Dashboard principal"""
    db = load_database()
    
    active_clients = [c for c in db['clients'] if c['active']]
    inactive_clients = [c for c in db['clients'] if not c['active']]
    
    stats = {
        'total': len(active_clients),
        'professional': len([c for c in active_clients if c['type'] == 'professional']),
        'retail': len([c for c in active_clients if c['type'] == 'retail']),
        'internal': len([c for c in active_clients if c['type'] == 'internal']),
    }
    
    report_names = {
        'AM_pro': 'Matutino Pro',
        'AM_general': 'Matutino General',
        'PM_pro': 'Vespertino Pro',
        'PM_general': 'Vespertino General',
        'weekly_quant': 'Cuantitativo Semanal'
    }
    
    # Distribución
    distribution = {}
    for report_type in AVAILABLE_REPORTS.keys():
        distribution[report_type] = get_recipients_for_report(report_type)
    
    return render_template_string(
        DASHBOARD_HTML,
        stats=stats,
        active_clients=active_clients,
        inactive_clients=inactive_clients,
        metadata=db['metadata'],
        report_types=AVAILABLE_REPORTS,
        report_names=report_names,
        distribution=distribution
    )


@app.route('/add_client', methods=['POST'])
def add_client_route():
    """Agregar nuevo cliente"""
    name = request.form['name']
    email = request.form['email']
    client_type = request.form['client_type']
    reports = request.form.getlist('reports')
    notes = request.form.get('notes', '')
    
    success = add_client(name, email, client_type, reports, notes)
    
    return redirect('/')


@app.route('/get_client/<int:client_id>')
def get_client(client_id):
    """Obtener datos de un cliente específico"""
    db = load_database()
    
    for client in db['clients']:
        if client['id'] == client_id:
            return jsonify(client)
    
    return jsonify({'error': 'Cliente no encontrado'}), 404


@app.route('/edit_client', methods=['POST'])
def edit_client_route():
    """Editar reportes de un cliente"""
    client_id = int(request.form['client_id'])
    reports = request.form.getlist('reports')
    
    db = load_database()
    
    for client in db['clients']:
        if client['id'] == client_id:
            client['reports'] = reports
            save_database(db)
            break
    
    return redirect('/')


@app.route('/toggle_client/<int:client_id>/<active>')
def toggle_client_route(client_id, active):
    """Activar/Desactivar cliente"""
    db = load_database()
    
    active_bool = active.lower() == 'true'
    
    for client in db['clients']:
        if client['id'] == client_id:
            client['active'] = active_bool
            save_database(db)
            break
    
    return redirect('/')


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*80)
    print("🏦 GREY BARK ADVISORS - DASHBOARD WEB")
    print("="*80)
    print("\n🌐 Dashboard corriendo en: http://localhost:5000")
    print("\n💡 Presiona Ctrl+C para detener el servidor")
    print("="*80 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)

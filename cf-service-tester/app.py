"""
Cloud Foundry Service Tester - Ticket Reservation System
Main Flask application for testing CF services with a ticket reservation system
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, jsonify, request, render_template_string

# Import framework components
from framework.config_loader import ConfigLoader
from framework.service_manager import ServiceManager
from framework.reservation_service import ReservationService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Global variables
config = None
service_manager = None
reservation_service = None

def initialize_app():
    """Initialize the application with configuration and services"""
    global config, service_manager, reservation_service
    
    try:
        # Load configuration
        config_loader = ConfigLoader()
        config = config_loader.load_config()
        
        # Validate configuration
        if not config_loader.validate_config(config):
            raise Exception("Configuration validation failed")
        
        # Initialize service manager
        service_manager = ServiceManager(config)
        
        # Connect to services
        connection_results = service_manager.connect_all()
        logger.info(f"Service connections: {connection_results}")
        
        # Initialize reservation service
        reservation_service = ReservationService(service_manager)
        
        logger.info(f"Application '{config.name}' initialized successfully")
        
    except Exception as e:
        logger.error(f"Application initialization failed: {str(e)}")
        raise

# Initialize app on startup
initialize_app()

@app.route('/health')
def health_check():
    """Health check endpoint for CF health monitoring"""
    try:
        health_status = service_manager.health_check_all()
        
        return jsonify({
            'status': 'healthy',
            'app': config.name,
            'description': config.description,
            'services': health_status,
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/')
def index():
    """Main page redirect to UI"""
    return jsonify({
        'message': f'Welcome to {config.name}',
        'description': config.description,
        'endpoints': {
            'ui': '/ui',
            'health': '/health',
            'api': '/api/reservations',
            'services': '/services'
        }
    })

@app.route('/services')
def list_services():
    """List configured services and their status"""
    try:
        health_status = service_manager.health_check_all()
        
        services_info = {
            'database': {
                'type': config.database.type,
                'connection_type': config.database.connection_type,
                'connected': health_status.get('database', False)
            }
        }
        
        if config.message_queue.enabled:
            services_info['message_queue'] = {
                'type': config.message_queue.type,
                'connection_type': config.message_queue.connection_type,
                'connected': health_status.get('message_queue', False)
            }
        
        if config.cache.enabled:
            services_info['cache'] = {
                'type': config.cache.type,
                'connection_type': config.cache.connection_type,
                'connected': health_status.get('cache', False)
            }
        
        return jsonify({
            'status': 'success',
            'services': services_info,
            'features': config.features
        })
    
    except Exception as e:
        logger.error(f"Service listing failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# API Endpoints for Reservations

@app.route('/api/reservations', methods=['GET'])
def get_reservations():
    """Get all reservations"""
    try:
        reservations = reservation_service.get_all_reservations()
        return jsonify({
            'status': 'success',
            'count': len(reservations),
            'reservations': [r.to_dict() for r in reservations]
        })
    
    except Exception as e:
        logger.error(f"Get reservations failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/reservations/<int:reservation_id>', methods=['GET'])
def get_reservation(reservation_id):
    """Get a specific reservation"""
    try:
        reservation = reservation_service.get_reservation_by_id(reservation_id)
        
        if reservation:
            return jsonify({
                'status': 'success',
                'reservation': reservation.to_dict()
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Reservation not found'
            }), 404
    
    except Exception as e:
        logger.error(f"Get reservation failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/reservations', methods=['POST'])
def create_reservation():
    """Create a new reservation"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['customer_name', 'event_name', 'event_date', 'seat_number']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}'
                }), 400
        
        reservation = reservation_service.create_reservation(data)
        
        if reservation:
            return jsonify({
                'status': 'success',
                'message': 'Reservation created successfully',
                'reservation': reservation.to_dict()
            }), 201
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to create reservation'
            }), 500
    
    except Exception as e:
        logger.error(f"Create reservation failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/reservations/<int:reservation_id>', methods=['PUT'])
def update_reservation(reservation_id):
    """Update an existing reservation"""
    try:
        data = request.get_json()
        
        reservation = reservation_service.update_reservation(reservation_id, data)
        
        if reservation:
            return jsonify({
                'status': 'success',
                'message': 'Reservation updated successfully',
                'reservation': reservation.to_dict()
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Reservation not found or update failed'
            }), 404
    
    except Exception as e:
        logger.error(f"Update reservation failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/reservations/<int:reservation_id>', methods=['DELETE'])
def delete_reservation(reservation_id):
    """Delete a reservation"""
    try:
        success = reservation_service.delete_reservation(reservation_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Reservation deleted successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Reservation not found or delete failed'
            }), 404
    
    except Exception as e:
        logger.error(f"Delete reservation failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/statistics')
def get_statistics():
    """Get reservation statistics"""
    try:
        stats = reservation_service.get_statistics()
        return jsonify({
            'status': 'success',
            'statistics': stats
        })
    
    except Exception as e:
        logger.error(f"Get statistics failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/ui')
def web_ui():
    """Web UI for reservation management"""
    html_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ app_name }} - CF Service Tester</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            font-weight: 700;
        }
        
        .header p {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        
        .main-content {
            padding: 30px;
        }
        
        .section {
            margin-bottom: 40px;
            background: #f8f9fa;
            border-radius: 8px;
            padding: 25px;
            border-left: 4px solid #007bff;
        }
        
        .section h2 {
            color: #333;
            margin-bottom: 20px;
            font-size: 1.5rem;
            display: flex;
            align-items: center;
        }
        
        .section h2::before {
            content: "🎫";
            margin-right: 10px;
            font-size: 1.2em;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 30px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #555;
        }
        
        input, select, textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #e1e5e9;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.3s ease;
        }
        
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #007bff;
            box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
        }
        
        .btn {
            background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
            margin-right: 10px;
            margin-bottom: 10px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 123, 255, 0.3);
        }
        
        .btn-success {
            background: linear-gradient(135deg, #28a745 0%, #1e7e34 100%);
        }
        
        .btn-warning {
            background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%);
            color: #333;
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #dc3545 0%, #bd2130 100%);
        }
        
        .btn-secondary {
            background: linear-gradient(135deg, #6c757d 0%, #545b62 100%);
        }
        
        .reservations-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .reservation-card {
            background: white;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s ease;
        }
        
        .reservation-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
        }
        
        .reservation-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .reservation-id {
            font-weight: bold;
            color: #007bff;
            font-size: 1.1em;
        }
        
        .status-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .status-confirmed {
            background: #d4edda;
            color: #155724;
        }
        
        .status-pending {
            background: #fff3cd;
            color: #856404;
        }
        
        .status-cancelled {
            background: #f8d7da;
            color: #721c24;
        }
        
        .reservation-details {
            margin-bottom: 15px;
        }
        
        .detail-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            padding: 4px 0;
            border-bottom: 1px solid #f1f1f1;
        }
        
        .detail-label {
            font-weight: 600;
            color: #666;
        }
        
        .detail-value {
            color: #333;
        }
        
        .reservation-actions {
            display: flex;
            gap: 10px;
        }
        
        .loading {
            display: none;
            color: #007bff;
            font-weight: 600;
        }
        
        .loading.show {
            display: inline-block;
        }
        
        .result {
            margin-top: 20px;
            padding: 15px;
            border-radius: 6px;
            border: 1px solid #ddd;
            background: #fff;
            max-height: 300px;
            overflow-y: auto;
        }
        
        .result pre {
            white-space: pre-wrap;
            word-wrap: break-word;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            line-height: 1.4;
        }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        
        .status-success {
            background: #28a745;
        }
        
        .status-error {
            background: #dc3545;
        }
        
        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
            }
            
            .reservations-grid {
                grid-template-columns: 1fr;
            }
            
            .header h1 {
                font-size: 2rem;
            }
            
            .main-content {
                padding: 20px;
            }
        }
        
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
        }
        
        .modal-content {
            background-color: white;
            margin: 5% auto;
            padding: 30px;
            border-radius: 8px;
            width: 90%;
            max-width: 500px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .close {
            color: #aaa;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        
        .close:hover {
            color: #333;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎫 {{ app_name }}</h1>
            <p>{{ app_description }}</p>
            <p><small>Cloud Foundry Service Testing Framework</small></p>
        </div>
        
        <div class="main-content">
            <!-- System Status Section -->
            <div class="section">
                <h2 style="border-left-color: #28a745;">⚡ System Status</h2>
                <button class="btn btn-success" onclick="checkSystemHealth()">Check Health</button>
                <button class="btn" onclick="getServiceInfo()">Service Info</button>
                <button class="btn btn-secondary" onclick="getStatistics()">Statistics</button>
                <span class="loading" id="status-loading">Loading...</span>
                <div class="result" id="status-result"></div>
            </div>
            
            <!-- Create Reservation Section -->
            <div class="section">
                <h2>➕ Create New Reservation</h2>
                <div class="grid">
                    <div>
                        <div class="form-group">
                            <label for="customer-name">Customer Name:</label>
                            <input type="text" id="customer-name" placeholder="John Doe" required>
                        </div>
                        <div class="form-group">
                            <label for="event-name">Event Name:</label>
                            <input type="text" id="event-name" placeholder="Cloud Foundry Summit 2025" required>
                        </div>
                    </div>
                    <div>
                        <div class="form-group">
                            <label for="event-date">Event Date:</label>
                            <input type="date" id="event-date" required>
                        </div>
                        <div class="form-group">
                            <label for="seat-number">Seat Number:</label>
                            <input type="text" id="seat-number" placeholder="A-101" required>
                        </div>
                    </div>
                </div>
                <div class="form-group">
                    <label for="status">Status:</label>
                    <select id="status">
                        <option value="pending">Pending</option>
                        <option value="confirmed">Confirmed</option>
                        <option value="cancelled">Cancelled</option>
                    </select>
                </div>
                <button class="btn" onclick="createReservation()">Create Reservation</button>
                <span class="loading" id="create-loading">Creating...</span>
                <div class="result" id="create-result"></div>
            </div>
            
            <!-- View Reservations Section -->
            <div class="section">
                <h2 style="border-left-color: #ffc107;">📋 Manage Reservations</h2>
                <button class="btn btn-warning" onclick="loadReservations()">Load All Reservations</button>
                <span class="loading" id="load-loading">Loading...</span>
                <div id="reservations-container"></div>
            </div>
        </div>
    </div>
    
    <!-- Edit Modal -->
    <div id="editModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>Edit Reservation</h3>
                <span class="close" onclick="closeEditModal()">&times;</span>
            </div>
            <div id="edit-form">
                <!-- Form will be populated dynamically -->
            </div>
        </div>
    </div>

    <script>
        let currentEditId = null;
        
        function showLoading(elementId, show = true) {
            const element = document.getElementById(elementId);
            if (element) {
                if (show) {
                    element.classList.add('show');
                } else {
                    element.classList.remove('show');
                }
            }
        }
        
        function displayResult(resultId, data, isError = false) {
            const resultDiv = document.getElementById(resultId);
            if (!resultDiv) return;
            
            const statusClass = isError ? 'status-error' : 'status-success';
            const statusIcon = isError ? '❌' : '✅';
            
            resultDiv.innerHTML = `
                <div style="margin-bottom: 10px;">
                    <span class="status-indicator ${statusClass}"></span>
                    <strong>${statusIcon} ${isError ? 'Error' : 'Success'}</strong>
                </div>
                <pre>${JSON.stringify(data, null, 2)}</pre>
            `;
        }
        
        async function checkSystemHealth() {
            showLoading('status-loading');
            try {
                const response = await fetch('/health');
                const data = await response.json();
                displayResult('status-result', data, !response.ok);
            } catch (error) {
                displayResult('status-result', { error: error.message }, true);
            } finally {
                showLoading('status-loading', false);
            }
        }
        
        async function getServiceInfo() {
            showLoading('status-loading');
            try {
                const response = await fetch('/services');
                const data = await response.json();
                displayResult('status-result', data, !response.ok);
            } catch (error) {
                displayResult('status-result', { error: error.message }, true);
            } finally {
                showLoading('status-loading', false);
            }
        }
        
        async function getStatistics() {
            showLoading('status-loading');
            try {
                const response = await fetch('/api/statistics');
                const data = await response.json();
                displayResult('status-result', data, !response.ok);
            } catch (error) {
                displayResult('status-result', { error: error.message }, true);
            } finally {
                showLoading('status-loading', false);
            }
        }
        
        async function createReservation() {
            showLoading('create-loading');
            try {
                const customerName = document.getElementById('customer-name').value;
                const eventName = document.getElementById('event-name').value;
                const eventDate = document.getElementById('event-date').value;
                const seatNumber = document.getElementById('seat-number').value;
                const status = document.getElementById('status').value;
                
                if (!customerName || !eventName || !eventDate || !seatNumber) {
                    throw new Error('Please fill in all required fields');
                }
                
                const reservationData = {
                    customer_name: customerName,
                    event_name: eventName,
                    event_date: eventDate,
                    seat_number: seatNumber,
                    status: status
                };
                
                const response = await fetch('/api/reservations', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(reservationData)
                });
                
                const data = await response.json();
                displayResult('create-result', data, !response.ok);
                
                if (response.ok) {
                    // Clear form
                    document.getElementById('customer-name').value = '';
                    document.getElementById('event-name').value = '';
                    document.getElementById('event-date').value = '';
                    document.getElementById('seat-number').value = '';
                    document.getElementById('status').value = 'pending';
                    
                    // Reload reservations if they're currently displayed
                    const container = document.getElementById('reservations-container');
                    if (container.innerHTML.trim()) {
                        loadReservations();
                    }
                }
                
            } catch (error) {
                displayResult('create-result', { error: error.message }, true);
            } finally {
                showLoading('create-loading', false);
            }
        }
        
        async function loadReservations() {
            showLoading('load-loading');
            try {
                const response = await fetch('/api/reservations');
                const data = await response.json();
                
                if (response.ok && data.reservations) {
                    displayReservations(data.reservations);
                } else {
                    displayResult('reservations-container', data, true);
                }
            } catch (error) {
                displayResult('reservations-container', { error: error.message }, true);
            } finally {
                showLoading('load-loading', false);
            }
        }
        
        function displayReservations(reservations) {
            const container = document.getElementById('reservations-container');
            
            if (reservations.length === 0) {
                container.innerHTML = '<p>No reservations found.</p>';
                return;
            }
            
            let html = `
                <div style="margin-bottom: 15px;">
                    <span class="status-indicator status-success"></span>
                    <strong>✅ Found ${reservations.length} reservations</strong>
                </div>
                <div class="reservations-grid">
            `;
            
            reservations.forEach(reservation => {
                const statusClass = `status-${reservation.status}`;
                html += `
                    <div class="reservation-card">
                        <div class="reservation-header">
                            <span class="reservation-id">#${reservation.id}</span>
                            <span class="status-badge ${statusClass}">${reservation.status}</span>
                        </div>
                        <div class="reservation-details">
                            <div class="detail-row">
                                <span class="detail-label">Customer:</span>
                                <span class="detail-value">${reservation.customer_name}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Event:</span>
                                <span class="detail-value">${reservation.event_name}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Date:</span>
                                <span class="detail-value">${reservation.event_date}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Seat:</span>
                                <span class="detail-value">${reservation.seat_number}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Created:</span>
                                <span class="detail-value">${new Date(reservation.created_at).toLocaleDateString()}</span>
                            </div>
                        </div>
                        <div class="reservation-actions">
                            <button class="btn btn-warning" onclick="editReservation(${reservation.id})">Edit</button>
                            <button class="btn btn-danger" onclick="deleteReservation(${reservation.id})">Delete</button>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
            container.innerHTML = html;
        }
        
        async function editReservation(id) {
            try {
                const response = await fetch(`/api/reservations/${id}`);
                const data = await response.json();
                
                if (response.ok && data.reservation) {
                    currentEditId = id;
                    showEditModal(data.reservation);
                } else {
                    alert('Failed to load reservation details');
                }
            } catch (error) {
                alert('Error loading reservation: ' + error.message);
            }
        }
        
        function showEditModal(reservation) {
            const formHtml = `
                <div class="form-group">
                    <label for="edit-customer-name">Customer Name:</label>
                    <input type="text" id="edit-customer-name" value="${reservation.customer_name}" required>
                </div>
                <div class="form-group">
                    <label for="edit-event-name">Event Name:</label>
                    <input type="text" id="edit-event-name" value="${reservation.event_name}" required>
                </div>
                <div class="form-group">
                    <label for="edit-event-date">Event Date:</label>
                    <input type="date" id="edit-event-date" value="${reservation.event_date}" required>
                </div>
                <div class="form-group">
                    <label for="edit-seat-number">Seat Number:</label>
                    <input type="text" id="edit-seat-number" value="${reservation.seat_number}" required>
                </div>
                <div class="form-group">
                    <label for="edit-status">Status:</label>
                    <select id="edit-status">
                        <option value="pending" ${reservation.status === 'pending' ? 'selected' : ''}>Pending</option>
                        <option value="confirmed" ${reservation.status === 'confirmed' ? 'selected' : ''}>Confirmed</option>
                        <option value="cancelled" ${reservation.status === 'cancelled' ? 'selected' : ''}>Cancelled</option>
                    </select>
                </div>
                <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;">
                    <button class="btn btn-secondary" onclick="closeEditModal()">Cancel</button>
                    <button class="btn" onclick="saveReservation()">Save Changes</button>
                </div>
            `;
            
            document.getElementById('edit-form').innerHTML = formHtml;
            document.getElementById('editModal').style.display = 'block';
        }
        
        function closeEditModal() {
            document.getElementById('editModal').style.display = 'none';
            currentEditId = null;
        }
        
        async function saveReservation() {
            try {
                const updateData = {
                    customer_name: document.getElementById('edit-customer-name').value,
                    event_name: document.getElementById('edit-event-name').value,
                    event_date: document.getElementById('edit-event-date').value,
                    seat_number: document.getElementById('edit-seat-number').value,
                    status: document.getElementById('edit-status').value
                };
                
                const response = await fetch(`/api/reservations/${currentEditId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(updateData)
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    closeEditModal();
                    loadReservations(); // Reload the list
                    alert('Reservation updated successfully!');
                } else {
                    alert('Failed to update reservation: ' + data.message);
                }
                
            } catch (error) {
                alert('Error updating reservation: ' + error.message);
            }
        }
        
        async function deleteReservation(id) {
            if (!confirm('Are you sure you want to delete this reservation? This action cannot be undone.')) {
                return;
            }
            
            try {
                const response = await fetch(`/api/reservations/${id}`, {
                    method: 'DELETE'
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    loadReservations(); // Reload the list
                    alert('Reservation deleted successfully!');
                } else {
                    alert('Failed to delete reservation: ' + data.message);
                }
                
            } catch (error) {
                alert('Error deleting reservation: ' + error.message);
            }
        }
        
        // Load system health on page load
        window.addEventListener('load', () => {
            checkSystemHealth();
        });
        
        // Close modal when clicking outside
        window.addEventListener('click', (event) => {
            const modal = document.getElementById('editModal');
            if (event.target === modal) {
                closeEditModal();
            }
        });
    </script>
</body>
</html>
    '''
    
    return render_template_string(
        html_template, 
        app_name=config.name,
        app_description=config.description
    )

# Cleanup on app shutdown
import atexit
atexit.register(lambda: service_manager.disconnect_all() if service_manager else None)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', config.port if config else 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

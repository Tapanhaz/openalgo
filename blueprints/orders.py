from flask import Blueprint, jsonify, request, render_template, session, redirect, url_for, Response
from importlib import import_module
from database.auth_db import get_auth_token
from utils.session import check_session_validity
import logging
import csv
import io

logger = logging.getLogger(__name__)

# Define the blueprint
orders_bp = Blueprint('orders_bp', __name__, url_prefix='/')

def dynamic_import(broker, module_name, function_names):
    module_functions = {}
    try:
        # Import the module based on the broker name
        module = import_module(f'broker.{broker}.{module_name}')
        for name in function_names:
            module_functions[name] = getattr(module, name)
        return module_functions
    except (ImportError, AttributeError) as e:
        logger.error(f"Error importing functions {function_names} from {module_name} for broker {broker}: {e}")
        return None

def generate_orderbook_csv(order_data):
    """Generate CSV file from orderbook data"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    headers = ['Order ID', 'Symbol', 'Order Type', 'Transaction Type', 'Product', 'Quantity', 
              'Price', 'Status', 'Order Time', 'Exchange', 'Validity']
    writer.writerow(headers)
    
    # Write data
    for order in order_data:
        row = [
            order.get('order_id', ''),
            order.get('symbol', ''),
            order.get('order_type', ''),
            order.get('transaction_type', ''),
            order.get('product', ''),
            order.get('quantity', ''),
            order.get('price', ''),
            order.get('status', ''),
            order.get('order_time', ''),
            order.get('exchange', ''),
            order.get('validity', '')
        ]
        writer.writerow(row)
    
    return output.getvalue()

def generate_tradebook_csv(trade_data):
    """Generate CSV file from tradebook data"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    headers = ['Trade ID', 'Order ID', 'Symbol', 'Trade Type', 'Quantity', 
              'Trade Price', 'Trade Time', 'Exchange']
    writer.writerow(headers)
    
    # Write data
    for trade in trade_data:
        row = [
            trade.get('trade_id', ''),
            trade.get('order_id', ''),
            trade.get('symbol', ''),
            trade.get('trade_type', ''),
            trade.get('quantity', ''),
            trade.get('trade_price', ''),
            trade.get('trade_time', ''),
            trade.get('exchange', '')
        ]
        writer.writerow(row)
    
    return output.getvalue()

def generate_positions_csv(positions_data):
    """Generate CSV file from positions data"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    headers = ['Symbol', 'Product', 'Net Quantity', 'Buy Quantity', 'Sell Quantity', 
              'Average Price', 'Last Price', 'P&L', 'Exchange']
    writer.writerow(headers)
    
    # Write data
    for position in positions_data:
        row = [
            position.get('symbol', ''),
            position.get('product', ''),
            position.get('net_quantity', ''),
            position.get('buy_quantity', ''),
            position.get('sell_quantity', ''),
            position.get('average_price', ''),
            position.get('last_price', ''),
            position.get('pnl', ''),
            position.get('exchange', '')
        ]
        writer.writerow(row)
    
    return output.getvalue()

@orders_bp.route('/orderbook')
@check_session_validity
def orderbook():
    broker = session.get('broker')
    if not broker:
        logger.error("Broker not set in session")
        return "Broker not set in session", 400

    # Dynamically import broker-specific modules for API and mapping
    api_funcs = dynamic_import(broker, 'api.order_api', ['get_order_book'])
    mapping_funcs = dynamic_import(broker, 'mapping.order_data', [
        'calculate_order_statistics', 'map_order_data', 
        'transform_order_data'
    ])

    if not api_funcs or not mapping_funcs:
        logger.error(f"Error loading broker-specific modules for {broker}")
        return "Error loading broker-specific modules", 500

    # Static import used for auth token retrieval
    login_username = session['user']
    auth_token = get_auth_token(login_username)

    if auth_token is None:
        logger.warning(f"No auth token found for user {login_username}")
        return redirect(url_for('auth.logout'))

    order_data = api_funcs['get_order_book'](auth_token)
    logger.debug(f"Order data received: {order_data}")
    
    if 'status' in order_data:
        if order_data['status'] == 'error':
            logger.error("Error in order data response")
            return redirect(url_for('auth.logout'))

    order_data = mapping_funcs['map_order_data'](order_data=order_data)
    order_stats = mapping_funcs['calculate_order_statistics'](order_data)
    order_data = mapping_funcs['transform_order_data'](order_data)

    return render_template('orderbook.html', order_data=order_data, order_stats=order_stats)

@orders_bp.route('/tradebook')
@check_session_validity
def tradebook():
    broker = session.get('broker')
    if not broker:
        logger.error("Broker not set in session")
        return "Broker not set in session", 400

    # Dynamically import broker-specific modules for API and mapping
    api_funcs = dynamic_import(broker, 'api.order_api', ['get_trade_book'])
    mapping_funcs = dynamic_import(broker, 'mapping.order_data', [
        'map_trade_data', 'transform_tradebook_data'
    ])

    if not api_funcs or not mapping_funcs:
        logger.error(f"Error loading broker-specific modules for {broker}")
        return "Error loading broker-specific modules", 500

    login_username = session['user']
    auth_token = get_auth_token(login_username)

    if auth_token is None:
        logger.warning(f"No auth token found for user {login_username}")
        return redirect(url_for('auth.logout'))

    # Using the dynamically imported `get_trade_book` function
    get_trade_book = api_funcs['get_trade_book']
    tradebook_data = get_trade_book(auth_token)
    logger.debug(f"Tradebook data received: {tradebook_data}")
  
    if 'status' in tradebook_data and tradebook_data['status'] == 'error':
        logger.error("Error in tradebook data response")
        return redirect(url_for('auth.logout'))

    # Using the dynamically imported mapping functions
    map_trade_data = mapping_funcs['map_trade_data']
    transform_tradebook_data = mapping_funcs['transform_tradebook_data']

    tradebook_data = map_trade_data(trade_data=tradebook_data)
    tradebook_data = transform_tradebook_data(tradebook_data)

    return render_template('tradebook.html', tradebook_data=tradebook_data)

@orders_bp.route('/positions')
@check_session_validity
def positions():
    broker = session.get('broker')
    if not broker:
        logger.error("Broker not set in session")
        return "Broker not set in session", 400

    # Dynamically import broker-specific modules for API and mapping
    api_funcs = dynamic_import(broker, 'api.order_api', ['get_positions'])
    mapping_funcs = dynamic_import(broker, 'mapping.order_data', [
        'map_position_data', 'transform_positions_data'
    ])

    if not api_funcs or not mapping_funcs:
        logger.error(f"Error loading broker-specific modules for {broker}")
        return "Error loading broker-specific modules", 500

    login_username = session['user']
    auth_token = get_auth_token(login_username)

    if auth_token is None:
        logger.warning(f"No auth token found for user {login_username}")
        return redirect(url_for('auth.logout'))

    # Using the dynamically imported `get_positions` function
    get_positions = api_funcs['get_positions']
    positions_data = get_positions(auth_token)
    logger.debug(f"Positions data received: {positions_data}")
   
    if 'status' in positions_data and positions_data['status'] == 'error':
        logger.error("Error in positions data response")
        return redirect(url_for('auth.logout'))

    # Using the dynamically imported mapping functions
    map_position_data = mapping_funcs['map_position_data']
    transform_positions_data = mapping_funcs['transform_positions_data']

    positions_data = map_position_data(positions_data)
    positions_data = transform_positions_data(positions_data)
    
    return render_template('positions.html', positions_data=positions_data)

@orders_bp.route('/positions/update', methods=['POST'])
@check_session_validity
def update_positions():
    broker = session.get('broker')
    if not broker:
        return jsonify({"status": "error", "message": "Broker not set in session"}), 400

    # Dynamically import broker-specific modules for API
    api_funcs = dynamic_import(broker, 'api.order_api', ['get_ltp'])
    
    if not api_funcs:
        return jsonify({"status": "error", "message": "Error loading broker-specific modules"}), 500

    login_username = session['user']
    auth_token = get_auth_token(login_username)

    if auth_token is None:
        return jsonify({"status": "error", "message": "Auth token not found"}), 401

    # Get the symbols from request
    data = request.get_json()
    symbols = data.get('symbols', [])
    
    if not symbols:
        return jsonify({"status": "error", "message": "No symbols provided"}), 400

    # Get LTP for all symbols
    get_ltp = api_funcs['get_ltp']
    ltp_data = get_ltp(auth_token, symbols)
    
    if 'status' in ltp_data and ltp_data['status'] == 'error':
        return jsonify({"status": "error", "message": "Error fetching LTP data"}), 500

    return jsonify({"status": "success", "data": ltp_data})

@orders_bp.route('/holdings')
@check_session_validity
def holdings():
    broker = session.get('broker')
    if not broker:
        logger.error("Broker not set in session")
        return "Broker not set in session", 400

    # Dynamically import broker-specific modules for API and mapping
    api_funcs = dynamic_import(broker, 'api.order_api', ['get_holdings'])
    mapping_funcs = dynamic_import(broker, 'mapping.order_data', [
        'map_portfolio_data', 'calculate_portfolio_statistics', 'transform_holdings_data'
    ])

    if not api_funcs or not mapping_funcs:
        logger.error(f"Error loading broker-specific modules for {broker}")
        return "Error loading broker-specific modules", 500

    login_username = session['user']
    auth_token = get_auth_token(login_username)

    if auth_token is None:
        logger.warning(f"No auth token found for user {login_username}")
        return redirect(url_for('auth.logout'))

    # Using the dynamically imported `get_holdings` function
    get_holdings = api_funcs['get_holdings']
    holdings_data = get_holdings(auth_token)
    logger.debug(f"Holdings data received: {holdings_data}")

    if 'status' in holdings_data and holdings_data['status'] == 'error':
        logger.error("Error in holdings data response")
        return redirect(url_for('auth.logout'))

    # Using the dynamically imported mapping functions
    map_portfolio_data = mapping_funcs['map_portfolio_data']
    calculate_portfolio_statistics = mapping_funcs['calculate_portfolio_statistics']
    transform_holdings_data = mapping_funcs['transform_holdings_data']

    holdings_data = map_portfolio_data(holdings_data)
    portfolio_stats = calculate_portfolio_statistics(holdings_data)
    holdings_data = transform_holdings_data(holdings_data)
    
    return render_template('holdings.html', holdings_data=holdings_data, portfolio_stats=portfolio_stats)

@orders_bp.route('/orderbook/export')
@check_session_validity
def export_orderbook():
    try:
        broker = session.get('broker')
        if not broker:
            logger.error("Broker not set in session")
            return "Broker not set in session", 400

        api_funcs = dynamic_import(broker, 'api.order_api', ['get_order_book'])
        mapping_funcs = dynamic_import(broker, 'mapping.order_data', ['map_order_data', 'transform_order_data'])

        if not api_funcs or not mapping_funcs:
            logger.error(f"Error loading broker-specific modules for {broker}")
            return "Error loading broker-specific modules", 500

        login_username = session['user']
        auth_token = get_auth_token(login_username)

        if auth_token is None:
            logger.warning(f"No auth token found for user {login_username}")
            return redirect(url_for('auth.logout'))

        order_data = api_funcs['get_order_book'](auth_token)
        if 'status' in order_data and order_data['status'] == 'error':
            logger.error("Error in order data response")
            return redirect(url_for('auth.logout'))

        order_data = mapping_funcs['map_order_data'](order_data=order_data)
        order_data = mapping_funcs['transform_order_data'](order_data)

        csv_data = generate_orderbook_csv(order_data)
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=orderbook.csv'}
        )
    except Exception as e:
        logger.error(f"Error exporting orderbook: {str(e)}")
        return "Error exporting orderbook", 500

@orders_bp.route('/tradebook/export')
@check_session_validity
def export_tradebook():
    try:
        broker = session.get('broker')
        if not broker:
            logger.error("Broker not set in session")
            return "Broker not set in session", 400

        api_funcs = dynamic_import(broker, 'api.order_api', ['get_trade_book'])
        mapping_funcs = dynamic_import(broker, 'mapping.order_data', ['map_trade_data', 'transform_tradebook_data'])

        if not api_funcs or not mapping_funcs:
            logger.error(f"Error loading broker-specific modules for {broker}")
            return "Error loading broker-specific modules", 500

        login_username = session['user']
        auth_token = get_auth_token(login_username)

        if auth_token is None:
            logger.warning(f"No auth token found for user {login_username}")
            return redirect(url_for('auth.logout'))

        tradebook_data = api_funcs['get_trade_book'](auth_token)
        if 'status' in tradebook_data and tradebook_data['status'] == 'error':
            logger.error("Error in tradebook data response")
            return redirect(url_for('auth.logout'))

        tradebook_data = mapping_funcs['map_trade_data'](tradebook_data)
        tradebook_data = mapping_funcs['transform_tradebook_data'](tradebook_data)

        csv_data = generate_tradebook_csv(tradebook_data)
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=tradebook.csv'}
        )
    except Exception as e:
        logger.error(f"Error exporting tradebook: {str(e)}")
        return "Error exporting tradebook", 500

@orders_bp.route('/positions/export')
@check_session_validity
def export_positions():
    try:
        broker = session.get('broker')
        if not broker:
            logger.error("Broker not set in session")
            return "Broker not set in session", 400

        api_funcs = dynamic_import(broker, 'api.order_api', ['get_positions'])
        mapping_funcs = dynamic_import(broker, 'mapping.order_data', [
            'map_position_data', 'transform_positions_data'
        ])

        if not api_funcs or not mapping_funcs:
            logger.error(f"Error loading broker-specific modules for {broker}")
            return "Error loading broker-specific modules", 500

        login_username = session['user']
        auth_token = get_auth_token(login_username)

        if auth_token is None:
            logger.warning(f"No auth token found for user {login_username}")
            return redirect(url_for('auth.logout'))

        positions_data = api_funcs['get_positions'](auth_token)
        if 'status' in positions_data and positions_data['status'] == 'error':
            logger.error("Error in positions data response")
            return redirect(url_for('auth.logout'))

        positions_data = mapping_funcs['map_position_data'](positions_data)
        positions_data = mapping_funcs['transform_positions_data'](positions_data)

        csv_data = generate_positions_csv(positions_data)
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=positions.csv'}
        )
    except Exception as e:
        logger.error(f"Error exporting positions: {str(e)}")
        return "Error exporting positions", 500

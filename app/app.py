"""Governance Hub Demo - Kubernetes Governance Service."""

import logging
import sys
from flask import Flask, jsonify
from flask_cors import CORS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)

# Import API blueprints after basic setup
from api import api_bp

# Create Flask app
app = Flask(__name__)

# Enable CORS
CORS(app)

# Register API blueprint
app.register_blueprint(api_bp, url_prefix='/api/v1')


@app.route('/health', methods=['GET'])
def root_health():
    """Root health check."""
    return jsonify({'status': 'ok', 'service': 'governance-hub-demo'}), 200


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    logger.info("Starting Governance Hub Demo service...")
    app.run(host='0.0.0.0', port=5000, debug=False)

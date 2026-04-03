"""Health check endpoint."""

import logging
from flask import Blueprint, jsonify
from validators import get_validators
from mutators import get_mutators

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health():
    """Return service health status."""
    try:
        validators_count = len(get_validators())
        mutators_count = len(get_mutators())

        return jsonify({
            'status': 'ok',
            'validators_loaded': validators_count,
            'mutators_loaded': mutators_count,
        }), 200

    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error': str(e),
        }), 500

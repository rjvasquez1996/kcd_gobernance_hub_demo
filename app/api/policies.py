"""API endpoint to list active policies."""

import logging
from flask import Blueprint, jsonify
from validators import get_validators
from mutators import get_mutators

logger = logging.getLogger(__name__)

policies_bp = Blueprint('policies', __name__)


@policies_bp.route('/policies', methods=['GET'])
def policies():
    """Return list of active validators and mutators."""
    try:
        validators = get_validators()
        mutators = get_mutators()

        validators_list = [
            {
                'name': v.__name__,
                'type': 'validator',
                'description': v.__doc__ or 'No description',
            }
            for v in validators
        ]

        mutators_list = [
            {
                'name': m.__name__,
                'type': 'mutator',
                'description': m.__doc__ or 'No description',
            }
            for m in mutators
        ]

        return jsonify({
            'validators': validators_list,
            'mutators': mutators_list,
            'total_validators': len(validators_list),
            'total_mutators': len(mutators_list),
        }), 200

    except Exception as e:
        logger.error(f"Error listing policies: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

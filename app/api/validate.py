"""Validation webhook endpoint."""

import json
import logging
from flask import Blueprint, request, jsonify
from validators import get_validators

logger = logging.getLogger(__name__)

validate_bp = Blueprint('validate', __name__)


@validate_bp.route('/validate', methods=['POST'])
def validate():
    """Handle validation webhook requests from Kubernetes.

    Kubernetes sends AdmissionReview requests with the resource to validate.
    We check all applicable validators and deny if any reject the resource.
    """
    try:
        review = request.get_json()
        if not review:
            return jsonify({'error': 'Invalid request body'}), 400

        # Extract the admission review request
        admission_review = review.get('request', {})
        uid = admission_review.get('uid', 'unknown')

        logger.info(f"Validating {admission_review.get('kind', {}).get('kind')} {admission_review.get('name')} in {admission_review.get('namespace')}")

        # Run all applicable validators
        validators_config = {}  # Can be extended with policy config
        validators = get_validators()

        for validator_class in validators:
            validator = validator_class(validators_config)

            if not validator.is_applicable(admission_review):
                continue

            allowed, message = validator.validate(admission_review)

            if not allowed:
                logger.warning(f"Validation failed: {validator_class.__name__} - {message}")
                return jsonify({
                    'apiVersion': 'admission.k8s.io/v1',
                    'kind': 'AdmissionReview',
                    'response': {
                        'uid': uid,
                        'allowed': False,
                        'status': {
                            'message': message,
                        }
                    }
                }), 200  # Return 200 but allowed=false

        logger.info(f"Validation passed for {uid}")

        # All validators passed
        return jsonify({
            'apiVersion': 'admission.k8s.io/v1',
            'kind': 'AdmissionReview',
            'response': {
                'uid': uid,
                'allowed': True,
            }
        }), 200

    except Exception as e:
        logger.error(f"Validation error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

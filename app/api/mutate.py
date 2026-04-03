"""Mutation webhook endpoint."""

import json
import base64
import logging
from flask import Blueprint, request, jsonify
from mutators import get_mutators

logger = logging.getLogger(__name__)

mutate_bp = Blueprint('mutate', __name__)


@mutate_bp.route('/mutate', methods=['POST'])
def mutate():
    """Handle mutation webhook requests from Kubernetes.

    Kubernetes sends AdmissionReview requests with the resource to mutate.
    We collect patches from all applicable mutators and return them.
    """
    try:
        review = request.get_json()
        if not review:
            return jsonify({'error': 'Invalid request body'}), 400

        # Extract the admission review request
        admission_review = review.get('request', {})
        uid = admission_review.get('uid', 'unknown')

        logger.info(f"Mutating {admission_review.get('kind', {}).get('kind')} {admission_review.get('name')} in {admission_review.get('namespace')}")

        # Collect patches from all applicable mutators
        mutators_config = {}  # Can be extended with policy config
        mutators = get_mutators()
        all_patches = []

        for mutator_class in mutators:
            mutator = mutator_class(mutators_config)

            if not mutator.is_applicable(admission_review):
                continue

            patches = mutator.generate_patch(admission_review)
            if patches:
                logger.debug(f"{mutator_class.__name__} generated {len(patches)} patch(es)")
                all_patches.extend(patches)

        # Prepare response
        response = {
            'apiVersion': 'admission.k8s.io/v1',
            'kind': 'AdmissionReview',
            'response': {
                'uid': uid,
                'allowed': True,
            }
        }

        # Add patches if any were generated
        if all_patches:
            patch_json = json.dumps(all_patches)
            patch_b64 = base64.b64encode(patch_json.encode()).decode()

            response['response']['patch'] = patch_b64
            response['response']['patchType'] = 'JSONPatch'

            logger.info(f"Generated {len(all_patches)} mutations for {uid}")
        else:
            logger.info(f"No mutations needed for {uid}")

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Mutation error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

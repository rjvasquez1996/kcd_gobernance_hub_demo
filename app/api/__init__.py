"""API blueprints."""

from flask import Blueprint

api_bp = Blueprint('api', __name__)

# Import and register all route blueprints
from api.validate import validate_bp
from api.mutate import mutate_bp
from api.policies import policies_bp
from api.health import health_bp

api_bp.register_blueprint(validate_bp)
api_bp.register_blueprint(mutate_bp)
api_bp.register_blueprint(policies_bp)
api_bp.register_blueprint(health_bp)

__all__ = ['api_bp']

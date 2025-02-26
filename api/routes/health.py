from flask import Blueprint, jsonify

health_check = Blueprint('health', __name__)

@health_check.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

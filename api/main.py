import os
from flask import Flask, request
from routes.health import health_check
from routes.suggestions import suggestions
from routes.preferences import preferences_bp
from routes.email_trigger import email_trigger  # Blueprint for triggering emails

def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('config.py', silent=True)

    # Register blueprints
    app.register_blueprint(health_check)
    app.register_blueprint(suggestions)
    app.register_blueprint(preferences_bp)
    app.register_blueprint(email_trigger)

    # Add an explicit health check endpoint for quick testing
    @app.route('/health')
    def health():
        return "OK", 200

    # Optional: Diagnostic route for debugging user_id propagation
    @app.route('/whoami')
    def whoami():
        user_id = request.args.get("user_id") or "unknown"
        return f"Hello, user {user_id}", 200

    return app

# Expose the Flask application object for production servers (e.g., Gunicorn)
app = create_app()

if __name__ == '__main__':
    # When running locally, use the development server.
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

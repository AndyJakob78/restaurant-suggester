import os
from flask import Flask
from routes.health import health_check
from routes.suggestions import suggestions
from routes.preferences import preferences_bp
from routes.email_trigger import email_trigger  # New blueprint for triggering emails

def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('config.py', silent=True)

    # Register blueprints
    app.register_blueprint(health_check)
    app.register_blueprint(suggestions)
    app.register_blueprint(preferences_bp)
    app.register_blueprint(email_trigger)

    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get("PORT", 8080))
    # Turn off debug mode and disable the reloader for production
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

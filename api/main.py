from flask import Flask
from routes.health import health_check
from routes.suggestions import suggestions

def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('config.py', silent=True)
    
    # Register Blueprints
    app.register_blueprint(health_check)
    app.register_blueprint(suggestions)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)

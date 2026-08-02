import os

from flask import Flask, redirect, url_for

from config import Config
from app.extensions import db, migrate, bcrypt, limiter
from app.utils import formatar_moeda, formatar_cpf


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(os.path.join(app.instance_path), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["BARCODE_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    limiter.init_app(app)

    # Blueprints
    from app.blueprints.auth.routes import auth_bp
    from app.blueprints.home.routes import home_bp
    from app.blueprints.produtos.routes import produtos_bp
    from app.blueprints.vendas.routes import vendas_bp
    from app.blueprints.clientes.routes import clientes_bp
    from app.blueprints.caixa.routes import caixa_bp
    from app.blueprints.cupons.routes import cupons_bp
    from app.blueprints.usuarios.routes import usuarios_bp
    from app.blueprints.relatorios.routes import relatorios_bp
    from app.blueprints.entregas.routes import entregas_bp
    from app.blueprints.logs.routes import logs_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(produtos_bp)
    app.register_blueprint(vendas_bp)
    app.register_blueprint(clientes_bp)
    app.register_blueprint(caixa_bp)
    app.register_blueprint(cupons_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(relatorios_bp)
    app.register_blueprint(entregas_bp)
    app.register_blueprint(logs_bp)

    @app.route("/")
    def index():
        return redirect(url_for("home.pagina_home"))

    app.jinja_env.filters["moeda"] = formatar_moeda
    app.jinja_env.filters["cpf"] = formatar_cpf

    @app.context_processor
    def inject_globals():
        from flask import session

        return {
            "usuario_logado_nome": session.get("nome"),
            "usuario_logado_papel": session.get("papel"),
        }

    return app

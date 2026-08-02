from flask import Blueprint, render_template, request, jsonify

from app.models import LogAtividade
from app.utils import token_requerido, admin_requerido, pagina_admin_requerida

logs_bp = Blueprint("logs", __name__, url_prefix="/logs")


@logs_bp.route("")
@pagina_admin_requerida
def pagina_lista():
    return render_template("logs/lista.html")


@logs_bp.route("/api", methods=["GET"])
@token_requerido
@admin_requerido
def api_listar_logs():
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = 50
    query = LogAtividade.query.order_by(LogAtividade.criado_em.desc())
    total = query.count()
    logs = query.offset((pagina - 1) * por_pagina).limit(por_pagina).all()
    return jsonify({
        "logs": [l.to_dict() for l in logs],
        "total": total,
        "pagina": pagina,
        "paginas": (total + por_pagina - 1) // por_pagina,
    })

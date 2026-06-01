"""
=======================================================
  MONITOR PNCP - EDITORA LIVRO IDEAL
  Servidor Python (Flask)
  Arquivo: server.py
=======================================================

INSTALAÇÃO (rode uma vez no terminal):
  pip install flask flask-cors requests schedule

COMO RODAR:
  python server.py

ACESSO:
  http://localhost:3001/api/licitacoes
  http://localhost:3001/api/status
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import schedule
import threading
import time
import logging
from datetime import datetime
from buscador import buscar_licitacoes

# ── Configuração do servidor ──────────────────────────
app = Flask(__name__)
CORS(app)  # Permite acesso do navegador (resolve o CORS)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ── Cache em memória ──────────────────────────────────
cache = {
    "dados": [],
    "atualizado_em": None,
    "total_pncp": 0
}

CACHE_TTL_HORAS = 1  # Tempo de vida do cache em horas


def cache_valido() -> bool:
    """Verifica se o cache ainda está dentro do tempo de vida."""
    if not cache["atualizado_em"]:
        return False
    diff = (datetime.now() - cache["atualizado_em"]).total_seconds()
    return diff < (CACHE_TTL_HORAS * 3600)


def atualizar_cache(**kwargs):
    """Busca dados frescos no PNCP e salva no cache."""
    log.info("🔍 Buscando dados frescos no PNCP...")
    try:
        resultado = buscar_licitacoes(**kwargs)
        cache["dados"] = resultado["itens"]
        cache["total_pncp"] = resultado["total_pncp"]
        cache["atualizado_em"] = datetime.now()
        log.info(f"✅ Cache atualizado: {len(cache['dados'])} licitações educacionais")
    except Exception as e:
        log.error(f"❌ Erro ao atualizar cache: {e}")


# ── Rotas da API ──────────────────────────────────────

@app.route("/api/status")
def status():
    """Rota de status — verifica se o servidor está vivo."""
    return jsonify({
        "status": "ok",
        "versao": "1.0",
        "cache_registros": len(cache["dados"]),
        "cache_atualizado": (
            cache["atualizado_em"].strftime("%d/%m/%Y %H:%M:%S")
            if cache["atualizado_em"] else "vazio"
        ),
        "total_pncp": cache["total_pncp"]
    })


@app.route("/api/licitacoes")
def licitacoes():
    """
    Rota principal — retorna licitações educacionais do PNCP.

    Parâmetros (query string):
        dtInicio  → data inicial AAAA-MM-DD (padrão: -90 dias)
        dtFim     → data final   AAAA-MM-DD (padrão: hoje)
        uf        → sigla do estado (ex: CE, SP, MG)
        modalidade→ código PNCP (6=pregão, 8=dispensa, 9=inexig.)
        texto     → palavra-chave para filtrar objeto/editora
        forcar    → true para ignorar cache e buscar agora
    """
    dt_inicio  = request.args.get("dtInicio", "")
    dt_fim     = request.args.get("dtFim", "")
    uf         = request.args.get("uf", "")
    modalidade = request.args.get("modalidade", "")
    texto      = request.args.get("texto", "").strip().lower()
    forcar     = request.args.get("forcar", "false").lower() == "true"

    try:
        # Atualiza cache se necessário
        if not cache_valido() or forcar:
            atualizar_cache(
                dt_inicio=dt_inicio,
                dt_fim=dt_fim,
                uf=uf,
                modalidade=modalidade
            )

        # Filtragem local por texto (editora / título)
        dados = cache["dados"]
        if texto:
            dados = [
                r for r in dados
                if texto in r.get("objeto", "").lower()
                or texto in r.get("editora", "").lower()
                or texto in r.get("municipio", "").lower()
            ]

        return jsonify({
            "sucesso": True,
            "total": len(dados),
            "total_pncp": cache["total_pncp"],
            "atualizado_em": (
                cache["atualizado_em"].isoformat()
                if cache["atualizado_em"] else None
            ),
            "dados": dados
        })

    except Exception as e:
        log.error(f"Erro na rota /api/licitacoes: {e}")
        return jsonify({"sucesso": False, "erro": str(e)}), 500


# ── Atualização automática a cada hora ───────────────

def loop_agendamento():
    """Roda o agendador em thread separada para não bloquear o Flask."""
    while True:
        schedule.run_pending()
        time.sleep(60)


schedule.every(1).hours.do(atualizar_cache)


# ── Inicialização ─────────────────────────────────────

if __name__ == "__main__":
    PORT = 3001

    print("=" * 55)
    print("  🚀 MONITOR PNCP — EDITORA LIVRO IDEAL")
    print("=" * 55)
    print(f"  Servidor: http://localhost:{PORT}")
    print(f"  Status:   http://localhost:{PORT}/api/status")
    print(f"  Dados:    http://localhost:{PORT}/api/licitacoes")
    print("=" * 55)

    # Primeira carga ao iniciar
    threading.Thread(target=atualizar_cache, daemon=True).start()

    # Thread do agendador
    threading.Thread(target=loop_agendamento, daemon=True).start()

import os
port = int(os.environ.get("PORT", 3001))
app.run(host="0.0.0.0", port=port, debug=False)

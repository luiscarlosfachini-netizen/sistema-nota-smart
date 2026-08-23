from datetime import datetime
import os
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "sua-chave-secreta-padrao"
)

# Conexão com o Supabase via variável de ambiente do Render
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
  database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# --- MODELOS DO BANCO DE DADOS ---
class ClienteModel(db.Model):
  __tablename__ = "clientes"
  id = db.Column(db.Integer, primary_key=True)
  empresa = db.Column(db.String(150))
  cnpj = db.Column(db.String(30))
  contato = db.Column(db.String(100))
  telefone = db.Column(db.String(30))
  sistema = db.Column(db.String(50))
  status_fmt = db.Column(db.String(20), default="ATIVO")
  modulos = db.Column(db.String(200))
  vencimento_cert = db.Column(db.String(30))


class CobrancaModel(db.Model):
  __tablename__ = "cobrancas"
  id = db.Column(db.Integer, primary_key=True)
  tipo_fmt = db.Column(db.String(30))
  nome_exibicao = db.Column(db.String(150))
  valor = db.Column(db.Float, default=0.0)
  data_vencimento = db.Column(db.String(30))
  status_fmt = db.Column(db.String(30))
  mes = db.Column(db.String(20))


# --- ROTAS PRINCIPAIS / DASHBOARD ---
@app.route("/")
@app.route("/dashboard")
def dashboard():
  tab = request.args.get("tab", "clientes")
  mes = request.args.get("mes", datetime.now().strftime("%Y-%m"))

  try:
    clientes_db = ClienteModel.query.all()
    cobrancas_db = CobrancaModel.query.filter_by(mes=mes).all()

    # Serialização manual para dicionários (evita erros no tojson do Jinja)
    clientes = []
    for c in clientes_db:
      clientes.append({
          "id": c.id,
          "empresa": c.empresa,
          "cnpj": c.cnpj,
          "contato": c.contato,
          "telefone": c.telefone,
          "sistema": c.sistema,
          "status_fmt": c.status_fmt,
          "modulos": c.modulos,
          "vencimento_cert": c.vencimento_cert,
      })

    cobrancas = []
    for cob in cobrancas_db:
      cobrancas.append({
          "id": cob.id,
          "tipo_fmt": cob.tipo_fmt,
          "nome_exibicao": cob.nome_exibicao,
          "valor": cob.valor,
          "data_vencimento": cob.data_vencimento,
          "status_fmt": cob.status_fmt,
          "mes": cob.mes,
      })

  except Exception as e:
    print(f"Erro ao consultar banco de dados: {e}")
    clientes = []
    cobrancas = []

  return render_template(
      "dashboard.html",
      clientes=clientes,
      cobrancas=cobrancas,
      tab_atual=tab,
      mes_atual=mes,
  )


# --- ROTAS DE EDIÇÃO / CADASTRO ---


@app.route("/cliente/editar", methods=["POST"])
def cliente_editar():
  tab = request.form.get("tab", "clientes")
  try:
    cliente_id_raw = request.form.get("id")
    if not cliente_id_raw:
      flash("Erro: ID do cliente não informado.", "danger")
      return redirect(url_for("dashboard", tab=tab))

    cliente_id = int(cliente_id_raw)
    c = ClienteModel.query.get(cliente_id)

    if c:
      c.empresa = request.form.get("empresa")
      c.cnpj = request.form.get("cnpj")
      c.contato = request.form.get("contato")
      c.telefone = request.form.get("telefone")
      c.sistema = request.form.get("sistema")
      c.status_fmt = request.form.get("status_cliente", "ATIVO")
      c.modulos = request.form.get("modulos")

      venc_cert = request.form.get("vencimento_cert")
      if venc_cert:
        c.vencimento_cert = venc_cert

      db.session.commit()
      flash("Cliente atualizado com sucesso!", "success")
    else:
      flash("Cliente não encontrado no banco de dados.", "warning")
  except Exception as e:
    db.session.rollback()
    print(f"Erro ao atualizar cliente: {e}")
    flash(f"Erro crítico ao salvar alterações do cliente: {e}", "danger")

  return redirect(url_for("dashboard", tab=tab))


@app.route("/financeiro/editar", methods=["POST"])
def financeiro_editar():
  mes = request.form.get("mes", datetime.now().strftime("%Y-%m"))
  tab = request.form.get("tab", "financeiro")
  try:
    lanc_id_raw = request.form.get("id")
    if not lanc_id_raw:
      flash("Erro: ID do lançamento não informado.", "danger")
      return redirect(url_for("dashboard", tab=tab, mes=mes))

    lanc_id = int(lanc_id_raw)
    cob = CobrancaModel.query.get(lanc_id)

    if cob:
      cob.tipo_fmt = request.form.get("tipo")
      cob.nome_exibicao = request.form.get("cliente_nome")

      valor_raw = request.form.get("valor", "0")
      if isinstance(valor_raw, str):
        valor_raw = (
            valor_raw.replace("R$", "").replace(".", "").replace(",", ".").strip()
        )
      cob.valor = float(valor_raw) if valor_raw else 0.0

      cob.data_vencimento = request.form.get("data_vencimento")
      cob.status_fmt = request.form.get("status_pagamento")
      cob.mes = mes

      db.session.commit()
      flash("Lançamento financeiro atualizado com sucesso!", "success")
    else:
      flash("Lançamento não encontrado.", "warning")
  except Exception as e:
    db.session.rollback()
    print(f"Erro ao atualizar lançamento financeiro: {e}")
    flash(f"Erro ao salvar lançamento: {e}", "danger")

  return redirect(url_for("dashboard", tab=tab, mes=mes))


if __name__ == "__main__":
  app.run(debug=True)

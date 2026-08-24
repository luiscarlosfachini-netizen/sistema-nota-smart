from datetime import datetime
import os
import calendar
import pandas as pd
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from functools import wraps

app = Flask(__name__)
app.secret_key = "sua_chave_secreta_aqui"

# Configuração do Banco de Dados PostgreSQL no Supabase com o search_path explícito
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "postgresql://postgres.bmnvxtcdmtuklmpxelwa:Spike%4077991340@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ==========================================
# MODELOS DO BANCO DE DADOS (SUPABASE)
# ==========================================
class ClienteModel(db.Model):
    __tablename__ = "clientes"
    id = db.Column(db.Integer, primary_key=True)
    empresa = db.Column(db.String(150), nullable=False)
    cnpj = db.Column(db.String(30))
    contato = db.Column(db.String(100))
    telefone = db.Column(db.String(30))
    sistema = db.Column(db.String(50))
    status_fmt = db.Column(db.String(20), default="ATIVO")
    modulos = db.Column(db.String(100))
    vencimento_cert = db.Column(db.String(20))

class CobrancaModel(db.Model):
    __tablename__ = "cobrancas"
    id = db.Column(db.Integer, primary_key=True)
    tipo_fmt = db.Column(db.String(20))
    nome_exibicao = db.Column(db.String(150))
    valor = db.Column(db.Float, default=0.0)
    data_vencimento = db.Column(db.String(20))
    status_fmt = db.Column(db.String(20), default="A VENCER")
    mes = db.Column(db.String(10))

class UsuarioModel(db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    senha = db.Column(db.String(100))
    cargo = db.Column(db.String(30), default="Admin")
    foto = db.Column(db.String(255), default="")


with app.app_context():
    db.create_all()

    if ClienteModel.query.count() == 0:
        ARQUIVO_EXCEL = "Clientes NOTA SMART!.xlsx"
        if os.path.exists(ARQUIVO_EXCEL):
            try:
                df = pd.read_excel(ARQUIVO_EXCEL, engine="openpyxl")
                for _, row in df.iterrows():
                    novo_c = ClienteModel(
                        empresa=str(row.get("Empresa", row.get("Cliente", "Empresa Exemplo"))),
                        cnpj=str(row.get("CNPJ", "")),
                        contato=str(row.get("Contato", "")),
                        telefone=str(row.get("Telefone", "")),
                        sistema=str(row.get("Sistema", "Retaguarda")),
                        status_fmt=str(row.get("Status", "ATIVO")),
                        modulos=str(row.get("Módulos", "")),
                        vencimento_cert="2026-12-15",
                    )
                    db.session.add(novo_c)
                db.session.commit()
            except Exception as e:
                print(f"Erro ao importar planilha: {e}")

    # Cria usuário admin com as credenciais solicitadas
    if UsuarioModel.query.count() == 0:
        admin_padrao = UsuarioModel(
            nome="Administrador",
            email="luisfachini",
            senha="123456",
            cargo="Admin",
        )
        db.session.add(admin_padrao)
        db.session.commit()


# ==========================================
# DECORATOR DE AUTENTICAÇÃO
# ==========================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# ROTAS DE AUTENTICAÇÃO
# ==========================================
@app.route("/", methods=["GET"])
def index():
    if "usuario_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")
        
        usuario = UsuarioModel.query.filter_by(email=email, senha=senha).first()
        if usuario:
            session["usuario_id"] = usuario.id
            return redirect(url_for("dashboard"))
        else:
            flash("Usuário ou senha incorretos!", "error")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ==========================================
# ROTA PRINCIPAL: DASHBOARD
# ==========================================
@app.route("/dashboard")
@login_required
def dashboard():
    db.session.expire_all()

    usuario_ativo = db.session.get(UsuarioModel, session["usuario_id"])
    if not usuario_ativo:
        session.clear()
        return redirect(url_for("login"))

    usuarios_db = UsuarioModel.query.all()
    clientes_db = ClienteModel.query.order_by(ClienteModel.empresa.asc()).all()
    cobrancas_db = CobrancaModel.query.all()

    tab = request.args.get("tab", "clientes")
    mes_atual = request.args.get("mes", datetime.now().strftime("%Y-%m"))
    
    # Filtros do Relatório Financeiro
    mes_relatorio = request.args.get("mes_relatorio", "")
    tipo_relatorio = request.args.get("tipo_relatorio", "")
    status_relatorio = request.args.get("status_relatorio", "")
    filtro_cliente = request.args.get("filtro_cliente", "")

    cobrancas_mes = [c for c in cobrancas_db if c.mes == mes_atual]

    cobrancas_relatorio = cobrancas_db
    if mes_relatorio:
        cobrancas_relatorio = [c for c in cobrancas_relatorio if c.mes == mes_relatorio]
    if tipo_relatorio:
        cobrancas_relatorio = [c for c in cobrancas_relatorio if c.tipo_fmt == tipo_relatorio]
    if status_relatorio:
        cobrancas_relatorio = [c for c in cobrancas_relatorio if c.status_fmt == status_relatorio]
    if filtro_cliente:
        cobrancas_relatorio = [c for c in cobrancas_relatorio if c.nome_exibicao == filtro_cliente]

    total_receita = sum(float(c.valor) for c in cobrancas_mes if c.tipo_fmt == "RECEITA" and c.status_fmt == "PAGO")
    total_custo = sum(float(c.valor) for c in cobrancas_mes if c.tipo_fmt == "DESPESA" and c.status_fmt == "PAGO")
    lucro_livre = total_receita - total_custo

    certificados = []
    for c in clientes_db:
        if c.status_fmt != "ATIVO":
            continue

        venc_str = c.vencimento_cert
        dias = 999
        status_cor = "verde"
        vencimento_fmt = "-"
        vencimento_raw = ""

        if venc_str:
            try:
                if hasattr(venc_str, "strftime"):
                    dt_venc = datetime(venc_str.year, venc_str.month, venc_str.day)
                    vencimento_raw = venc_str.strftime("%Y-%m-%d")
                else:
                    dt_venc = datetime.strptime(str(venc_str).strip(), "%Y-%m-%d")
                    vencimento_raw = str(venc_str).strip()

                dias = (dt_venc - datetime.now()).days
                vencimento_fmt = dt_venc.strftime("%d/%m/%Y")

                if dias < 0:
                    status_cor = "vermelho"
                elif dias <= 15:
                    status_cor = "amarelo"
            except Exception as e:
                pass

        certificados.append({
            "id": c.id,
            "empresa": c.empresa,
            "contato": c.contato,
            "telefone": c.telefone,
            "vencimento_raw": vencimento_raw,
            "vencimento_fmt": vencimento_fmt,
            "dias": dias,
            "status_cor": status_cor,
        })

    certificados = sorted(certificados, key=lambda x: x["dias"])

    clientes_dict = []
    for c in clientes_db:
        v_raw = ""
        if c.vencimento_cert:
            if hasattr(c.vencimento_cert, "strftime"):
                v_raw = c.vencimento_cert.strftime("%Y-%m-%d")
            else:
                v_raw = str(c.vencimento_cert).strip()

        clientes_dict.append({
            "id": c.id, "empresa": c.empresa, "cnpj": c.cnpj, "contato": c.contato, 
            "telefone": c.telefone, "sistema": c.sistema, "status_fmt": c.status_fmt, 
            "modulos": c.modulos, "vencimento_cert": v_raw,
        })

    cobrancas_mes_dict = [{"id": c.id, "tipo_fmt": c.tipo_fmt, "nome_exibicao": c.nome_exibicao, "valor": c.valor, "data_vencimento": c.data_vencimento, "status_fmt": c.status_fmt, "mes": c.mes} for c in cobrancas_mes]
    todas_cobrancas_dict = [{"id": c.id, "tipo_fmt": c.tipo_fmt, "nome_exibicao": c.nome_exibicao, "valor": c.valor, "data_vencimento": c.data_vencimento, "status_fmt": c.status_fmt, "mes": c.mes} for c in cobrancas_db]
    cobrancas_rel_dict = [{"id": c.id, "tipo_fmt": c.tipo_fmt, "nome_exibicao": c.nome_exibicao, "valor": c.valor, "data_vencimento": c.data_vencimento, "status_fmt": c.status_fmt, "mes": c.mes} for c in cobrancas_relatorio]
    usuarios_dict = [{"id": u.id, "nome": u.nome, "email": u.email, "cargo": u.cargo, "foto": u.foto} for u in usuarios_db]

    return render_template(
        "dashboard.html",
        usuario=usuario_ativo, usuarios=usuarios_dict, clientes=clientes_dict,
        cobrancas=cobrancas_mes_dict, todas_cobrancas=todas_cobrancas_dict,
        cobrancas_relatorio=cobrancas_rel_dict, total_receita=total_receita,
        total_custo=total_custo, lucro_livre=lucro_livre, certificados=certificados,
        tab=tab, mes_atual=mes_atual,
        mes_relatorio=mes_relatorio, filtro_cliente=filtro_cliente,
        tipo_relatorio=tipo_relatorio, status_relatorio=status_relatorio
    )

# ==========================================
# ROTAS DE CLIENTES
# ==========================================
@app.route("/cliente/novo", methods=["POST"])
@login_required
def cliente_novo():
    novo_cliente = ClienteModel(
        empresa=request.form.get("empresa"), cnpj=request.form.get("cnpj"),
        contato=request.form.get("contato"), telefone=request.form.get("telefone"),
        sistema=request.form.get("sistema"), status_fmt=request.form.get("status_cliente", "ATIVO"),
        modulos=request.form.get("modulos"), vencimento_cert=request.form.get("vencimento_cert"),
    )
    db.session.add(novo_cliente)
    db.session.commit()
    return redirect(url_for("dashboard", tab=request.form.get("tab", "clientes")))

@app.route("/cliente/editar", methods=["POST"])
@login_required
def cliente_editar():
    c = db.session.get(ClienteModel, int(request.form.get("id")))
    if c:
        c.empresa = request.form.get("empresa")
        c.cnpj = request.form.get("cnpj")
        c.contato = request.form.get("contato")
        c.telefone = request.form.get("telefone")
        c.sistema = request.form.get("sistema")
        c.status_fmt = request.form.get("status_cliente", "ATIVO")
        c.modulos = request.form.get("modulos")
        c.vencimento_cert = request.form.get("vencimento_cert")
        db.session.commit()
    return redirect(url_for("dashboard", tab=request.form.get("tab", "clientes")))

@app.route("/cliente/deletar/<int:id>")
@login_required
def cliente_deletar(id):
    c = db.session.get(ClienteModel, id)
    if c:
        db.session.delete(c)
        db.session.commit()
    return redirect(url_for("dashboard", tab=request.args.get("tab", "clientes")))

@app.route("/cliente/deletar_varios", methods=["POST"])
@login_required
def cliente_deletar_varios():
    ids = request.form.get("ids", "").split(",")
    for cid in ids:
        if cid.strip():
            c = db.session.get(ClienteModel, int(cid))
            if c: db.session.delete(c)
    db.session.commit()
    return redirect(url_for("dashboard", tab=request.form.get("tab", "clientes")))

@app.route("/cliente/atualizar-cert", methods=["POST"])
@login_required
def atualizar_cert():
    c = db.session.get(ClienteModel, int(request.form.get("id")))
    if c:
        c.vencimento_cert = request.form.get("vencimento_cert")
        db.session.commit()
    return redirect(url_for("dashboard", tab=request.form.get("tab", "certificados")))


# ==========================================
# ROTAS FINANCEIRAS
# ==========================================
@app.route("/financeiro/novo", methods=["POST"])
@login_required
def financeiro_novo():
    mes_base_str = request.form.get("mes", datetime.now().strftime("%Y-%m"))
    tipo = request.form.get("tipo")
    cliente_nome = request.form.get("cliente_nome")
    valor = float(request.form.get("valor", 0))
    dt_venc = datetime.strptime(request.form.get("data_vencimento"), "%Y-%m-%d")
    status_pagamento = request.form.get("status_pagamento", "A VENCER")
    
    qtd_meses = int(request.form.get("qtd_meses", 1)) if request.form.get("recorrente") == "on" else 1

    for i in range(qtd_meses):
        mes_add = dt_venc.month - 1 + i
        new_year = dt_venc.year + mes_add // 12
        new_month = mes_add % 12 + 1
        new_day = min(dt_venc.day, calendar.monthrange(new_year, new_month)[1])
        new_date = datetime(new_year, new_month, new_day)
        
        nova_cobranca = CobrancaModel(
            tipo_fmt=tipo, nome_exibicao=cliente_nome, valor=valor,
            data_vencimento=new_date.strftime("%Y-%m-%d"),
            status_fmt=status_pagamento, mes=new_date.strftime("%Y-%m"),
        )
        db.session.add(nova_cobranca)

    db.session.commit()
    return redirect(url_for("dashboard", tab=request.form.get("tab", "financeiro"), mes=mes_base_str))

@app.route("/financeiro/editar", methods=["POST"])
@login_required
def financeiro_editar():
    mes = request.form.get("mes", datetime.now().strftime("%Y-%m"))
    cob = db.session.get(CobrancaModel, int(request.form.get("id")))
    if cob:
        cob.tipo_fmt = request.form.get("tipo")
        cob.nome_exibicao = request.form.get("cliente_nome")
        cob.valor = float(request.form.get("valor", 0))
        cob.data_vencimento = request.form.get("data_vencimento")
        cob.status_fmt = request.form.get("status_pagamento")
        cob.mes = mes
        db.session.commit()
    return redirect(url_for("dashboard", tab=request.form.get("tab", "financeiro"), mes=mes))

@app.route("/financeiro/pagar/<int:id>")
@login_required
def financeiro_pagar(id):
    mes = request.args.get("mes", datetime.now().strftime("%Y-%m"))
    cob = db.session.get(CobrancaModel, id)
    if cob:
        cob.status_fmt = "PAGO"
        db.session.commit()
    return redirect(url_for("dashboard", tab=request.args.get("tab", "financeiro"), mes=mes))

@app.route("/financeiro/deletar/<int:id>")
@login_required
def financeiro_deletar(id):
    mes = request.args.get("mes", datetime.now().strftime("%Y-%m"))
    cob = db.session.get(CobrancaModel, id)
    if cob:
        db.session.delete(cob)
        db.session.commit()
    return redirect(url_for("dashboard", tab=request.args.get("tab", "financeiro"), mes=mes))

@app.route("/financeiro/deletar_varios", methods=["POST"])
@login_required
def financeiro_deletar_varios():
    ids = request.form.get("ids", "").split(",")
    for fid in ids:
        if fid.strip():
            cob = db.session.get(CobrancaModel, int(fid))
            if cob: db.session.delete(cob)
    db.session.commit()
    return redirect(url_for("dashboard", tab=request.form.get("tab", "financeiro")))


# ==========================================
# ROTAS DE USUÁRIOS E PERFIL
# ==========================================
@app.route("/usuario/configurar", methods=["POST"])
@login_required
def usuario_configurar():
    u = db.session.get(UsuarioModel, session["usuario_id"])
    if u:
        u.nome = request.form.get("nome", u.nome)
        u.email = request.form.get("email", u.email)
        u.foto = request.form.get("foto", u.foto)
        nova_senha = request.form.get("senha")
        if nova_senha and nova_senha.strip() != "":
            u.senha = nova_senha.strip()
        db.session.commit()
        flash("Perfil atualizado com sucesso!", "success")
    return redirect(url_for("dashboard", tab=request.form.get("tab", "clientes")))

@app.route("/usuario/novo", methods=["POST"])
@login_required
def usuario_novo():
    novo_u = UsuarioModel(
        nome=request.form.get("nome"), 
        email=request.form.get("email"),
        senha=request.form.get("senha"), 
        cargo=request.form.get("cargo", "Admin"),
        foto=request.form.get("foto", "")
    )
    db.session.add(novo_u)
    db.session.commit()
    return redirect(url_for("dashboard", tab=request.form.get("tab", "clientes")))

@app.route("/usuario/deletar/<int:id>")
@login_required
def usuario_deletar(id):
    u = db.session.get(UsuarioModel, id)
    if u:
        db.session.delete(u)
        db.session.commit()
    return redirect(url_for("dashboard", tab=request.args.get("tab", "clientes")))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

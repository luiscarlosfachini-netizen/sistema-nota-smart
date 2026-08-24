import os
import calendar
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chave_secreta_padrao_nota_smart")

# ==========================================
# CONFIGURAÇÃO DO BANCO DE DADOS (SUPABASE)
# ==========================================
DEFAULT_SUPABASE_URI = "postgresql://postgres.bmnvxtcdmtuklmpxelwa:Spike%4077991340@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_SUPABASE_URI)

# Correção de compatibilidade para URIs do PostgreSQL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ==========================================
# MODELOS DO BANCO DE DADOS
# ==========================================
class UsuarioModel(db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(100), nullable=False)
    cargo = db.Column(db.String(50), default="Operador")
    foto = db.Column(db.String(255), nullable=True)

class ClienteModel(db.Model):
    __tablename__ = "clientes"
    id = db.Column(db.Integer, primary_key=True)
    empresa = db.Column(db.String(100), nullable=False)
    cnpj = db.Column(db.String(20), nullable=True)
    contato = db.Column(db.String(100), nullable=True)
    telefone = db.Column(db.String(30), nullable=True)
    sistema = db.Column(db.String(50), nullable=True)
    status_fmt = db.Column(db.String(20), default="ATIVO")
    modulos = db.Column(db.String(200), nullable=True)
    vencimento_cert = db.Column(db.String(20), nullable=True)

class CobrancaModel(db.Model):
    __tablename__ = "cobrancas"
    id = db.Column(db.Integer, primary_key=True)
    tipo_fmt = db.Column(db.String(20), nullable=False)  # RECEITA ou DESPESA
    nome_exibicao = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data_vencimento = db.Column(db.String(20), nullable=False)
    status_fmt = db.Column(db.String(20), default="A VENCER")  # PAGO, A VENCER, VENCIDO
    mes = db.Column(db.String(20), nullable=True)

# Cria as tabelas e garante um usuário padrão apenas se ainda não existir
with app.app_context():
    db.create_all()
    if not UsuarioModel.query.filter_by(email="admin@admin.com").first():
        admin = UsuarioModel(
            nome="Administrador",
            email="admin@admin.com",
            senha="admin",
            cargo="Admin"
        )
        db.session.add(admin)
        db.session.commit()

# ==========================================
# DECORATOR E ROTAS DE AUTENTICAÇÃO
# ==========================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def index():
    if "usuario_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")

        usuario = UsuarioModel.query.filter_by(email=email).first()

        if usuario and usuario.senha == senha:
            session["usuario_id"] = usuario.id
            return redirect(url_for("dashboard"))

        flash("E-mail ou senha incorretos.", "error")
        return redirect(url_for("login"))

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
    cobrancas_db = CobrancaModel.query.order_by(CobrancaModel.data_vencimento.asc()).all()

    tab = request.args.get("tab", "clientes")
    
    hoje = datetime.now()
    primeiro_dia_mes = hoje.replace(day=1).strftime("%Y-%m-%d")
    ultimo_dia_mes = hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1]).strftime("%Y-%m-%d")

    data_inicio = request.args.get("data_inicio", primeiro_dia_mes)
    data_fim = request.args.get("data_fim", ultimo_dia_mes)

    data_inicio_rel = request.args.get("data_inicio_rel", "")
    data_fim_rel = request.args.get("data_fim_rel", "")
    tipo_relatorio = request.args.get("tipo_relatorio", "")
    status_relatorio = request.args.get("status_relatorio", "")
    filtro_cliente = request.args.get("filtro_cliente", "")

    cobrancas_mes = [
        c for c in cobrancas_db 
        if c.data_vencimento and data_inicio <= c.data_vencimento <= data_fim
    ]

    cobrancas_relatorio = cobrancas_db
    if data_inicio_rel and data_fim_rel:
        cobrancas_relatorio = [
            c for c in cobrancas_relatorio 
            if c.data_vencimento and data_inicio_rel <= c.data_vencimento <= data_fim_rel
        ]
    elif data_inicio_rel:
        cobrancas_relatorio = [
            c for c in cobrancas_relatorio 
            if c.data_vencimento and c.data_vencimento >= data_inicio_rel
        ]
    elif data_fim_rel:
        cobrancas_relatorio = [
            c for c in cobrancas_relatorio 
            if c.data_vencimento and c.data_vencimento <= data_fim_rel
        ]

    if tipo_relatorio:
        cobrancas_relatorio = [c for c in cobrancas_relatorio if c.tipo_fmt == tipo_relatorio]
        
    if status_relatorio:
        cobrancas_relatorio = [c for c in cobrancas_relatorio if c.status_fmt == status_relatorio]
        
    if filtro_cliente:
        cobrancas_relatorio = [c for c in cobrancas_relatorio if filtro_cliente.lower() in (c.nome_exibicao or "").lower()]

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
            except Exception:
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

    def formatar_data_br(dt_str):
        if not dt_str:
            return "-"
        try:
            partes = str(dt_str).strip().split("-")
            if len(partes) == 3:
                return f"{partes[2]}/{partes[1]}/{partes[0]}"
        except Exception:
            pass
        return dt_str

    cobrancas_mes_dict = [
        {
            "id": c.id, "tipo_fmt": c.tipo_fmt, "nome_exibicao": c.nome_exibicao,
            "valor": c.valor, "data_vencimento": c.data_vencimento,
            "data_vencimento_fmt": formatar_data_br(c.data_vencimento),
            "status_fmt": c.status_fmt, "mes": c.mes
        } for c in cobrancas_mes
    ]

    todas_cobrancas_dict = [
        {
            "id": c.id, "tipo_fmt": c.tipo_fmt, "nome_exibicao": c.nome_exibicao,
            "valor": c.valor, "data_vencimento": c.data_vencimento,
            "data_vencimento_fmt": formatar_data_br(c.data_vencimento),
            "status_fmt": c.status_fmt, "mes": c.mes
        } for c in cobrancas_db
    ]

    cobrancas_rel_dict = [
        {
            "id": c.id, "tipo_fmt": c.tipo_fmt, "nome_exibicao": c.nome_exibicao,
            "valor": c.valor, "data_vencimento": c.data_vencimento,
            "data_vencimento_fmt": formatar_data_br(c.data_vencimento),
            "status_fmt": c.status_fmt, "mes": c.mes
        } for c in cobrancas_relatorio
    ]

    usuarios_dict = [{"id": u.id, "nome": u.nome, "email": u.email, "cargo": u.cargo, "foto": u.foto} for u in usuarios_db]

    return render_template(
        "dashboard.html",
        usuario=usuario_ativo, usuarios=usuarios_dict, clientes=clientes_dict,
        cobrancas=cobrancas_mes_dict, todas_cobrancas=todas_cobrancas_dict,
        cobrancas_relatorio=cobrancas_rel_dict, total_receita=total_receita,
        total_custo=total_custo, lucro_livre=lucro_livre, certificados=certificados,
        tab=tab, data_inicio=data_inicio, data_fim=data_fim,
        data_inicio_rel=data_inicio_rel, data_fim_rel=data_fim_rel,
        filtro_cliente=filtro_cliente, tipo_relatorio=tipo_relatorio, status_relatorio=status_relatorio
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

from datetime import datetime
import os
import pandas as pd
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "sua_chave_secreta_aqui"

# Configuração do Banco de Dados PostgreSQL no Supabase (com o '@' da senha codificado como %40)
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "postgresql://postgres:Spike%4077991340@db.bmnvxtcdmtuklmpxelwa.supabase.co:6453/postgres"
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


# Criar tabelas e importar planilha automaticamente na primeira execução
with app.app_context():
    db.create_all()

    # Se a tabela de clientes estiver vazia, importa da planilha
    if ClienteModel.query.count() == 0:
        ARQUIVO_EXCEL = "Clientes NOTA SMART!.xlsx"
        if os.path.exists(ARQUIVO_EXCEL):
            try:
                df = pd.read_excel(ARQUIVO_EXCEL, engine="openpyxl")
                for _, row in df.iterrows():
                    novo_c = ClienteModel(
                        empresa=str(
                            row.get(
                                "Empresa", row.get("Cliente", "Empresa Exemplo")
                            )
                        ),
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
                print("✅ Clientes da planilha importados para o Supabase!")
            except Exception as e:
                print(f"Erro ao importar planilha: {e}")

        # Cria um usuário admin padrão se não houver nenhum
        if UsuarioModel.query.count() == 0:
            admin_padrao = UsuarioModel(
                nome="Administrador",
                email="admin@notasmart.com",
                senha="123",
                cargo="Admin",
            )
            db.session.add(admin_padrao)
            db.session.commit()


# ==========================================
# ROTAS DE AUTENTICAÇÃO
# ==========================================
@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ==========================================
# ROTA PRINCIPAL: DASHBOARD
# ==========================================
@app.route("/dashboard")
def dashboard():
    usuario_ativo = UsuarioModel.query.first()
    usuarios_db = UsuarioModel.query.all()
    clientes_db = ClienteModel.query.all()
    cobrancas_db = CobrancaModel.query.all()

    tab = request.args.get("tab", "clientes")
    mes_atual = request.args.get("mes", datetime.now().strftime("%Y-%m"))
    filtro_cliente = request.args.get("filtro_cliente", "")
    data_inicio = request.args.get("data_inicio", "")
    data_fim = request.args.get("data_fim", "")

    cobrancas_mes = [c for c in cobrancas_db if c.mes == mes_atual]

    cobrancas_relatorio = cobrancas_db
    if filtro_cliente:
        cobrancas_relatorio = [
            c for c in cobrancas_relatorio if c.nome_exibicao == filtro_cliente
        ]

    total_receita = sum(
        float(c.valor)
        for c in cobrancas_mes
        if c.tipo_fmt == "RECEITA" and c.status_fmt == "PAGO"
    )
    total_custo = sum(
        float(c.valor)
        for c in cobrancas_mes
        if c.tipo_fmt == "DESPESA" and c.status_fmt == "PAGO"
    )
    lucro_livre = total_receita - total_custo

    certificados = []
    for c in clientes_db:
        venc_str = c.vencimento_cert
        dias = 999
        status_cor = "verde"
        vencimento_fmt = "-"

        if venc_str:
            try:
                dt_venc = datetime.strptime(venc_str, "%Y-%m-%d")
                dias = (dt_venc - datetime.now()).days
                vencimento_fmt = dt_venc.strftime("%d/%m/%Y")

                if dias < 0:
                    status_cor = "vermelho"
                elif dias <= 15:
                    status_cor = "amarelo"
            except:
                pass

        certificados.append(
            {
                "id": c.id,
                "empresa": c.empresa,
                "contato": c.contato,
                "telefone": c.telefone,
                "vencimento_raw": venc_str,
                "vencimento_fmt": vencimento_fmt,
                "dias": dias,
                "status_cor": status_cor,
            }
        )

    clientes_dict = [
        {
            "id": c.id,
            "empresa": c.empresa,
            "cnpj": c.cnpj,
            "contato": c.contato,
            "telefone": c.telefone,
            "sistema": c.sistema,
            "status_fmt": c.status_fmt,
            "modulos": c.modulos,
            "vencimento_cert": c.vencimento_cert,
        }
        for c in clientes_db
    ]

    cobrancas_mes_dict = [
        {
            "id": c.id,
            "tipo_fmt": c.tipo_fmt,
            "nome_exibicao": c.nome_exibicao,
            "valor": c.valor,
            "data_vencimento": c.data_vencimento,
            "status_fmt": c.status_fmt,
            "mes": c.mes,
        }
        for c in cobrancas_mes
    ]

    todas_cobrancas_dict = [
        {
            "id": c.id,
            "tipo_fmt": c.tipo_fmt,
            "nome_exibicao": c.nome_exibicao,
            "valor": c.valor,
            "data_vencimento": c.data_vencimento,
            "status_fmt": c.status_fmt,
            "mes": c.mes,
        }
        for c in cobrancas_db
    ]

    cobrancas_rel_dict = [
        {
            "id": c.id,
            "tipo_fmt": c.tipo_fmt,
            "nome_exibicao": c.nome_exibicao,
            "valor": c.valor,
            "data_vencimento": c.data_vencimento,
            "status_fmt": c.status_fmt,
            "mes": c.mes,
        }
        for c in cobrancas_relatorio
    ]

    usuarios_dict = [
        {
            "id": u.id,
            "nome": u.nome,
            "email": u.email,
            "cargo": u.cargo,
            "foto": u.foto,
        }
        for u in usuarios_db
    ]

    return render_template(
        "dashboard.html",
        usuario=usuario_ativo,
        usuarios=usuarios_dict,
        clientes=clientes_dict,
        cobrancas=cobrancas_mes_dict,
        todas_cobrancas=todas_cobrancas_dict,
        cobrancas_relatorio=cobrancas_rel_dict,
        total_receita=total_receita,
        total_custo=total_custo,
        lucro_livre=lucro_livre,
        certificados=certificados,
        tab=tab,
        mes_atual=mes_atual,
        filtro_cliente=filtro_cliente,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


# ==========================================
# ROTAS DE CLIENTES
# ==========================================
@app.route("/cliente/novo", methods=["POST"])
def cliente_novo():
    novo_cliente = ClienteModel(
        empresa=request.form.get("empresa"),
        cnpj=request.form.get("cnpj"),
        contato=request.form.get("contato"),
        telefone=request.form.get("telefone"),
        sistema=request.form.get("sistema"),
        status_fmt=request.form.get("status_cliente", "ATIVO"),
        modulos=request.form.get("modulos"),
        vencimento_cert=request.form.get("vencimento_cert"),
    )
    db.session.add(novo_cliente)
    db.session.commit()
    tab = request.form.get("tab", "clientes")
    return redirect(url_for("dashboard", tab=tab))


@app.route("/cliente/editar", methods=["POST"])
def cliente_editar():
    cliente_id = int(request.form.get("id"))
    c = ClienteModel.query.get(cliente_id)
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
    tab = request.form.get("tab", "clientes")
    return redirect(url_for("dashboard", tab=tab))


@app.route("/cliente/deletar/<int:id>")
def cliente_deletar(id):
    c = ClienteModel.query.get(id)
    if c:
        db.session.delete(c)
        db.session.commit()
    tab = request.args.get("tab", "clientes")
    return redirect(url_for("dashboard", tab=tab))


@app.route("/cliente/atualizar-cert", methods=["POST"])
def atualizar_cert():
    cliente_id = int(request.form.get("id"))
    c = ClienteModel.query.get(cliente_id)
    if c:
        c.vencimento_cert = request.form.get("vencimento_cert")
        db.session.commit()
    tab = request.form.get("tab", "certificados")
    return redirect(url_for("dashboard", tab=tab))


# ==========================================
# ROTAS FINANCEIRAS
# ==========================================
@app.route("/financeiro/novo", methods=["POST"])
def financeiro_novo():
    mes = request.form.get("mes", datetime.now().strftime("%Y-%m"))
    nova_cobranca = CobrancaModel(
        tipo_fmt=request.form.get("tipo"),
        nome_exibicao=request.form.get("cliente_nome"),
        valor=float(request.form.get("valor", 0)),
        data_vencimento=request.form.get("data_vencimento"),
        status_fmt=request.form.get("status_pagamento", "A VENCER"),
        mes=mes,
    )
    db.session.add(nova_cobranca)
    db.session.commit()
    tab = request.form.get("tab", "financeiro")
    return redirect(url_for("dashboard", tab=tab, mes=mes))


@app.route("/financeiro/editar", methods=["POST"])
def financeiro_editar():
    lanc_id = int(request.form.get("id"))
    mes = request.form.get("mes", datetime.now().strftime("%Y-%m"))
    cob = CobrancaModel.query.get(lanc_id)
    if cob:
        cob.tipo_fmt = request.form.get("tipo")
        cob.nome_exibicao = request.form.get("cliente_nome")
        cob.valor = float(request.form.get("valor", 0))
        cob.data_vencimento = request.form.get("data_vencimento")
        cob.status_fmt = request.form.get("status_pagamento")
        cob.mes = mes
        db.session.commit()
    tab = request.form.get("tab", "financeiro")
    return redirect(url_for("dashboard", tab=tab, mes=mes))


@app.route("/financeiro/pagar/<int:id>")
def financeiro_pagar(id):
    mes = request.args.get("mes", datetime.now().strftime("%Y-%m"))
    cob = CobrancaModel.query.get(id)
    if cob:
        cob.status_fmt = "PAGO"
        db.session.commit()
    tab = request.args.get("tab", "financeiro")
    return redirect(url_for("dashboard", tab=tab, mes=mes))


@app.route("/financeiro/deletar/<int:id>")
def financeiro_deletar(id):
    mes = request.args.get("mes", datetime.now().strftime("%Y-%m"))
    cob = CobrancaModel.query.get(id)
    if cob:
        db.session.delete(cob)
        db.session.commit()
    tab = request.args.get("tab", "financeiro")
    return redirect(url_for("dashboard", tab=tab, mes=mes))


# ==========================================
# ROTAS DE USUÁRIOS
# ==========================================
@app.route("/usuario/novo", methods=["POST"])
def usuario_novo():
    novo_u = UsuarioModel(
        nome=request.form.get("nome"),
        email=request.form.get("email"),
        senha=request.form.get("senha"),
        cargo="Operador",
    )
    db.session.add(novo_u)
    db.session.commit()
    tab = request.form.get("tab", "perfil")
    return redirect(url_for("dashboard", tab=tab))


@app.route("/usuario/editar", methods=["POST"])
def usuario_editar():
    u_id = int(request.form.get("id"))
    u = UsuarioModel.query.get(u_id)
    if u:
        u.nome = request.form.get("nome")
        u.email = request.form.get("email")
        db.session.commit()
    tab = request.form.get("tab", "perfil")
    return redirect(url_for("dashboard", tab=tab))


@app.route("/usuario/deletar/<int:id>")
def usuario_deletar(id):
    u = UsuarioModel.query.get(id)
    if u:
        db.session.delete(u)
        db.session.commit()
    tab = request.args.get("tab", "perfil")
    return redirect(url_for("dashboard", tab=tab))


if __name__ == "__main__":
    app.run(debug=True)

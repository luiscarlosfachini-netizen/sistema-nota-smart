from flask import Flask, render_template, request, redirect, url_for, session
from flask_login import login_required
from datetime import datetime
import calendar

# 1. INICIALIZAÇÃO OBRIGATÓRIA DO FLASK
app = Flask(__name__)

# Chave secreta necessária para gerenciar a 'session' de login
app.secret_key = "minha_chave_secreta_super_segura_aqui"

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
    
    # 1. ORDENAÇÃO POR DATA DE VENCIMENTO
    cobrancas_db = CobrancaModel.query.order_by(CobrancaModel.data_vencimento.asc()).all()

    tab = request.args.get("tab", "clientes")
    
    # 2. DEFINIÇÃO DO PERÍODO PADRÃO (MÊS ATUAL: PRIMEIRO E ÚLTIMO DIA)
    hoje = datetime.now()
    primeiro_dia_mes = hoje.replace(day=1).strftime("%Y-%m-%d")
    ultimo_dia_mes = hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1]).strftime("%Y-%m-%d")

    data_inicio = request.args.get("data_inicio", primeiro_dia_mes)
    data_fim = request.args.get("data_fim", ultimo_dia_mes)

    # Filtros do Relatório Financeiro
    data_inicio_rel = request.args.get("data_inicio_rel", "")
    data_fim_rel = request.args.get("data_fim_rel", "")
    tipo_relatorio = request.args.get("tipo_relatorio", "")
    status_relatorio = request.args.get("status_relatorio", "")
    filtro_cliente = request.args.get("filtro_cliente", "")

    # Lógica do Período na Aba Financeiro (Extrato)
    cobrancas_mes = [
        c for c in cobrancas_db 
        if c.data_vencimento and data_inicio <= c.data_vencimento <= data_fim
    ]

    # Lógica do Relatório Financeiro (Aba Relatórios)
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

    # Função Auxiliar para Formatar Data no Padrão BR (DD/MM/AAAA)
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
    app.run()

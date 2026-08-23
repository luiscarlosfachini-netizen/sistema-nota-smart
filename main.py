# --- ROTAS PRINCIPAIS / DASHBOARD ---
@app.route("/")
@app.route("/dashboard")
def dashboard():
  tab = request.args.get("tab", "clientes")
  mes = request.args.get("mes", datetime.now().strftime("%Y-%m"))

  try:
    clientes_db = ClienteModel.query.all()
    cobrancas_db = CobrancaModel.query.filter_by(mes=mes).all()

    # Converte os objetos do SQLAlchemy em dicionários para evitar erros no tojson
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

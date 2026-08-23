import os
from datetime import datetime
from fastapi import FastAPI, Request, Form, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import jinja2

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
DATABASE_URL = "sqlite:///./banco.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODELOS ---
class Cliente(Base):
    __tablename__ = "clientes"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(150), nullable=False)
    empresa = Column(String(150))
    cnpj = Column(String(30))
    contato = Column(String(100))
    telefone = Column(String(30))
    sistema = Column(String(100))
    status_cliente = Column(String(50)) # "ATIVO" ou "INATIVO"
    modulos = Column(String(200))
    vencimento_certificado = Column(String(50))

class Lancamento(Base):
    __tablename__ = "lancamentos"
    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String(200), nullable=False)
    valor = Column(Float, nullable=False)
    tipo = Column(String(30), nullable=False) # "RECEITA" ou "DESPESA"
    cliente_nome = Column(String(150))
    data_vencimento = Column(String(30))
    status_pagamento = Column(String(30)) # "A VENCER", "PAGO", "VENCIDO"

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(100))
    senha = Column(String(100))
    cargo = Column(String(50))

Base.metadata.create_all(bind=engine)

# --- APLICAÇÃO FASTAPI ---
app = FastAPI()

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

class SafeUndefined(jinja2.Undefined):
    def __str__(self):
        return ""
    def __int__(self):
        return 0
    def __float__(self):
        return 0.0

templates = Jinja2Templates(directory="templates")
templates.env.undefined = SafeUndefined

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def calcular_dias_vencimento(data_str):
    if not data_str:
        return 0
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M"):
        try:
            dt = datetime.strptime(data_str.strip()[:10], fmt if "-" in data_str else "%d/%m/%Y")
            delta = (dt - datetime.now()).days
            return delta
        except:
            continue
    return 0

# --- ROTAS PRINCIPAIS ---

@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request, 
    tab: str = "clientes", 
    mes: str = None, 
    data_inicio: str = None, 
    data_fim: str = None, 
    filtro_cliente: str = None,
    db: Session = Depends(get_db)
):
    clientes_db = db.query(Cliente).all()
    lancamentos_db = db.query(Lancamento).all()
    usuarios_db = db.query(Usuario).all()
    usuario_atual = db.query(Usuario).first()
    
    if not usuario_atual:
        usuario_atual = Usuario(nome="Administrador", email="admin@sistema.com", cargo="Admin")
        db.add(usuario_atual)
        db.commit()
        db.refresh(usuario_atual)
        usuarios_db = [usuario_atual]
        
    clientes = []
    for c in clientes_db:
        st_raw = str(c.status_cliente or "ATIVO").upper().strip()
        if any(w in st_raw for w in ["INATIVO", "0", "FALSE", "NAO", "OFF"]):
            st_fmt = "INATIVO"
            is_ativo = False
        else:
            st_fmt = "ATIVO"
            is_ativo = True
        
        dias_venc = calcular_dias_vencimento(c.vencimento_certificado)
        
        if dias_venc < 0:
            status_cor = "vermelho"
        elif dias_venc <= 30:
            status_cor = "amarelo"
        else:
            status_cor = "verde"
            
        venc_val = c.vencimento_certificado or ""
            
        clientes.append({
            "id": c.id, 
            "nome": c.nome or c.empresa, 
            "empresa": c.empresa or c.nome,
            "cnpj": c.cnpj,
            "contato": c.contato,
            "telefone": c.telefone,
            "sistema": c.sistema,
            "modulos": c.modulos,
            "status_cliente": st_fmt,
            "status_fmt": st_fmt,
            "ativo": is_ativo,
            "vencimento_certificado": venc_val,
            "vencimento": venc_val,
            "data_vencimento": venc_val,
            "vencimento_fmt": venc_val or "-",
            "dias": dias_venc,
            "status_cor": status_cor
        })

    # Define o mês atual se não vier preenchido
    mes_atual = mes if mes else datetime.now().strftime("%Y-%m")

    lancamentos = []
    for l in lancamentos_db:
        t_raw = str(l.tipo or "RECEITA").upper().strip()
        if any(w in t_raw for w in ['DESPESA', 'PAGAR', 'SAIDA', 'SAÍDA', 'CUSTO', '2']):
            tipo_fmt = "DESPESA"
        else:
            tipo_fmt = "RECEITA"
            
        st_pag = str(l.status_pagamento or "A VENCER").upper().strip()

        # Filtro padrão por mês na aba de financeiro convencional
        if l.data_vencimento and l.data_vencimento.startswith(mes_atual):
            lancamentos.append({
                "id": l.id, 
                "descricao": l.descricao, 
                "valor": l.valor, 
                "tipo": tipo_fmt,
                "tipo_fmt": tipo_fmt,
                "cliente_nome": l.cliente_nome,
                "nome_exibicao": l.cliente_nome or l.descricao,
                "data_vencimento": l.data_vencimento,
                "status_pagamento": st_pag,
                "status_fmt": st_pag
            })
    
    # Processamento para a aba de RELATÓRIO FINANCEIRO (com filtros customizados de data e cliente)
    relatorio_lancamentos = []
    for l in lancamentos_db:
        t_raw = str(l.tipo or "RECEITA").upper().strip()
        tipo_fmt = "DESPESA" if any(w in t_raw for w in ['DESPESA', 'PAGAR', 'SAIDA', 'SAÍDA', 'CUSTO', '2']) else "RECEITA"
        st_pag = str(l.status_pagamento or "A VENCER").upper().strip()
        
        # Valida filtros de data e cliente para o relatório
        incluir = True
        dt_venc = l.data_vencimento or ""
        
        if data_inicio and dt_venc < data_inicio:
            incluir = False
        if data_fim and dt_venc > data_fim:
            incluir = False
        if filtro_cliente and filtro_cliente.strip():
            c_nome = str(l.cliente_nome or "").lower()
            if filtro_cliente.lower() not in c_nome:
                incluir = False
                
        if incluir:
            relatorio_lancamentos.append({
                "id": l.id, 
                "descricao": l.descricao, 
                "valor": l.valor, 
                "tipo": tipo_fmt,
                "tipo_fmt": tipo_fmt,
                "cliente_nome": l.cliente_nome,
                "nome_exibicao": l.cliente_nome or l.descricao,
                "data_vencimento": l.data_vencimento,
                "status_pagamento": st_pag,
                "status_fmt": st_pag
            })

    todas_cobrancas = [{
        "id": l.id, 
        "descricao": l.descricao, 
        "valor": l.valor, 
        "tipo": "DESPESA" if any(w in str(l.tipo or "").upper() for w in ['DESPESA', 'PAGAR', 'SAIDA', 'CUSTO', '2']) else "RECEITA",
        "tipo_fmt": "DESPESA" if any(w in str(l.tipo or "").upper() for w in ['DESPESA', 'PAGAR', 'SAIDA', 'CUSTO', '2']) else "RECEITA",
        "cliente_nome": l.cliente_nome,
        "nome_exibicao": l.cliente_nome or l.descricao,
        "data_vencimento": l.data_vencimento,
        "status_pagamento": str(l.status_pagamento or "A VENCER").upper().strip(),
        "status_fmt": str(l.status_pagamento or "A VENCER").upper().strip()
    } for l in lancamentos_db]
    
    usuarios = [{
        "id": u.id,
        "nome": u.nome,
        "email": u.email,
        "username": u.email.split("@")[0] if u.email else "user",
        "cargo": u.cargo or "Usuário"
    } for u in usuarios_db]
    
    total_receita = sum(l["valor"] for l in lancamentos if l["tipo_fmt"] == "RECEITA")
    total_custo = sum(l["valor"] for l in lancamentos if l["tipo_fmt"] == "DESPESA")
    lucro_livre = total_receita - total_custo
    
    context = {
        "request": request,
        "tab": tab,
        "clientes": clientes,
        "lista_clientes": clientes,
        "lancamentos": lancamentos,
        "cobrancas": lancamentos,
        "relatorio_lancamentos": relatorio_lancamentos,
        "todas_cobrancas": todas_cobrancas,
        "certificados": clientes,
        "usuarios": usuarios,
        "usuarios_lista": usuarios,
        "usuario": usuario_atual,
        "total_receita": total_receita,
        "total_custo": total_custo,
        "lucro_livre": lucro_livre,
        "mes_atual": mes_atual,
        "data_inicio": data_inicio or "",
        "data_fim": data_fim or "",
        "filtro_cliente": filtro_cliente or ""
    }
    return templates.TemplateResponse(request=request, name="dashboard.html", context=context)

# --- ROTA PARA ATUALIZAR CERTIFICADO ---
@app.post("/cliente/atualizar-cert")
async def atualizar_certificado(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    tab = form_data.get("tab", "certificados")
    
    cliente_id = (
        form_data.get("id") or 
        form_data.get("cliente_id") or 
        form_data.get("cert_id") or 
        form_data.get("cliente")
    )
    
    vencimento_certificado = (
        form_data.get("vencimento_cert") or 
        form_data.get("vencimento_certificado") or 
        form_data.get("vencimento") or 
        form_data.get("certificado") or 
        form_data.get("data_vencimento") or
        form_data.get("data")
    )
    
    if cliente_id and str(cliente_id).strip().isdigit():
        cliente = db.query(Cliente).filter(Cliente.id == int(cliente_id)).first()
        if cliente and vencimento_certificado:
            cliente.vencimento_certificado = str(vencimento_certificado).strip()
            db.commit()
            
    return RedirectResponse(url=f"/dashboard?tab={tab}", status_code=status.HTTP_302_FOUND)

# --- ROTA DE CLIENTES E EDIÇÃO GERAL ---
@app.post("/cliente/editar")
@app.post("/cliente/editar/{cliente_id}")
@app.post("/cliente/salvar")
@app.post("/cliente/novo")
@app.post("/editar")
@app.post("/salvar")
async def salvar_cliente(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    tab = form_data.get("tab", "clientes")
    
    cliente_id = (
        form_data.get("id") or 
        form_data.get("cliente_id") or 
        form_data.get("cert_id") or 
        form_data.get("cliente")
    )
    
    status_digitado = (
        form_data.get("status_cliente") or 
        form_data.get("status") or 
        form_data.get("ativo") or 
        "ATIVO"
    )
    st_limpo = str(status_digitado).upper().strip()
    status_final = "INATIVO" if any(p in st_limpo for p in ["INATIVO", "0", "FALSE", "NAO", "NÃO", "OFF"]) else "ATIVO"

    vencimento_certificado = (
        form_data.get("vencimento_cert") or 
        form_data.get("vencimento_certificado") or 
        form_data.get("vencimento") or 
        form_data.get("certificado") or 
        form_data.get("data_vencimento") or
        form_data.get("data") or None
    )
    
    if cliente_id and str(cliente_id).strip().isdigit():
        cliente = db.query(Cliente).filter(Cliente.id == int(cliente_id)).first()
        if cliente:
            cliente.status_cliente = status_final
            
            if vencimento_certificado is not None and str(vencimento_certificado).strip() != "":
                cliente.vencimento_certificado = str(vencimento_certificado).strip()
            
            nome = form_data.get("nome") or form_data.get("empresa")
            if nome:
                cliente.nome = str(nome)
            empresa = form_data.get("empresa")
            if empresa:
                cliente.empresa = str(empresa)
            cnpj = form_data.get("cnpj")
            if cnpj is not None:
                cliente.cnpj = str(cnpj)
            contato = form_data.get("contato")
            if contato is not None:
                cliente.contato = str(contato)
            telefone = form_data.get("telefone") or form_data.get("phone")
            if telefone is not None:
                cliente.telefone = str(telefone)
            sistema = form_data.get("sistema")
            if sistema is not None:
                cliente.sistema = str(sistema)
            modulos = form_data.get("modulos") or form_data.get("modulo")
            if modulos is not None:
                cliente.modulos = str(modulos)
                
            db.commit()
    else:
        nome = form_data.get("nome") or form_data.get("empresa") or "Cliente"
        empresa = form_data.get("empresa") or nome
        cnpj = form_data.get("cnpj") or ""
        contato = form_data.get("contato") or ""
        telefone = form_data.get("telefone") or ""
        sistema = form_data.get("sistema") or ""
        modulos = form_data.get("modulos") or ""
        venc = vencimento_certificado or ""
        
        novo = Cliente(
            nome=str(nome), empresa=str(empresa), cnpj=str(cnpj),
            contato=str(contato), telefone=str(telefone), sistema=str(sistema),
            status_cliente=status_final, modulos=str(modulos),
            vencimento_certificado=str(venc)
        )
        db.add(novo)
        db.commit()
        
    return RedirectResponse(url=f"/dashboard?tab={tab}", status_code=status.HTTP_302_FOUND)

# --- ROTA FINANCEIRA ---
@app.post("/financeiro/editar")
@app.post("/financeiro/editar/{lancamento_id}")
@app.post("/financeiro/novo")
@app.post("/financeiro/salvar")
@app.post("/lancamento/novo")
@app.post("/lancamento/editar")
async def salvar_lancamento(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    tab = form_data.get("tab", "financeiro")
    mes = form_data.get("mes")
    
    descricao = form_data.get("descricao") or form_data.get("desc") or "Lançamento"
    valor_str = form_data.get("valor") or "0.0"
    try:
        valor = float(str(valor_str).replace("R$", "").replace(".", "").replace(",", ".").strip())
    except:
        valor = 0.0
        
    tipo_raw = str(form_data.get("tipo") or form_data.get("type") or "RECEITA").upper()
    if any(k in tipo_raw for k in ['DESPESA', 'PAGAR', 'SAIDA', 'SAÍDA', 'CUSTO', '2']):
        tipo = "DESPESA"
    else:
        tipo = "RECEITA"
        
    cliente_nome = form_data.get("cliente_nome") or form_data.get("cliente") or ""
    data_vencimento = form_data.get("data_vencimento") or form_data.get("vencimento") or ""
    status_pagamento = form_data.get("status_pagamento") or form_data.get("status") or "A VENCER"
    
    if data_vencimento and len(data_vencimento) >= 7 and not mes:
        mes = data_vencimento[:7]

    lancamento_id = form_data.get("id") or form_data.get("lancamento_id")
    
    if lancamento_id and str(lancamento_id).strip().isdigit():
        lanc = db.query(Lancamento).filter(Lancamento.id == int(lancamento_id)).first()
        if lanc:
            lanc.descricao = str(descricao)
            lanc.valor = valor
            lanc.tipo = str(tipo)
            lanc.cliente_nome = str(cliente_nome)
            lanc.data_vencimento = str(data_vencimento)
            lanc.status_pagamento = str(status_pagamento)
            db.commit()
    else:
        novo = Lancamento(
            descricao=str(descricao), valor=valor, tipo=str(tipo),
            cliente_nome=str(cliente_nome), data_vencimento=str(data_vencimento), 
            status_pagamento=str(status_pagamento)
        )
        db.add(novo)
        db.commit()
    
    url_redirect = f"/dashboard?tab={tab}"
    if mes:
        url_redirect += f"&mes={mes}"
    return RedirectResponse(url=url_redirect, status_code=status.HTTP_302_FOUND)

# --- ROTA PARA MARCAR FINANCEIRO COMO PAGO ---
@app.get("/financeiro/pagar/{item_id}")
async def pagar_lancamento(item_id: int, request: Request, db: Session = Depends(get_db)):
    tab = request.query_params.get("tab", "financeiro")
    mes = request.query_params.get("mes")
    
    item = db.query(Lancamento).filter(Lancamento.id == item_id).first()
    if item:
        item.status_pagamento = "PAGO"
        db.commit()
        
    url_redirect = f"/dashboard?tab={tab}"
    if mes:
        url_redirect += f"&mes={mes}"
    return RedirectResponse(url=url_redirect, status_code=status.HTTP_302_FOUND)

# --- USUÁRIOS / GERENCIAR CONTAS (INCLUINDO EDIÇÃO E EXCLUSÃO) ---
@app.post("/usuario/novo")
@app.post("/usuario/salvar")
@app.post("/usuarios/novo")
@app.post("/conta/novo")
@app.post("/perfil/editar")
@app.post("/usuario/editar")
async def salvar_ou_criar_usuario(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    tab = form_data.get("tab", "perfil")
    
    usuario_id = form_data.get("id") or form_data.get("usuario_id")
    nome = form_data.get("nome") or form_data.get("name") or "Usuário"
    email = form_data.get("email") or form_data.get("mail") or ""
    senha = form_data.get("senha") or form_data.get("password") or ""
    cargo = form_data.get("cargo") or form_data.get("role") or "Usuário"
    
    if usuario_id and str(usuario_id).strip().isdigit():
        u = db.query(Usuario).filter(Usuario.id == int(usuario_id)).first()
        if u:
            u.nome = str(nome)
            if email:
                u.email = str(email)
            if senha:
                u.senha = str(senha)
            if cargo:
                u.cargo = str(cargo)
            db.commit()
    else:
        # Se tentou editar o primeiro usuário logado sem mandar ID, atualiza o primeiro do banco
        primeiro_u = db.query(Usuario).first()
        if primeiro_u and tab == "perfil":
            primeiro_u.nome = str(nome)
            if email:
                primeiro_u.email = str(email)
            if senha:
                primeiro_u.senha = str(senha)
            if cargo:
                primeiro_u.cargo = str(cargo)
            db.commit()
        else:
            novo_u = Usuario(nome=str(nome), email=str(email), senha=str(senha), cargo=str(cargo))
            db.add(novo_u)
            db.commit()
            
    return RedirectResponse(url=f"/dashboard?tab={tab}", status_code=status.HTTP_302_FOUND)

@app.get("/usuario/deletar/{item_id}")
@app.get("/conta/deletar/{item_id}")
async def deletar_usuario(item_id: int, request: Request, db: Session = Depends(get_db)):
    tab = request.query_params.get("tab", "perfil")
    item = db.query(Usuario).filter(Usuario.id == item_id).first()
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(url=f"/dashboard?tab={tab}", status_code=status.HTTP_302_FOUND)

# --- EXCLUSÕES DE CLIENTES ---
@app.get("/cliente/deletar/{item_id}")
async def deletar_cliente(item_id: int, request: Request, db: Session = Depends(get_db)):
    tab = request.query_params.get("tab", "clientes")
    item = db.query(Cliente).filter(Cliente.id == item_id).first()
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(url=f"/dashboard?tab={tab}", status_code=status.HTTP_302_FOUND)

# --- EXCLUSÕES DE LANÇAMENTOS ---
@app.get("/financeiro/deletar/{item_id}")
@app.get("/deletar/{item_id}")
async def deletar_lancamento(item_id: int, request: Request, db: Session = Depends(get_db)):
    tab = request.query_params.get("tab", "financeiro")
    mes = request.query_params.get("mes")
    
    item = db.query(Lancamento).filter(Lancamento.id == item_id).first()
    if item:
        db.delete(item)
        db.commit()
        
    url_redirect = f"/dashboard?tab={tab}"
    if mes:
        url_redirect += f"&mes={mes}"
    return RedirectResponse(url=url_redirect, status_code=status.HTTP_302_FOUND)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

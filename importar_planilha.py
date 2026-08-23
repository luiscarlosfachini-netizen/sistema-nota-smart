import os
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ⚠️ Insira aqui a sua Connection String do Supabase (PostgreSQL)
# Exemplo: "postgresql://postgres:sua_senha@db.xxxxxx.supabase.co:5432/postgres"
SUPABASE_URL = os.environ.get(
    "DATABASE_URL", "COLOQUE_SUA_URL_DO_SUPABASE_AQUI"
)

engine = create_engine(SUPABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Definição da Tabela de Clientes no Banco
class ClienteModel(Base):
    __tablename__ = "clientes"
    id = Column(Integer, primary_key=True, index=True)
    empresa = Column(String, nullable=False)
    cnpj = Column(String)
    contato = Column(String)
    telefone = Column(String)
    sistema = Column(String)
    status_fmt = Column(String)
    modulos = Column(String)
    vencimento_cert = Column(String)


def importar():
    ARQUIVO_EXCEL = "Clientes NOTA SMART!.xlsx"

    if not os.path.exists(ARQUIVO_EXCEL):
        print(f"❌ Arquivo '{ARQUIVO_EXCEL}' não encontrado na pasta do projeto.")
        return

    print("🔄 Lendo a planilha...")
    df = pd.read_excel(ARQUIVO_EXCEL, engine="openpyxl")

    db = SessionLocal()
    try:
        contador = 0
        for _, row in df.iterrows():
            # Mapeie os nomes das colunas conforme estão na sua planilha
            nome_empresa = str(
                row.get("Empresa", row.get("Cliente", "Desconhecida"))
            )

            # Verifica se o cliente já existe no Supabase para evitar duplicatas
            existe = (
                db.query(ClienteModel)
                .filter(ClienteModel.empresa == nome_empresa)
                .first()
            )
            if existe:
                print(f"⚠️ Cliente já cadastrado: {nome_empresa} (Pulando)")
                continue

            novo_cliente = ClienteModel(
                empresa=nome_empresa,
                cnpj=str(row.get("CNPJ", "")),
                contato=str(row.get("Contato", "")),
                telefone=str(row.get("Telefone", "")),
                sistema=str(row.get("Retaguarda/Pista", row.get("Sistema", ""))),
                status_fmt=str(row.get("Status", "ATIVO")),
                modulos=str(row.get("Módulos", "")),
                vencimento_cert="2026-12-15",  # Ajuste se houver coluna de certificado na planilha
            )
            db.add(novo_cliente)
            contador += 1

        db.commit()
        print(
            f"✅ Sucesso! {contador} novos clientes foram importados para o Supabase."
        )
    except Exception as e:
        db.rollback()
        print(f"❌ Erro ao importar para o Supabase: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    importar()

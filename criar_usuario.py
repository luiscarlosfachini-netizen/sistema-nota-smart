from app import app, db, UsuarioModel

with app.app_context():
    # Limpa qualquer usuário existente para evitar conflitos
    UsuarioModel.query.delete()
    
    # Cria o usuário admin limpo
    admin = UsuarioModel(
        nome="Administrador",
        email="luisfachini",
        senha="123456",
        cargo="Admin"
    )
    db.session.add(admin)
    db.session.commit()
    print(">>> Usuário 'luisfachini' criado com sucesso!")

import main

with main.app.app_context():
    main.UsuarioModel.query.delete()
    admin = main.UsuarioModel(
        nome="Administrador",
        email="luisfachini",
        senha="123456",
        cargo="Admin"
    )
    main.db.session.add(admin)
    main.db.session.commit()
    print(">>> Sucesso! Usuário recriado.")

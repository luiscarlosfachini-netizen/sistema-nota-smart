from app import app, db, UsuarioModel
with app.app_context():
    UsuarioModel.query.delete()
    admin = UsuarioModel(nome='Administrador', email='luisfachini', senha='123456', cargo='Admin')
    db.session.add(admin)
    db.session.commit()
    print('>>> Usuário recriado com sucesso!')

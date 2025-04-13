import os

class Config:
    # Configuração do banco de dados SQLite
    SQLALCHEMY_DATABASE_URI = 'sqlite:///riscos_psicossociais.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'rp-api'

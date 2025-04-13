from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Inicializa o SQLAlchemy
db = SQLAlchemy()

# Modelo de dados para macrotemas (categorias A, B, C, D, E do PRD-PRQ)
class MacroTema(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(5), nullable=False)  # Ex: "A", "B", "C"
    titulo = db.Column(db.String(100), nullable=False)
    
    # Relação: um macrotema tem muitos temas
    temas = db.relationship('Tema', backref='macro_tema', lazy=True)

# Modelo de dados para os 20 temas do PRD-PRQ
class Tema(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False)  # Ex: 1, 2, 3...
    descricao = db.Column(db.Text, nullable=False)
    macro_tema_id = db.Column(db.Integer, db.ForeignKey('macro_tema.id'), nullable=False)
    
    # Relações
    subtemas = db.relationship('Subtema', backref='tema', lazy=True)
    avaliacoes = db.relationship('RespostaPrimeiroNivel', backref='tema', lazy=True)
    recomendacoes = db.relationship('Recomendacao', backref='tema', lazy=True)

# Modelo para os subtemas (perguntas do segundo nível)
class Subtema(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    letra = db.Column(db.String(5), nullable=False)  # Ex: "a", "b", "c"
    descricao = db.Column(db.Text, nullable=False)
    tema_id = db.Column(db.Integer, db.ForeignKey('tema.id'), nullable=False)
    
    # Relações
    avaliacoes = db.relationship('RespostaSegundoNivel', backref='subtema', lazy=True)

# Modelo para cada avaliação completa feita por um trabalhador
class Avaliacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    empresa = db.Column(db.String(100), nullable=False)
    departamento = db.Column(db.String(100), nullable=False)
    funcao = db.Column(db.String(100), nullable=True)
    data_avaliacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relações com as respostas
    respostas_nivel1 = db.relationship('RespostaPrimeiroNivel', backref='avaliacao', lazy=True)
    respostas_nivel2 = db.relationship('RespostaSegundoNivel', backref='avaliacao', lazy=True)

# Modelo para respostas do primeiro nível (temas selecionados)
class RespostaPrimeiroNivel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    avaliacao_id = db.Column(db.Integer, db.ForeignKey('avaliacao.id'), nullable=False)
    tema_id = db.Column(db.Integer, db.ForeignKey('tema.id'), nullable=False)
    selecionado = db.Column(db.Boolean, default=False)

# Modelo para respostas do segundo nível (nível de desconforto)
class RespostaSegundoNivel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    avaliacao_id = db.Column(db.Integer, db.ForeignKey('avaliacao.id'), nullable=False)
    subtema_id = db.Column(db.Integer, db.ForeignKey('subtema.id'), nullable=False)
    # 0=Sem impacto, 1=Desconforto leve, 2=Desconforto moderado, 3=Dor leve, 4=Dor intensa
    nivel_desconforto = db.Column(db.Integer, nullable=False)  

# Modelo para recomendações baseadas no tema e nível de risco
class Recomendacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tema_id = db.Column(db.Integer, db.ForeignKey('tema.id'), nullable=False)
    faixa_nivel = db.Column(db.Integer, nullable=False)  # 0=Baixo risco, 1=Médio risco, 2=Alto risco
    descricao = db.Column(db.Text, nullable=False)

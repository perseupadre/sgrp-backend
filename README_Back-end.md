# API de Riscos Psicossociais (Back-end)

## Descrição

API desenvolvida em Python/Flask para avaliação de riscos psicossociais em ambientes de trabalho. O sistema implementa um questionário baseado no PRD-PRQ (Raising Psychosocial Risks - Quick Questionnaire), oferecendo uma estrutura hierárquica de macrotemas, temas e subtemas para identificação detalhada de áreas problemáticas.

A API gerencia a coleta de respostas em dois níveis, processa os dados e gera relatórios estatísticos com recomendações específicas baseadas no nível de risco identificado.

## Principais Funcionalidades

- Estrutura hierárquica de questionário (macrotemas, temas e subtemas)
- Coleta de avaliações em dois níveis (seleção de temas relevantes e nível de desconforto)
- Geração de relatórios estatísticos com cálculo de níveis de risco
- Recomendações personalizadas baseadas no nível de risco identificado
- Documentação completa da API via Swagger

## Requisitos

- Python 3.8 ou superior
- pip (gerenciador de pacotes do Python)
- SQLite

## Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/perseupadre/rp-backend.git
cd rp-backend
```

### 2. Crie e ative um ambiente virtual

No Windows:

`python -m venv venv venv\Scripts\activate`

No macOS/Linux:

`python3 -m venv venv source venv/bin/activate`

### 3. Instale as dependências

`pip install -r requirements.txt`

### 4. Configure o ambiente

Crie um arquivo `.env` na raiz do projeto (opcional) ou use as configurações padrão:

`DATABASE_URL = sqlite:///app.db `

`SECRET_KEY = rp-api`

## Execução

### 1. Inicialize o banco de dados

O banco de dados será inicializado automaticamente na primeira execução, mas você também pode rodar:

`python -c "from app import app, inicializar_db; app.app_context().push(); inicializar_db()"`

### 2. Inicie o servidor

`python app.py`

O servidor está disponível em [http://localhost:5000]

### 3. Acesse a documentação da API

Acesse [http://localhost:5000/api/docs] para visualizar a documentação Swagger interativa da API.

## Endpoints Principais

* **GET /obter_questionario** - Retorna a estrutura completa do questionário
* **POST /cadastrar_avaliacao** - Cadastra uma nova avaliação com respostas de usuários
* **GET /gerar_relatorio** - Gera relatórios estatísticos com base nas avaliações cadastradas

## Estrutura do Projeto

* **app.py** - Arquivo principal com as rotas da API
* **models.py** - Definições dos modelos de dados (SQLAlchemy)
* **config.py** - Configurações da aplicação
* `static/swagger.json` - Documentação Swagger da API

## Tecnologias Utilizadas

* **Flask** - Framework web
* **SQLAlchemy**- ORM para gerenciamento de banco de dados
* **SQLite**- Banco de dados relacional
* **Flask-CORS** - Suporte a requisições cross-origin
* **Swagger** - Documentação da API

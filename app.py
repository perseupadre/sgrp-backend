# Importações essenciais para a API
from flask import Flask, request, jsonify
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
from config import Config
from models import db, MacroTema, Tema, Subtema, Avaliacao, RespostaPrimeiroNivel, RespostaSegundoNivel, Recomendacao
import json
import time
_ultima_submissao = {'timestamp': 0, 'chave': None}

# Inicialização da aplicação Flask e suas extensões
app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
CORS(app)

# Configuração da documentação da API usando Swagger
SWAGGER_URL = '/api/docs'
API_URL = '/static/swagger.json'
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "API de Riscos Psicossociais"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

# Rota para obter a estrutura do questionário
@app.route('/obter_questionario', methods=['GET'])
def obter_questionario():
    macrotemas = MacroTema.query.all()
    resultado = []
    
    for macrotema in macrotemas:
        temas_data = []
        for tema in macrotema.temas:
            subtemas_data = []
            for subtema in tema.subtemas:
                subtemas_data.append({
                    'id': subtema.id,
                    'letra': subtema.letra,
                    'descricao': subtema.descricao
                })
            
            temas_data.append({
                'id': tema.id,
                'numero': tema.numero,
                'descricao': tema.descricao,
                'subtemas': subtemas_data
            })
        
        resultado.append({
            'id': macrotema.id,
            'codigo': macrotema.codigo,
            'titulo': macrotema.titulo,
            'temas': temas_data
        })
    
    return jsonify({'questionario': resultado})

# Rota para cadastrar uma nova avaliação
@app.route('/cadastrar_avaliacao', methods=['POST'])
def cadastrar_avaliacao():
    global _ultima_submissao
    dados = request.json
    chave_atual = f"{dados['empresa']}_{dados['departamento']}"
    
    # Verificar se é duplicação nos últimos 3 segundos
    if time.time() - _ultima_submissao['timestamp'] < 3 and _ultima_submissao['chave'] == chave_atual:
        return jsonify({'mensagem': 'Avaliação já registrada recentemente.'}), 200
    
    # Registrar esta submissão
    _ultima_submissao = {'timestamp': time.time(), 'chave': chave_atual}
    
    # Criar avaliação
    nova_avaliacao = Avaliacao(
        empresa=dados['empresa'],
        departamento=dados['departamento'],
        funcao=dados.get('funcao', '')
    )
    db.session.add(nova_avaliacao)
    db.session.flush()
    
    # Processar respostas do primeiro nível
    for resposta_nivel1 in dados['respostas_nivel1']:
        nova_resposta = RespostaPrimeiroNivel(
            avaliacao_id=nova_avaliacao.id,
            tema_id=resposta_nivel1['tema_id'],
            selecionado=resposta_nivel1['selecionado']
        )
        db.session.add(nova_resposta)
    
    # Processar respostas do segundo nível
    for resposta_nivel2 in dados['respostas_nivel2']:
        nova_resposta = RespostaSegundoNivel(
            avaliacao_id=nova_avaliacao.id,
            subtema_id=resposta_nivel2['subtema_id'],
            nivel_desconforto=resposta_nivel2['nivel_desconforto']
        )
        db.session.add(nova_resposta)
    
    db.session.commit()
    
    return jsonify({'mensagem': 'Avaliação cadastrada com sucesso', 'id': nova_avaliacao.id}), 201

# Rota para gerar relatório
@app.route('/gerar_relatorio', methods=['GET'])
def gerar_relatorio():
    empresa = request.args.get('empresa')
    departamento = request.args.get('departamento')
    
    # Consulta base para avaliacoes
    query = Avaliacao.query
    if empresa:
        query = query.filter_by(empresa=empresa)
    if departamento:
        query = query.filter_by(departamento=departamento)
    
    avaliacoes = query.all()
    total_avaliacoes = len(avaliacoes)
    
    if total_avaliacoes == 0:
        return jsonify({
            'total_avaliacoes': 0,
            'mensagem': 'Nenhuma avaliação encontrada com os filtros informados.'
        })
    
    # Estatísticas por tema
    estatisticas_temas = {}
    for avaliacao in avaliacoes:
        for resposta in avaliacao.respostas_nivel1:
            if resposta.selecionado:
                tema_id = resposta.tema_id
                if tema_id not in estatisticas_temas:
                    tema = Tema.query.get(tema_id)
                    estatisticas_temas[tema_id] = {
                        'tema': tema.numero,
                        'descricao': tema.descricao,
                        'contagem': 0,
                        'percentual': 0,
                        'nivel_medio': 0,
                        'subtemas': {}
                    }
                estatisticas_temas[tema_id]['contagem'] += 1
    
    # Calcular percentuais
    for tema_id in estatisticas_temas:
        estatisticas_temas[tema_id]['percentual'] = round((estatisticas_temas[tema_id]['contagem'] / total_avaliacoes) * 100, 1)
    
    # Estatísticas por subtema
    for avaliacao in avaliacoes:
        for resposta in avaliacao.respostas_nivel2:
            subtema = Subtema.query.get(resposta.subtema_id)
            tema_id = subtema.tema_id
            
            if tema_id in estatisticas_temas:
                if subtema.id not in estatisticas_temas[tema_id]['subtemas']:
                    estatisticas_temas[tema_id]['subtemas'][subtema.id] = {
                        'letra': subtema.letra,
                        'descricao': subtema.descricao,
                        'total_pontos': 0,
                        'contagem': 0,
                        'nivel_medio': 0
                    }
                
                estatisticas_temas[tema_id]['subtemas'][subtema.id]['total_pontos'] += resposta.nivel_desconforto
                estatisticas_temas[tema_id]['subtemas'][subtema.id]['contagem'] += 1
    
    # Calcular médias dos subtemas
    for tema_id in estatisticas_temas:
        total_pontos_tema = 0
        total_respostas_tema = 0
        
        for subtema_id in estatisticas_temas[tema_id]['subtemas']:
            subtema_data = estatisticas_temas[tema_id]['subtemas'][subtema_id]
            if subtema_data['contagem'] > 0:
                subtema_data['nivel_medio'] = round(subtema_data['total_pontos'] / subtema_data['contagem'], 2)
                total_pontos_tema += subtema_data['total_pontos']
                total_respostas_tema += subtema_data['contagem']
        
        # Calcular média do tema
        if total_respostas_tema > 0:
            estatisticas_temas[tema_id]['nivel_medio'] = round(total_pontos_tema / total_respostas_tema, 2)
    
    # Preparar dados para retorno
    temas_resultado = []
    for tema_id, dados in estatisticas_temas.items():
        # Busca o tema para obter seu macrotema (MOVIDO PARA AQUI)
        tema_obj = Tema.query.get(tema_id)
        macrotema_codigo = tema_obj.macro_tema.codigo if tema_obj and tema_obj.macro_tema else "?"
        dados['macrotema'] = macrotema_codigo
        
        subtemas_lista = []
        for subtema_id, subtema_dados in dados['subtemas'].items():
            subtemas_lista.append({
                'letra': subtema_dados['letra'],
                'descricao': subtema_dados['descricao'],
                'nivel_medio': subtema_dados['nivel_medio']
            })
        
        # Obter recomendações com base no nível médio
        nivel_medio = dados['nivel_medio']
        faixa_nivel = 0  # Ausência de Risco (padrão)

        # Classificação simplificada
        if nivel_medio >= 0.5 and nivel_medio < 1.5:
            faixa_nivel = 1  # Risco Baixo
        elif nivel_medio >= 1.5 and nivel_medio < 2.5:
            faixa_nivel = 2  # Risco Moderado
        elif nivel_medio >= 2.5 and nivel_medio < 3.5:
            faixa_nivel = 3  # Risco Alto
        elif nivel_medio >= 3.5:
            faixa_nivel = 4  # Risco Crítico
        
        # Adicionar print para debug
        print(f"Tema {dados['tema']}: nivel_medio={nivel_medio}, faixa_nivel={faixa_nivel}")
        
        recomendacoes = Recomendacao.query.filter_by(tema_id=tema_id, faixa_nivel=faixa_nivel).all()
        recomendacoes_lista = [rec.descricao for rec in recomendacoes]
        
        # Verificar se recomendações foram encontradas
        print(f"Tema {dados['tema']}: {len(recomendacoes_lista)} recomendações encontradas")

        # Adiciona dados consolidados do tema ao resultado final
        temas_resultado.append({
            'tema': dados['tema'],
            'descricao': dados['descricao'],
            'contagem': dados['contagem'],
            'macrotema': dados['macrotema'],
            'percentual': dados['percentual'],
            'nivel_medio': dados['nivel_medio'],
            'subtemas': subtemas_lista,
            'recomendacoes': recomendacoes_lista
        })
        
    # Ordenar por percentual (decrescente)
    temas_resultado.sort(key=lambda x: x['percentual'], reverse=True)
        
    return jsonify({
        'total_avaliacoes': total_avaliacoes,
        'empresa': empresa if empresa else 'Todas',
         'departamento': departamento if departamento else 'Todos',
           'temas': temas_resultado
    })

@app.route('/static/swagger.json')
def swagger_spec():
    with open('static/swagger.json', 'r', encoding='utf-8') as f:
        content = f.read()
    # Não use jsonify, retorne a resposta diretamente
    response = app.response_class(
        response=content,
        status=200,
        mimetype='application/json'
    )
    return response

# Aqui está a função modificada (sem o decorador @app.before_first_request)
def inicializar_db():
    with app.app_context():
        db.create_all()
        
        # Verifica se já existem dados
        if MacroTema.query.count() == 0:
            # Cria os macro temas
            macro_a = MacroTema(codigo="A", titulo="Sobre diferentes cargas de trabalho")
            macro_b = MacroTema(codigo="B", titulo="Sobre aspectos sociais no trabalho")
            macro_c = MacroTema(codigo="C", titulo="Sobre suporte organizacional")
            macro_d = MacroTema(codigo="D", titulo="Sobre saúde no trabalho")
            macro_e = MacroTema(codigo="E", titulo="Sobre outros aspectos")
            
            db.session.add_all([macro_a, macro_b, macro_c, macro_d, macro_e])
            db.session.flush()
            
            temas = [
                # Macro tema A - Sobre diferentes cargas de trabalho
                {"macro": macro_a, "numero": 1, "descricao": "Meu trabalho é caracterizado por alta intensidade e um ritmo acelerado de trabalho.", 
                "subtemas": [
                    {"letra": "a", "descricao": "Preciso trabalhar muito rápido ou com muito esforço ao longo do dia"},
                    {"letra": "b", "descricao": "Frequentemente não tenho tempo para concluir todas as minhas tarefas ou preciso fazer horas extras"},
                    {"letra": "c", "descricao": "Frequentemente sou pressionado(a) a fazer horas extras"},
                    {"letra": "d", "descricao": "Tenho muitas demandas no trabalho com metas ou prazos difíceis de cumprir"}
                ]},
                {"macro": macro_a, "numero": 2, "descricao": "Meu trabalho é caracterizado por variações extremamente baixas (monotonia) ou excessivas.", 
                "subtemas": [
                    {"letra": "a", "descricao": "Meu trabalho não é variado e faço a mesma coisa repetidamente"},
                    {"letra": "b", "descricao": "O trabalho não exige que eu utilize diferentes habilidades"},
                    {"letra": "c", "descricao": "Tenho que repetir o mesmo procedimento em intervalos curtos"},
                    {"letra": "d", "descricao": "Minha carga de trabalho é distribuída de forma desigual ou aumenta repentinamente"}
                ]},
                {"macro": macro_a, "numero": 3, "descricao": "Meu trabalho é difícil (em termos de tarefas, decisões, objetivos, habilidades e conhecimentos exigidos, etc.).", 
                "subtemas": [
                    {"letra": "a", "descricao": "Meu trabalho exige um alto nível de conhecimento e habilidades técnicas"},
                    {"letra": "b", "descricao": "Meu trabalho exige que eu tome decisões difíceis, rápidas ou complexas"},
                    {"letra": "c", "descricao": "Preciso me esforçar muito para alcançar o nível de desempenho exigido"},
                ]},
                {"macro": macro_a, "numero": 4, "descricao": "Preciso pensar e raciocinar muito no meu trabalho.", 
                "subtemas": [
                    {"letra": "a", "descricao": "Meu trabalho exige que eu memorize ou preste atenção a muitas informações ao mesmo tempo"},
                    {"letra": "b", "descricao": "Meu trabalho exige muita concentração"},
                    {"letra": "c", "descricao": "Preciso pensar constantemente sobre o trabalho durante o expediente"},
                ]},
                {"macro": macro_a, "numero": 5, "descricao": "Meu trabalho causa alguma perturbação emocional em algumas situações.", 
                "subtemas": [
                    {"letra": "a", "descricao": "Tenho que lidar com problemas pessoais de outras pessoas no trabalho"},
                    {"letra": "b", "descricao": "Meu trabalho é emocionalmente exigente ou perturbador"},
                    {"letra": "c", "descricao": "Preciso esconder meus sentimentos ou não posso expressar minha opinião"},
                    {"letra": "d", "descricao": "Sou obrigado(a) a ser gentil com todos, independente de como se comportem comigo"},
                    {"letra": "e", "descricao": "Tenho responsabilidade sobre o futuro, segurança, moral, bem-estar ou vida de outras pessoas"}
                ]},

                # Macro tema B - Sobre aspectos sociais no trabalho
                {"macro": macro_b, "numero": 6, "descricao": "No meu trabalho, o relacionamento com meus colegas é desafiador.", 
                "subtemas": [
                    {"letra": "a", "descricao": "Trabalhar com certos colegas é difícil ou frustrante e drena minha energia"},
                    {"letra": "b", "descricao": "Há pouca cooperação entre os colegas"},
                    {"letra": "c", "descricao": "Existe atrito, raiva ou falta de respeito entre colegas"},
                    {"letra": "d", "descricao": "Os colegas não estão dispostos a ouvir meus problemas ou ideias"},
                    {"letra": "e", "descricao": "Não tenho oportunidade de desenvolver relações sociais com colegas"}
                ]},
                {"macro": macro_b, "numero": 7, "descricao": "No meu trabalho, o relacionamento com meus superiores (em qualquer nível) é desafiador.", 
                "subtemas": [
                    {"letra": "a", "descricao": "Trabalhar com meus superiores é difícil ou frustrante e drena minha energia"},
                    {"letra": "b", "descricao": "Meus superiores não sabem administrar bem a equipe"},
                    {"letra": "c", "descricao": "Meus superiores dão pouca importância à satisfação, segurança e bem-estar dos trabalhadores"},
                    {"letra": "d", "descricao": "Não posso contar com a ajuda dos superiores ou liderança da empresa em caso de necessidade"},
                    {"letra": "e", "descricao": "Os funcionários não conseguem expressar suas opiniões, sentimentos e ideias"},
                    {"letra": "f", "descricao": "Meus superiores não estão dispostos a ouvir meus problemas relacionados ao trabalho ou pessoais"}
                ]},
                {"macro": macro_b, "numero": 8, "descricao": "Meu trabalho impacta negativamente minha vida pessoal.", 
                "subtemas": [
                    {"letra": "a", "descricao": "Preciso alterar meus planos pessoais ou familiares por causa do trabalho"},
                    {"letra": "b", "descricao": "Pessoas próximas dizem que sacrifico demais pelo trabalho"},
                    {"letra": "c", "descricao": "É difícil tirar um tempo durante o trabalho para cuidar de assuntos pessoais ou familiares"},
                    {"letra": "d", "descricao": "As demandas do trabalho interferem na minha vida pessoal e familiar (ou vice-versa)"},
                    {"letra": "e", "descricao": "Não me sinto à vontade ou confiante para conversar sobre meus problemas de trabalho com meu cônjuge ou pessoa próxima"}
                ]},
                {"macro": macro_b, "numero": 9, "descricao": "No meu trabalho, há falta de confiança entre os trabalhadores e entre trabalhadores e superiores.", 
                "subtemas": [
                    {"letra": "a", "descricao": "Funcionários ou gestores retêm informações entre si"},
                    {"letra": "b", "descricao": "Em geral, os funcionários não confiam uns nos outros"},
                    {"letra": "c", "descricao": "A gestão não confia que os funcionários realizem bem seu trabalho"},
                    {"letra": "d", "descricao": "Os funcionários não confiam nas informações que vêm da gestão"},
                    {"letra": "e", "descricao": "A gestão retém informações importantes dos funcionários (ou vice-versa)"}
                ]},
               
                # Macro tema C - Sobre suporte organizacional
                {"macro": macro_c, "numero": 10, "descricao": "Não tenho clareza sobre o que preciso fazer e quais metas alcançar (ou não recebo feedback sobre meu desempenho).", 
                "subtemas": [
                    {"letra": "a", "descricao": "Meu trabalho não possui objetivos claros ou não sei o que se espera de mim"},
                    {"letra": "b", "descricao": "Demandas contraditórias são colocadas sobre mim no trabalho"},
                    {"letra": "c", "descricao": "Não recebo informações sobre meu desempenho dos gestores ou colegas"},
                    {"letra": "d", "descricao": "Os funcionários não são informados sobre os objetivos ou políticas atuais da empresa"}
                ]},
                {"macro": macro_c, "numero": 11, "descricao": "Meu desempenho no trabalho é negativamente impactado por aspectos fora do meu alcance.", 
                "subtemas": [
                    {"letra": "a", "descricao": "Minhas atividades de trabalho são muito afetadas pelo trabalho de outras pessoas"},
                    {"letra": "b", "descricao": "Sofro muitas interrupções e distrações durante o trabalho"},
                    {"letra": "c", "descricao": "Tenho dificuldade em realizar meu trabalho com qualidade por falta de apoio organizacional"},
                    {"letra": "d", "descricao": "Não recebo os recursos ou ajuda necessária para fazer meu trabalho bem"}
                ]},
                {"macro": macro_c, "numero": 12, "descricao": "No trabalho, percebo algumas situações que considero injustas.", 
                "subtemas": [
                    {"letra": "a", "descricao": "O trabalho não é distribuído de forma justa"},
                    {"letra": "b", "descricao": "As sugestões dos funcionários não são levadas a sério pela gestão"},
                    {"letra": "c", "descricao": "Os conflitos não são resolvidos de forma justa ou satisfatória"},
                    {"letra": "d", "descricao": "Não sou tratado(a) com respeito ou justiça no trabalho"}
                ]},
                {"macro": macro_c, "numero": 13, "descricao": "Meu trabalho não permite desenvolvimento profissional (carreira e treinamento).", 
                "subtemas": [
                    {"letra": "a", "descricao": "Não há boas perspectivas de promoção ou desenvolvimento no trabalho"},
                    {"letra": "b", "descricao": "Não tenho a possibilidade de desenvolver novos conhecimentos ou habilidades no trabalho"},
                    {"letra": "c", "descricao": "Não posso aplicar minhas habilidades ou conhecimentos no trabalho, ou trabalho abaixo da minha capacidade"},
                    {"letra": "d", "descricao": "Não me sinto certo(a) ou confiante sobre minha trajetória profissional"},
                    {"letra": "e", "descricao": "Meu trabalho não me estimula a encontrar soluções criativas ou pensar fora da caixa"}
                ]},
                {"macro": macro_c, "numero": 14, "descricao": "No meu trabalho, a participação e/ou autonomia dos trabalhadores não é incentivada.", 
                "subtemas": [
                    {"letra": "a", "descricao": "Meu trabalho não me dá chance de usar minha iniciativa pessoal ou julgamento próprio"},
                    {"letra": "b", "descricao": "Às vezes preciso fazer coisas que parecem desnecessárias ou que poderiam ser feitas de outra forma"},
                    {"letra": "c", "descricao": "Não tenho poder de decisão sobre meu trabalho (o que fazer, ritmo, com quem, quantidade de tarefas, etc.)"},
                    {"letra": "d", "descricao": "Não posso decidir quando tirar pausas ou férias, ou não posso interromper o trabalho para conversar com um colega"},
                    {"letra": "e", "descricao": "Meu trabalho é frequentemente controlado (supervisores, auditorias, inspeções, etc.)"},
                    {"letra": "f", "descricao": "Os trabalhadores não são incentivados a pensar em maneiras de melhorar o trabalho"}
                ]},

                # Macro tema D - Sobre saúde no trabalho
                {"macro": macro_d, "numero": 15, "descricao": "No meu trabalho, há situações de comportamento prejudicial (bullying, agressão, assédio, discriminação, etc.).", 
                "subtemas": [
                    {"letra": "a", "descricao": "Ameaças, agressões físicas ou violência"},
                    {"letra": "b", "descricao": "Discriminação por gênero, idade, religião, filiação política, nacionalidade, raça, orientação sexual, saúde, estado civil, etc."},
                    {"letra": "c", "descricao": "Abuso verbal, conflitos, insultos, provocações, assédio nas redes sociais relacionado ao trabalho"},
                    {"letra": "d", "descricao": "Assédio sexual ou atenção sexual indesejada"},
                    {"letra": "e", "descricao": "Palavras ou atitudes humilhantes, bullying, boatos prejudiciais, hostilidade"}
                ]},
                {"macro": macro_d, "numero": 16, "descricao": "Minha saúde mental é negativamente afetada pelo trabalho (estresse, exaustão, depressão, etc.).", 
                "subtemas": [
                    {"letra": "a", "descricao": "Frequentemente acho que não suporto mais meu trabalho"},
                    {"letra": "b", "descricao": "Tenho estado frequentemente física ou emocionalmente exausto(a)"},
                    {"letra": "c", "descricao": "Frequentemente sinto tristeza ou falta de interesse nas coisas do dia a dia"},
                    {"letra": "d", "descricao": "Frequentemente me sinto sem confiança ou com culpa/remorso"},
                    {"letra": "e", "descricao": "Tenho dificuldade em me concentrar ou pensar com clareza"},
                    {"letra": "f", "descricao": "Tenho dificuldade em tomar decisões ou em lembrar das coisas"},
                    {"letra": "g", "descricao": "Frequentemente fico irritado(a) ou tenso(a)"},
                    {"letra": "h", "descricao": "Frequentemente tenho dores de estômago, dor de cabeça, palpitações ou tensão muscular"}
                ]},
                
                # Macro tema D - Sobre saúde no trabalho
                {"macro": macro_d, "numero": 17, "descricao": "A qualidade do meu sono é negativamente impactada pelo trabalho.", 
                "subtemas": [
                    {"letra": "a", "descricao": "O trabalho não me deixa em paz, penso nele mesmo ao ir dormir"},
                    {"letra": "b", "descricao": "Se deixo de fazer algo no trabalho, tenho dificuldade para dormir"},
                    {"letra": "c", "descricao": "Assim que acordo, já começo a pensar nos problemas do trabalho"},
                    {"letra": "d", "descricao": "A rotina de trabalho afeta a qualidade do meu sono (trabalho noturno, turnos, etc.)"}
                ]},

                # Macro tema E - Sobre outros aspectos
                {"macro": macro_e, "numero": 18, "descricao": "Estou preocupado(a) com meu futuro profissional (desemprego, mudanças indesejadas, etc.).", 
                "subtemas": [
                    {"letra": "a", "descricao": "Tenho medo de ser demitido ou de ser substituído por tecnologia"},
                    {"letra": "b", "descricao": "Tenho medo de ser transferido de função sem aviso prévio ou contra minha vontade"},
                    {"letra": "c", "descricao": "Tenho receio de mudanças no cronograma/horários contra minha vontade"},
                    {"letra": "d", "descricao": "Tenho medo de redução salarial ou introdução de salário variável"},
                    {"letra": "e", "descricao": "Me preocupo com a dificuldade de encontrar outro bom emprego se ficar desempregado"}
                ]},
                {"macro": macro_e, "numero": 19, "descricao": "Considero meu trabalho sem importância ou não devidamente reconhecido.", 
                "subtemas": [
                    {"letra": "a", "descricao": "Sinto que meu trabalho é sem sentido ou pouco importante"},
                    {"letra": "b", "descricao": "Meu trabalho não é reconhecido pela gestão, mesmo quando faço um bom trabalho"},
                    {"letra": "c", "descricao": "Sinto que meu local de trabalho tem pouca importância para mim / Penso frequentemente em procurar outro emprego"},
                    {"letra": "d", "descricao": "O resultado do meu trabalho não afeta significativamente a vida de outras pessoas ou o mundo"},
                    {"letra": "e", "descricao": "Na organização, não sou recompensado(a) (dinheiro, incentivo, etc.) por um bom desempenho"}
                ]},
                {"macro": macro_e, "numero": 20, "descricao": "Estou insatisfeito(a) com meu trabalho em geral.", 
                "subtemas": [
                    {"letra": "a", "descricao": "Não estou satisfeito com a qualidade do trabalho realizado na empresa"},
                    {"letra": "b", "descricao": "Considerando meus esforços e conquistas, não estou satisfeito com minhas perspectivas/salário"},
                    {"letra": "c", "descricao": "Não me sinto inspirado nem satisfeito com meu trabalho, de modo geral"},
                    {"letra": "d", "descricao": "Tenho vergonha de falar sobre meu trabalho ou não recomendaria meu emprego a outras pessoas"},
                    {"letra": "e", "descricao": "No trabalho, não me sinto energizado ou imerso no que faço"}
                ]}
            
            ]
                  
            for tema_data in temas:
                tema = Tema(numero=tema_data["numero"], descricao=tema_data["descricao"], macro_tema=tema_data["macro"])
                db.session.add(tema)
                db.session.flush()
                
                for subtema_data in tema_data["subtemas"]:
                    subtema = Subtema(letra=subtema_data["letra"], descricao=subtema_data["descricao"], tema=tema)
                    db.session.add(subtema)     
            
            recomendacoes = [
                # Tema 1 - Intensidade e ritmo
                {"tema_numero": 1, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. O ritmo de trabalho está adequado, mantenha o monitoramento regular."},
                {"tema_numero": 1, "faixa_nivel": 1, "descricao": "Implementar check-ins periódicos para avaliar percepções sobre o ritmo de trabalho. Analisar distribuição de tarefas."},
                {"tema_numero": 1, "faixa_nivel": 2, "descricao": "Revisar a distribuição de tarefas e prazos. Considerar ajustes de cronograma e implementar pausas programadas."},
                {"tema_numero": 1, "faixa_nivel": 3, "descricao": "Redistribuir urgentemente a carga de trabalho, limitar horas extras e implementar apoio adicional para equipes sobrecarregadas."},
                {"tema_numero": 1, "faixa_nivel": 4, "descricao": "Intervenção imediata: redesenhar processos de trabalho, contratar pessoal adicional e implementar política de limite máximo de horas trabalhadas."},
                
                # Tema 2 - Variações no trabalho
                {"tema_numero": 2, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. As variações nas atividades de trabalho estão equilibradas."},
                {"tema_numero": 2, "faixa_nivel": 1, "descricao": "Iniciar pequenas modificações nas rotinas para introduzir mais variedade nas tarefas diárias."},
                {"tema_numero": 2, "faixa_nivel": 2, "descricao": "Implementar rotação de funções e diversificar tarefas dentro da equipe para reduzir monotonia."},
                {"tema_numero": 2, "faixa_nivel": 3, "descricao": "Reorganizar fluxos de trabalho, adicionar novas responsabilidades e implementar sistema formal de rotação de tarefas."},
                {"tema_numero": 2, "faixa_nivel": 4, "descricao": "Reestruturação completa das funções, com redesenho dos cargos para garantir variação adequada e prevenção de lesões por esforço repetitivo."},
                
                # Tema 3 - Dificuldade do trabalho
                {"tema_numero": 3, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. O nível de dificuldade está bem ajustado às capacidades da equipe."},
                {"tema_numero": 3, "faixa_nivel": 1, "descricao": "Oferecer materiais de referência e pequenos treinamentos para apoiar a execução de tarefas mais complexas."},
                {"tema_numero": 3, "faixa_nivel": 2, "descricao": "Implementar treinamentos técnicos regulares e criar procedimentos de suporte para tarefas complexas."},
                {"tema_numero": 3, "faixa_nivel": 3, "descricao": "Desenvolver sistema estruturado de mentoria, simplificar processos decisórios e revisar requisitos técnicos excessivos."},
                {"tema_numero": 3, "faixa_nivel": 4, "descricao": "Redesenhar completamente os requisitos do cargo, implementar suporte técnico constante e estabelecer equipes multidisciplinares para decisões complexas."},
                
                # Tema 4 - Demanda mental
                {"tema_numero": 4, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. A carga mental está bem equilibrada."},
                {"tema_numero": 4, "faixa_nivel": 1, "descricao": "Sugerir técnicas de organização mental e implementar pequenas pausas ao longo do dia."},
                {"tema_numero": 4, "faixa_nivel": 2, "descricao": "Introduzir pausas cognitivas programadas e implementar checklists para reduzir sobrecarga mental."},
                {"tema_numero": 4, "faixa_nivel": 3, "descricao": "Desenvolver ferramentas de suporte para tomada de decisão, reduzir multitarefas e estabelecer períodos protegidos para trabalho concentrado."},
                {"tema_numero": 4, "faixa_nivel": 4, "descricao": "Redesenhar completamente processos cognitivos, introduzir sistemas de IA de suporte, implementar pausas mandatórias e revezamento em funções de alta exigência mental."},
                
                # Tema 5 - Perturbação emocional
                {"tema_numero": 5, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. O ambiente emocional parece saudável."},
                {"tema_numero": 5, "faixa_nivel": 1, "descricao": "Disponibilizar materiais sobre inteligência emocional e técnicas de autocuidado para situações desafiadoras."},
                {"tema_numero": 5, "faixa_nivel": 2, "descricao": "Oferecer workshops sobre gestão emocional e estabelecer espaços seguros para expressão de sentimentos e opiniões."},
                {"tema_numero": 5, "faixa_nivel": 3, "descricao": "Implementar programa estruturado de suporte psicológico, rodízio em funções emocionalmente desgastantes e treinamento avançado em resiliência."},
                {"tema_numero": 5, "faixa_nivel": 4, "descricao": "Intervenção emergencial com suporte terapêutico contínuo, redesenho completo de funções com alta carga emocional e implementação de equipes de suporte dedicadas."},
                
                # Tema 6 - Relacionamento com colegas
                {"tema_numero": 6, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. As relações entre colegas são saudáveis e cooperativas."},
                {"tema_numero": 6, "faixa_nivel": 1, "descricao": "Promover momentos informais de integração e reconhecer publicamente comportamentos colaborativos."},
                {"tema_numero": 6, "faixa_nivel": 2, "descricao": "Implementar atividades estruturadas de team building e estabelecer normas claras de comunicação respeitosa."},
                {"tema_numero": 6, "faixa_nivel": 3, "descricao": "Realizar treinamentos específicos em comunicação não-violenta, implementar mediação de conflitos e reorganizar equipes problemáticas."},
                {"tema_numero": 6, "faixa_nivel": 4, "descricao": "Intervenção imediata com consultoria especializada em clima organizacional, possível remanejo de pessoas e implementação de política rigorosa anti-assédio moral."},
                
                # Tema 7 - Relacionamento com superiores
                {"tema_numero": 7, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. A relação com a liderança é transparente e construtiva."},
                {"tema_numero": 7, "faixa_nivel": 1, "descricao": "Implementar reuniões periódicas de feedback e canais simples para sugestões."},
                {"tema_numero": 7, "faixa_nivel": 2, "descricao": "Oferecer treinamento básico em liderança e estabelecer canais seguros para feedback anônimo."},
                {"tema_numero": 7, "faixa_nivel": 3, "descricao": "Implementar programa intensivo de desenvolvimento de lideranças, coaching para gestores e reestruturar canais de comunicação hierárquica."},
                {"tema_numero": 7, "faixa_nivel": 4, "descricao": "Intervenção emergencial na cultura de liderança, possível substituição de gestores problemáticos e implementação de programa de transformação de liderança com acompanhamento externo."},
                
                # Tema 8 - Impacto na vida pessoal
                {"tema_numero": 8, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. Há bom equilíbrio entre vida profissional e pessoal."},
                {"tema_numero": 8, "faixa_nivel": 1, "descricao": "Oferecer dicas de gestão do tempo e reforçar a importância de respeitar horários de descanso."},
                {"tema_numero": 8, "faixa_nivel": 2, "descricao": "Implementar política de flexibilidade de horários e desconexão digital após o expediente."},
                {"tema_numero": 8, "faixa_nivel": 3, "descricao": "Revisar cargas de trabalho, estabelecer limites rígidos para contatos fora do horário e oferecer suporte para questões de conciliação familiar."},
                {"tema_numero": 8, "faixa_nivel": 4, "descricao": "Redesenhar completamente a jornada de trabalho, implementar banco de horas obrigatório, oferecer suporte especializado para casos graves e revisar metas inatingíveis."},
                
                # Tema 9 - Confiança no ambiente de trabalho
                {"tema_numero": 9, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. Há cultura de confiança mútua na organização."},
                {"tema_numero": 9, "faixa_nivel": 1, "descricao": "Aumentar a transparência nas comunicações básicas e reconhecer comportamentos que demonstrem confiança."},
                {"tema_numero": 9, "faixa_nivel": 2, "descricao": "Implementar práticas de comunicação transparente e incentivar a colaboração entre departamentos."},
                {"tema_numero": 9, "faixa_nivel": 3, "descricao": "Realizar diagnóstico detalhado de clima, reorganizar processos que geram desconfiança e implementar gestão participativa."},
                {"tema_numero": 9, "faixa_nivel": 4, "descricao": "Intervenção profunda na cultura organizacional, com facilitadores externos, reformulação de políticas de transparência e possível mudança na liderança sênior."},
                
                # Tema 10 - Clareza sobre papéis e metas
                {"tema_numero": 10, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. Os papéis e metas são claros e bem comunicados."},
                {"tema_numero": 10, "faixa_nivel": 1, "descricao": "Revisar e atualizar descrições de cargo e clarificar expectativas de desempenho individual."},
                {"tema_numero": 10, "faixa_nivel": 2, "descricao": "Implementar sistema regular de feedback e desenvolvimento de competências alinhadas às descrições de cargo."},
                {"tema_numero": 10, "faixa_nivel": 3, "descricao": "Reestruturar o sistema de gestão de desempenho, com objetivos SMART e acompanhamento constante de progresso."},
                {"tema_numero": 10, "faixa_nivel": 4, "descricao": "Redesenhar completamente os cargos e responsabilidades, implementar metodologia OKR e cascateamento claro de objetivos com verificações frequentes."},
                
                # Tema 11 - Impacto negativo por fatores externos
                {"tema_numero": 11, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. Os fatores externos são bem gerenciados."},
                {"tema_numero": 11, "faixa_nivel": 1, "descricao": "Mapear principais interrupções e implementar soluções simples para minimizá-las."},
                {"tema_numero": 11, "faixa_nivel": 2, "descricao": "Definir protocolos de comunicação entre equipes e estabelecer períodos sem interrupções."},
                {"tema_numero": 11, "faixa_nivel": 3, "descricao": "Redesenhar interfaces entre departamentos, implementar gestão de recursos mais eficiente e criar espaços protegidos para trabalho concentrado."},
                {"tema_numero": 11, "faixa_nivel": 4, "descricao": "Reestruturação completa dos fluxos de trabalho, revisão dos recursos disponíveis e implementação de métodos ágeis para gerenciamento de interdependências."},
                
                # Tema 12 - Percepção de injustiça
                {"tema_numero": 12, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. Há percepção de justiça organizacional."},
                {"tema_numero": 12, "faixa_nivel": 1, "descricao": "Aumentar a transparência nos critérios de distribuição de trabalho e reconhecimento."},
                {"tema_numero": 12, "faixa_nivel": 2, "descricao": "Implementar sistema de sugestões com feedback obrigatório e treinar líderes em justiça organizacional."},
                {"tema_numero": 12, "faixa_nivel": 3, "descricao": "Revisar políticas de promoção e remuneração, estabelecer comitê de avaliação imparcial e criar canal seguro para denúncias."},
                {"tema_numero": 12, "faixa_nivel": 4, "descricao": "Reformulação completa das políticas de gestão de pessoas, com auditoria externa de equidade, implementação de ombudsman e revisão de casos históricos."},
                
                # Tema 13 - Desenvolvimento profissional
                {"tema_numero": 13, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. Há boas oportunidades de desenvolvimento."},
                {"tema_numero": 13, "faixa_nivel": 1, "descricao": "Comunicar melhor as oportunidades existentes e incentivar o desenvolvimento autodirigido."},
                {"tema_numero": 13, "faixa_nivel": 2, "descricao": "Implementar planos de desenvolvimento individual e disponibilizar recursos de aprendizagem."},
                {"tema_numero": 13, "faixa_nivel": 3, "descricao": "Desenvolver trilhas claras de carreira, estabelecer programa formal de mentoria e criar projetos para aplicação de novas competências."},
                {"tema_numero": 13, "faixa_nivel": 4, "descricao": "Redesenhar completamente a estratégia de desenvolvimento, com orçamento dedicado, parcerias educacionais e tempo protegido para aprendizagem."},
                
                # Tema 14 - Participação e autonomia
                {"tema_numero": 14, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. Há bom nível de autonomia e participação."},
                {"tema_numero": 14, "faixa_nivel": 1, "descricao": "Incentivar pequenas decisões autônomas e reconhecer iniciativas individuais."},
                {"tema_numero": 14, "faixa_nivel": 2, "descricao": "Reduzir níveis de aprovação desnecessários e criar espaços regulares para contribuições dos colaboradores."},
                {"tema_numero": 14, "faixa_nivel": 3, "descricao": "Implementar gestão participativa estruturada, delegar responsabilidades significativas e reduzir controles excessivos."},
                {"tema_numero": 14, "faixa_nivel": 4, "descricao": "Transformar o modelo de gestão para abordagens como sociocracia ou holocracia, com equipes autogeridas e empoderamento radical."},
                
                # Tema 15 - Comportamentos prejudiciais
                {"tema_numero": 15, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. O ambiente está livre de comportamentos prejudiciais."},
                {"tema_numero": 15, "faixa_nivel": 1, "descricao": "Reforçar os valores organizacionais e oferecer treinamento básico sobre respeito no ambiente de trabalho."},
                {"tema_numero": 15, "faixa_nivel": 2, "descricao": "Implementar política clara de consequências para comportamentos inadequados e treinar gestores para identificá-los."},
                {"tema_numero": 15, "faixa_nivel": 3, "descricao": "Criar canal de denúncias com proteção ao denunciante, implementar programa intensivo sobre diversidade e respeito e investigar casos existentes."},
                {"tema_numero": 15, "faixa_nivel": 4, "descricao": "Intervenção imediata com consultoria externa especializada, afastamento temporário dos agressores, suporte psicológico às vítimas e reformulação completa das políticas de conduta."},
                
                # Tema 16 - Saúde mental
                {"tema_numero": 16, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. Os indicadores de saúde mental são positivos."},
                {"tema_numero": 16, "faixa_nivel": 1, "descricao": "Promover conscientização sobre saúde mental e oferecer recursos de autocuidado."},
                {"tema_numero": 16, "faixa_nivel": 2, "descricao": "Implementar programa regular de práticas de bem-estar e disponibilizar suporte psicológico básico."},
                {"tema_numero": 16, "faixa_nivel": 3, "descricao": "Oferecer suporte psicológico profissional, identificar e reduzir fatores de estresse organizacional e treinar líderes em saúde mental."},
                {"tema_numero": 16, "faixa_nivel": 4, "descricao": "Intervenção emergencial com programa abrangente de saúde mental, redesenho de funções de alto impacto emocional e parceria com especialistas para casos graves."},
                
                # Tema 17 - Qualidade do sono
                {"tema_numero": 17, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. O trabalho não afeta negativamente o sono dos colaboradores."},
                {"tema_numero": 17, "faixa_nivel": 1, "descricao": "Oferecer informações sobre higiene do sono e descanso adequado."},
                {"tema_numero": 17, "faixa_nivel": 2, "descricao": "Implementar política de desconexão digital e evitar agendamento de tarefas próximo aos horários de descanso."},
                {"tema_numero": 17, "faixa_nivel": 3, "descricao": "Revisar escalas de trabalho, eliminar expectativas de resposta fora do horário e oferecer programa de saúde do sono."},
                {"tema_numero": 17, "faixa_nivel": 4, "descricao": "Redesenhar completamente turnos e escalas, proibir comunicações fora do horário, oferecer suporte especializado e ajustar metas para reduzir preocupações constantes."},
                
                # Tema 18 - Preocupação com futuro profissional
                {"tema_numero": 18, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. Há segurança e perspectivas claras de futuro profissional."},
                {"tema_numero": 18, "faixa_nivel": 1, "descricao": "Melhorar a comunicação sobre estabilidade organizacional e perspectivas de carreira."},
                {"tema_numero": 18, "faixa_nivel": 2, "descricao": "Implementar comunicações regulares sobre o direcionamento da empresa e oferecer workshops de desenvolvimento de carreira."},
                {"tema_numero": 18, "faixa_nivel": 3, "descricao": "Desenvolver programa estruturado de planejamento de carreira, aumentar a transparência sobre mudanças e oferecer suporte para adaptação a transformações."},
                {"tema_numero": 18, "faixa_nivel": 4, "descricao": "Implementar programa abrangente de segurança profissional, com requalificação contínua, comunicação transparente sobre o futuro da organização e planos de contingência individuais."},
                
                # Tema 19 - Reconhecimento e importância do trabalho
                {"tema_numero": 19, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. O trabalho é reconhecido e valorizado adequadamente."},
                {"tema_numero": 19, "faixa_nivel": 1, "descricao": "Implementar práticas simples de reconhecimento e destacar o impacto do trabalho individual."},
                {"tema_numero": 19, "faixa_nivel": 2, "descricao": "Criar programa formal de reconhecimento e conectar o trabalho individual à missão e valor da organização."},
                {"tema_numero": 19, "faixa_nivel": 3, "descricao": "Revisar sistema de recompensas, implementar reconhecimento estruturado em múltiplos níveis e redesenhar cargos para aumentar significado."},
                {"tema_numero": 19, "faixa_nivel": 4, "descricao": "Transformação completa da cultura de reconhecimento, com revisão do sistema de remuneração, redesenho profundo dos cargos e implementação de práticas de trabalho com propósito."},
                
                # Tema 20 - Satisfação geral com o trabalho
                {"tema_numero": 20, "faixa_nivel": 0, "descricao": "Nenhum risco identificado. Há alto nível de satisfação geral com o trabalho."},
                {"tema_numero": 20, "faixa_nivel": 1, "descricao": "Realizar pesquisas específicas para identificar pequenos pontos de melhoria na satisfação."},
                {"tema_numero": 20, "faixa_nivel": 2, "descricao": "Implementar melhorias nos fatores mais citados de insatisfação e estabelecer grupos de trabalho para soluções."},
                {"tema_numero": 20, "faixa_nivel": 3, "descricao": "Conduzir diagnóstico organizacional completo, implementar plano estruturado de melhoria e monitorar indicadores de engajamento."},
                {"tema_numero": 20, "faixa_nivel": 4, "descricao": "Transformação organizacional profunda, com redesenho de processos, cultura, liderança e condições de trabalho, guiada por consultoria especializada."}
            ]
            
            for rec_data in recomendacoes:
                tema = Tema.query.filter_by(numero=rec_data["tema_numero"]).first()
                if tema:
                    recomendacao = Recomendacao(
                        tema_id=tema.id, 
                        faixa_nivel=rec_data["faixa_nivel"], 
                        descricao=rec_data["descricao"]
                        )
                    db.session.add(recomendacao)
            
            db.session.commit()

if __name__ == '__main__':
    inicializar_db()  # Esta linha chama a função para inicializar o banco de dados
    app.run(debug=True)

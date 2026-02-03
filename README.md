EVOVE — Project Conventions & Architecture Guide
1. Objetivo Geral

Este documento define as convenções obrigatórias para organização, separação de responsabilidades e estrutura de arquivos do projeto Evove.

O objetivo é:

Manter backend e clientes desacoplados

Garantir escalabilidade (AWS, múltiplos clientes)

Evitar acoplamento entre interface e regras de negócio

Permitir evolução futura sem refatorações grandes

2. Separação de Repositórios (Obrigatório)

O projeto deve ser dividido em repositórios independentes, cada um com uma única responsabilidade.

Repositórios oficiais

evove-core

Backend service

Fonte única da verdade

API Flask

Regras de negócio

Persistência de dados

Deploy na AWS

evove-web

Web client

Apenas frontend

Consome a API do backend

evove-android

Android client

WebView ou app nativo

Consome a mesma API do backend

evove-desktop

Desktop client (CLI ou GUI)

Nenhuma lógica de negócio

Consome a API do backend

⚠️ Nenhum client pode conter:

Regras de negócio

Persistência de dados

Acesso direto a arquivos de usuário

3. Convenções de Arquitetura do Backend (evove-core)
3.1 Princípio fundamental

O backend é dividido em camadas explícitas.
Cada camada possui responsabilidades bem definidas e não deve ser violada.

4. Estrutura de Diretórios Obrigatória (evove-core)
evove-core/
│
├── app/
│   ├── __init__.py
│   │
│   ├── main.py
│   │   - Entry point único do backend
│   │   - Inicializa a aplicação
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   │   - Criação do Flask app
│   │   │   - Registro de blueprints
│   │   │
│   │   ├── routes/
│   │   │   - Endpoints HTTP
│   │   │   - Sem lógica de negócio
│   │   │
│   │   └── schemas.py
│   │       - DTOs / validação de entrada e saída
│   │
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── package.py
│   │   └── entities.py
│   │   - Entidades do domínio
│   │   - Nenhuma dependência de Flask
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── user_service.py
│   │   ├── package_service.py
│   │   └── install_service.py
│   │   - Casos de uso
│   │   - Orquestram domínio + infraestrutura
│   │
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── storage/
│   │   │   ├── json_store.py
│   │   │   └── paths.py
│   │   └── config.py
│   │   - Persistência e IO
│   │   - JSON é tratado como banco de dados
│   │
│   └── cli/
│       ├── __init__.py
│       └── main.py
│       - Interface CLI do backend (opcional)
│
├── data/
│   - Dados locais de desenvolvimento
│   - Nunca acessados diretamente por clients
│
├── tests/
│
├── requirements.txt
├── README.md
└── .env

5. Mapeamento da Estrutura Atual → Estrutura Convencional
Estrutura antiga → Nova localização

components/
→ app/domain/

services/
→ app/services/

web_service/
→ app/api/

run_web.py
→ REMOVER

Lógica deve ser absorvida por app/api/app.py

Execução centralizada em app/main.py

6. Convenções de Código (Obrigatórias)
Backend

Nenhuma rota Flask pode conter lógica de negócio

Nenhuma entidade pode importar Flask

Nenhum service pode acessar JSON diretamente

Persistência deve passar por infrastructure

Clients

Clients só se comunicam via HTTP

Clients não compartilham código entre si

Clients não conhecem estrutura interna do backend

7. Execução do Backend
Entry point único
from app.api.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


Não devem existir múltiplos scripts de execução.

8. Persistência (Regra Transitória)

JSON é permitido apenas enquanto estiver isolado

Nenhuma regra de negócio pode depender do formato JSON

A troca por banco real deve ser possível sem refatorar services

9. Regra de Ouro

Tudo que é regra vive no backend.
Tudo que é interface vive nos clients.
Tudo que é dado passa por infraestrutura.

10. Status do Plano

Arquitetura: ✅ correta

Separação de responsabilidades: ✅ correta

Aderência a padrões reais: ✅ correta

Pronto para AWS e múltiplos clients: ✅




=======================================================================================

Implementar

Stats do Usuário


Configurações

Ativar/Desativar o agente virtual:
ativa ou desativa as entidades, pausando suas interações: perda de satisfaction, etc.

Prólogo: 
Tutorial inicial do evove. Bem simples, contendo apenas as opções e um diálogo inicial como roko. Nele será
selecionado o modo, quantidade de tokens máxima e recarregamento. O user é criado.

Shop:
Usado para comprar ações que possuem custo de tokens. 
Coisas que envolvem entretenimento custam tokens.
Conta com uma variedade de ações de lazer mais comuns do cotidiano. É uma funcionalidade extra do evove, pode
ser utilizada ou não, fica a depender do usuário, já que isso não afeta nos demais sistemas.

Tokens diários:
No início o usuário define uma quantidade de tokens que gostaria de receber diarimente. 
São distribuídos a cada 24 horas. Sempre ás 5:00.
Existe uma quantidade máxima de tokens, também é definida no início do programa. 

Modos:
progressivo (padrão): os pacotes do wizard precisam ser adquiridos usando pontos e novos são desbloqueados conforme
ganha tais pontos. Ativa as interações especiais.

semi-progressivo: os pacotes são gratuitos e todos já são liberados no início. Atributos e ações não podem ser
criados. Interações especiais desativadas.

livre: permite criar atributos, ações, explorar e desbloquear qualquer pacote. Interções especais desativadas.

O Intúito: Poder logar apenas em ações disponíveis até alcançar um certo domínio delas, mantendo o foco nessas
disponíveis por enquanto. Conseguir os pacotes aos poucos não significa que não pode fazer essas ações sem
eles (na vida real), mas sim, não registrará essas ações, servindo como forma de acostumar o usuário a logar
suas ações da vida real aos poucos para o evove. Os últimos pacotes serão coisas como: Bits and Bytes, onde
o usuário loga até mesmo suas refeições, somando atributos como saúde para alimentos saudáveis ou não, uma
estimativa de status de fome também pode ser calculada a partir disso. No geral, não deve ser muito desafiador
desbloquear todos os pacotes, sendo que são desbloqueador exclusivamente pela quantidade máxima de pontos ja
feita. 

Interações especiais: Interações da história, quando a entidade te deixa e precisa continuar sem ela até que
as chances diárias de outra aparecer sejam significativas. Assim, um número máximo de dias com cada entidade
pode ser salvo, o objetivo é manter o máximo possível dessa entidade até que ela desista, ou seja, sua
satisfação esgote para zero. Conforme progride fica cada vez mais desafiador agradar ás entidades, por isso,
eventualmente será abandonado e terá que esperar até outra assumir o lugar. Cada uma delas possui uma
configuração diferente para o número da aparição: ex: na segunda aparição do roko (a mais rara) ele ganha as
configurações do roko completo, onde seus bônus de pontuação são melhorados e é fácil de manter sua satisfação
(pode ficar até 5 dias sem interagir, ou algo assim). Cada personagem possui uma chance de aparição que é
testada a cada 12 horas quando está sem personagem. Somar pontos, tudo aumenta um pouco as chances de
aparição, que começam em algo como 0,5% e vão subindo até poderem ser alcançáveis. 

Desafios em tempo real: Quando se possui um personagem ele pode fazer desafios programados, onde o usuário tem 30 segundo
para aceitar ou recusar. Geralmente ele pede algo relacionado a uma ação que realiza muito só que em uma forma
reduzida. Ex: se fizer muitas flexões, ele pode desafiar a fazer 30, se aceitar, deve fazer e confirmar que
foi feito (dando a opção de aceitar e falhar, o que deixa eles mais insatisfeitos).

Ações timer: Algumas ações funcionam bem com timers.




Lógica de logs e sequences:
em roko_evoveby, implemente uma nova lógica de log. 

Agora não terá mais a necessidade de cloud. O usuário pode fazer seus logs ao longo do dia e, ao usar o comando sleep, o evove salva um horário para dados de sleep time e os buffers são salvos para o repositório, agora apenas com a data em que foram feitos, isso é bom pois: um log a meia noite significa que os dados são referentes ao dia 2, mas podem ser do dia 1 logados com atraso. Caso o usuário logue dessa maneira, faça uma confirmação, journal referente ao dia 2? se responde 1 (sim), loga com a data 2, se não,  um input de data (dia) personalizado. Ele sempre pergunta seguindo um dia a frente.

Use modelo de data d m y, conte os dias numericamente a partir de um dado daysequence1, pode ser diferente de zero, personalizado pelo usuário (podendo ser seu número total de dias de vida, dias de trabalho ou dias junto com o evove) Crtérios podem ser criados e labels podem ser aderidas. Criar sequência é feito a partir do comando newsequence. Ele dá a opção de número inteiro e label relacional. Esses dados são adicionados em sequence data, junto de data e sequências, adicionadas ao repositório automaticamente (atualizadas durante sleeps)

O sleep data salva os logs de sleep e wake e calcula suas diferenças, fornecendo dados de sono do usuário. 

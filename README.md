# AtendeDoc — atendimento com documentos e fontes

Assistente em português para consultar políticas, produtos e procedimentos, com referência ao documento e à posição de cada trecho usado na resposta.

O projeto reúne recuperação de informação, integração generativa opcional, interface Streamlit e API FastAPI. A base inicial apresenta a **Lume Casa, uma loja fictícia**, e pode ser substituída por documentos próprios em Markdown, TXT ou PDF com texto selecionável.

**[Estudo de caso](docs/ESTUDO_DE_CASO.md)** · **[Arquitetura e validação](docs/ARQUITETURA.md)** · **[Resultados da avaliação](reports/evaluation.json)**

## Funcionalidades

| Recurso | Comportamento |
| --- | --- |
| Documentos próprios | Até 5 arquivos; processamento em memória na sessão do painel. |
| Recuperação de fontes | TF-IDF combina palavras e sequências de caracteres para localizar até três trechos. |
| Consulta local | Reproduz os trechos encontrados com fonte, seção e página ou linhas. Funciona sem chave de API. |
| Síntese generativa | Redige uma resposta a partir dos trechos recuperados e valida os identificadores das citações. |
| Ausência de informação | Informa quando a recuperação não encontra evidência suficiente, em vez de criar uma resposta livre. |
| Atendimento individual | Encaminha consultas com identificadores de pedidos para atendimento autenticado. |
| Integração | API com contratos de entrada, documentação interativa e respostas em JSON. |

## Executar o painel

Use Python 3.12. Na raiz do repositório:

```bash
python -m venv .venv
```

Ative o ambiente:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# Linux/macOS
source .venv/bin/activate
```

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Abra a URL local mostrada pelo Streamlit. A base demonstrativa já acompanha o código, sem necessidade de download de modelos ou cadastro em um provedor para a consulta local.

### Perguntas de exemplo

- Qual é o prazo de entrega para São Paulo?
- Como posso devolver um produto?
- Existe desconto para Pix?
- A Caneca Brisa pode ir ao micro-ondas?
- Qual é a previsão do tempo amanhã? — exemplo de pergunta fora da base.

No painel, a opção **Meus documentos** usa somente os arquivos enviados naquela sessão. PDFs digitalizados precisam passar por OCR antes do envio. Limites: 2 MB por arquivo, 30 páginas por PDF e 300.000 caracteres ou 600 trechos por base.

## API

```bash
python -m uvicorn atendedoc.api:app --host 127.0.0.1 --port 8001
```

Documentação interativa: http://127.0.0.1:8001/docs

| Rota | Uso |
| --- | --- |
| GET /health | Verificar o serviço e a quantidade de trechos. |
| GET /sources | Listar os documentos da base demonstrativa. |
| POST /ask | Consultar uma pergunta e receber resposta, fontes e duração. |

Exemplo de corpo para POST /ask:

```json
{
  "question": "Como funciona o frete grátis?",
  "mode": "extractive"
}
```

A API usa a base demonstrativa do servidor. O envio de documentos próprios é um recurso do painel. A execução local não expõe a API à internet; uma publicação externa deve configurar autenticação, limites de requisição e segredos no ambiente de hospedagem.

## Síntese com IA

Configure OPENAI_API_KEY e OPENAI_MODEL no ambiente do servidor, usando uma chave e um modelo da sua conta com suporte a saída estruturada. O aplicativo não carrega .env automaticamente e não solicita chaves pelo chat.

```powershell
# Depois de configurar OPENAI_API_KEY no ambiente:
$env:OPENAI_MODEL = 'nome-do-modelo-na-sua-conta'
python -m streamlit run app.py
```

O painel solicita autorização antes de enviar a pergunta e os trechos ao provedor. Na API, o modo generative exige approve_external_processing=true. A chamada pode consumir créditos da API.

A integração usa saída JSON estruturada, store=False e validação dos identificadores de fontes. O modo extrativo faz recuperação e reprodução de evidências; a síntese por LLM é a etapa generativa do fluxo RAG. Não há uso de embeddings semânticos nesta versão.

## Avaliação e testes

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m atendedoc evaluate
```

O conjunto de referência tem **28 perguntas**: 20 consultas com fonte esperada, 5 perguntas fora da base e 3 casos de encaminhamento ou proteção de dados. O relatório registra o resultado de cada pergunta, as seções recuperadas e a duração.

Na execução de referência, foram atendidos **28 de 28 critérios**, com **100% de recuperação da seção esperada entre as três primeiras fontes** nas 20 perguntas com referência. Os resultados descrevem esse conjunto pequeno e específico da loja fictícia; não medem qualidade geral de atendimento nem desempenho em documentos externos.

Os testes verificam ingestão de texto e PDF, isolamento entre bases, posições das fontes, limites de entrada, validação das citações, contratos da API e fluxo da interface. A integração generativa é testada com cliente simulado; sua qualidade de redação depende de avaliação com o modelo configurado.

## Organização

```text
app.py                       # Interface Streamlit
atendedoc/
  retrieval.py               # Documentos, trechos e busca lexical
  assistant.py               # Respostas e validação de citações
  api.py                     # Serviço FastAPI
  __main__.py                # Consulta e avaliação pelo terminal
data/knowledge_base/         # Documentos da loja fictícia
evals/questions.json         # Perguntas com critérios esperados
reports/evaluation.json      # Avaliação reproduzível
tests/                       # Testes automatizados
docs/                        # Estudo de caso e arquitetura
```

Os documentos e as políticas da Lume Casa foram criados para este projeto e não descrevem uma empresa real. O desenvolvimento foi assistido por IA, com validação automatizada e rastreabilidade das fontes.

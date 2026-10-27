"""Interface do AtendeDoc: python -m streamlit run app.py."""
from hashlib import sha256
import json
import os
from pathlib import Path

import streamlit as st

from atendedoc.assistant import ProviderError, answer_question
from atendedoc.retrieval import KnowledgeIndex, demo_chunks, ingest_bytes

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="AtendeDoc | Respostas com fontes", page_icon="💬", layout="wide")
st.markdown("""<style>
.stApp {background:#f6f7fb;}
[data-testid="stSidebar"] {background:#edf0f7;}
.block-container {padding-top:4rem;max-width:1450px;}
h1,h2,h3 {color:#223354;}
.eyebrow {color:#6755c7;letter-spacing:2px;font-size:13px;font-weight:700;}
.intro {color:#57647b;font-size:18px;max-width:850px;}
[data-testid="stMetric"] {background:white;border-radius:12px;}
</style>""", unsafe_allow_html=True)


@st.cache_resource
def demo_index():
    return KnowledgeIndex(demo_chunks())


with st.sidebar:
    st.markdown("### Base de conhecimento")
    collection = st.radio("Documentos usados na consulta", ["Loja demonstrativa", "Meus documentos"])
    if collection == "Loja demonstrativa":
        index = demo_index()
        st.caption("Lume Casa · loja fictícia. Políticas e produtos criados para este projeto.")
    else:
        uploaded = st.file_uploader("Enviar documentos", type=["md", "txt", "pdf"], accept_multiple_files=True)
        st.caption("Até 5 arquivos, 2 MB cada. PDF com texto selecionável, até 30 páginas. Os arquivos ficam na memória desta sessão.")
        if not uploaded:
            st.info("Envie documentos para começar a consulta.")
            st.stop()
        if len(uploaded) > 5:
            st.error("Selecione no máximo 5 documentos.")
            st.stop()
        upload_key = sha256(b"".join(file.name.encode() + file.getvalue() for file in uploaded)).hexdigest()
        if st.session_state.get("upload_key") != upload_key:
            try:
                chunks = [chunk for file in uploaded for chunk in ingest_bytes(file.name, file.getvalue())]
                st.session_state["upload_index"] = KnowledgeIndex(chunks)
                st.session_state["upload_key"] = upload_key
            except ValueError as error:
                st.error(str(error))
                st.stop()
        index = st.session_state["upload_index"]
    documents = sorted({chunk.source for chunk in index.chunks})
    st.divider()
    st.write(f"**{len(documents)} documentos · {len(index.chunks)} trechos**")
    st.caption("As fontes exibidas correspondem à base selecionada.")
    st.link_button("Ver projeto no GitHub", "https://github.com/GustavoCurio/atendedoc")

st.markdown('<div class="eyebrow">ATENDEDOC · ATENDIMENTO COM EVIDÊNCIAS</div>', unsafe_allow_html=True)
st.title("A resposta começa nos seus documentos")
st.markdown('<p class="intro">Consulte políticas, produtos e procedimentos. Cada resposta mostra de onde veio a informação para facilitar a conferência das fontes.</p>', unsafe_allow_html=True)
a, b, c = st.columns(3)
a.metric("Documentos na base", len(documents), border=True)
b.metric("Trechos indexados", len(index.chunks), border=True)
c.metric("Fontes por consulta", "Até 3", border=True)

chat, library, about = st.tabs(["Atendimento", "Documentos e fontes", "Como funciona"])
with chat:
    st.subheader("Como podemos ajudar?")
    mode_label = st.radio("Formato da resposta", ["Trechos dos documentos", "Síntese com IA"], horizontal=True)
    mode = "generative" if mode_label == "Síntese com IA" else "extractive"
    configured = bool(os.environ.get("OPENAI_API_KEY") and os.environ.get("OPENAI_MODEL"))
    context_key = sha256((mode + "|".join(chunk.id for chunk in index.chunks)).encode()).hexdigest()
    if st.session_state.get("context_key") != context_key:
        st.session_state["history"] = []
        st.session_state["context_key"] = context_key
    if collection == "Loja demonstrativa":
        suggestions = st.columns(3)
        for column, label, question in zip(suggestions,
                ["Prazo de entrega", "Trocas e devoluções", "Formas de pagamento"],
                ["Qual é o prazo de entrega para São Paulo?", "Como posso devolver um produto?", "Quais formas de pagamento são aceitas?"]):
            if column.button(label, width="stretch"):
                st.session_state["question"] = question
    if mode == "generative" and not configured:
        st.info("A síntese com IA é ativada quando OPENAI_API_KEY e OPENAI_MODEL estão configurados no servidor. A consulta aos trechos funciona localmente.")
    with st.form("question_form"):
        question = st.text_input("Sua pergunta", key="question", max_chars=1500, placeholder="Ex.: Qual é o prazo para solicitar uma troca?")
        approved = True
        if mode == "generative":
            approved = st.checkbox("Autorizar o envio desta pergunta e dos trechos recuperados para a OpenAI. A chamada pode consumir créditos da API.")
        submitted = st.form_submit_button("Consultar documentos", type="primary", disabled=mode == "generative" and not configured)
    if submitted:
        if not approved:
            st.warning("Autorize o processamento externo para usar a síntese com IA.")
        else:
            try:
                with st.spinner("Buscando informações na base…"):
                    answer = answer_question(question, index, mode)
                st.session_state["history"].append({"question": question, "answer": answer.to_dict()})
                st.session_state["history"] = st.session_state["history"][-6:]
            except (ValueError, ProviderError) as error:
                st.error(str(error))
    for turn in reversed(st.session_state.get("history", [])):
        with st.chat_message("user"):
            st.write(turn["question"])
        response = turn["answer"]
        with st.chat_message("assistant"):
            st.caption(f"{mode_label} · {response['elapsed_ms']:.0f} ms")
            if response["status"] == "needs_human":
                st.info(response["message"])
            else:
                st.markdown(response["message"])
            for source in response["sources"]:
                position = f"página {source['page']}" if source["page"] else f"linhas {source['line_start']}–{source['line_end']}"
                with st.expander(f"[{source['reference']}] {source['source']} · {source['section']} · {position}"):
                    st.text(source["text"])
                    st.caption(f"Identificador do trecho: {source['id']} · relevância lexical: {source['score']:.3f}")
    st.caption("Trechos dos documentos: recuperação e reprodução de evidências, sem geração por LLM. Síntese com IA: redação baseada nos trechos, com validação dos identificadores das fontes.")
    if st.session_state.get("history"):
        st.download_button("Baixar consulta mais recente (JSON)", json.dumps(st.session_state["history"][-1], ensure_ascii=False, indent=2),
                           "atendedoc-consulta.json", mime="application/json")
        if st.button("Limpar consultas da sessão"):
            st.session_state["history"] = []
            st.rerun()

with library:
    st.subheader("Conheça as informações disponíveis")
    for document in documents:
        sections = [chunk for chunk in index.chunks if chunk.source == document]
        with st.expander(f"{document} · {len(sections)} trechos"):
            for chunk in sections:
                st.markdown(f"**{chunk.section}**")
                st.text(chunk.text)
    st.caption("A posição da fonte usa a página do PDF ou as linhas do arquivo de texto. PDFs digitalizados precisam passar por OCR antes do envio.")

with about:
    st.subheader("Da pergunta à evidência")
    st.markdown("""
1. **Ingestão:** documentos Markdown, TXT e PDFs com texto são divididos em trechos com origem e posição.
2. **Recuperação:** TF-IDF combina palavras e sequências de caracteres para localizar até três trechos relacionados à pergunta.
3. **Resposta:** o modo local reproduz as informações recuperadas; o modo generativo usa esses trechos para redigir uma síntese.
4. **Referências:** a síntese só é aceita quando os identificadores citados correspondem às fontes fornecidas.
""")
    st.write("Perguntas sem evidência suficiente recebem uma mensagem de ausência de informação. Consultas a pedidos individuais seguem para atendimento autenticado; este projeto não acessa sistemas de pedidos.")
    report_path = ROOT / "reports" / "evaluation.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        st.subheader("Avaliação da base demonstrativa")
        x, y, z = st.columns(3)
        x.metric("Perguntas avaliadas", report["total"])
        y.metric("Critérios atendidos", f"{report['pass_rate_pct']:.1f}%")
        z.metric("Recuperação das fontes @3", f"{report['source_recall_at_3_pct']:.1f}%")
        st.caption("Resultados no conjunto de perguntas do projeto. A avaliação verifica recuperação, ausência de informação e encaminhamento; não mede a qualidade de um LLM externo.")
    st.markdown("**Integração:** a API FastAPI oferece `/health`, `/sources` e `/ask`, com documentação interativa em `/docs`.")

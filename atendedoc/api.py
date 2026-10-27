"""API HTTP para consultar a base demonstrativa do AtendeDoc."""
from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .assistant import ProviderError, answer_question
from .retrieval import KnowledgeIndex, demo_chunks

app = FastAPI(title="AtendeDoc API", version="1.0.0", description="Atendimento baseado em documentos com fontes rastreáveis.")


@lru_cache(maxsize=1)
def index():
    return KnowledgeIndex(demo_chunks())


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1500)
    mode: Literal["extractive", "generative"] = "extractive"
    approve_external_processing: bool = False


@app.get("/health")
def health():
    return {"status": "ok", "chunks": len(index().chunks)}


@app.get("/sources")
def sources():
    return {"documents": sorted({chunk.source for chunk in index().chunks}), "chunks": len(index().chunks)}


@app.post("/ask")
def ask(body: AskRequest):
    if body.mode == "generative" and not body.approve_external_processing:
        raise HTTPException(403, "A síntese generativa exige autorização para enviar a pergunta e os trechos ao provedor.")
    try:
        return answer_question(body.question, index(), body.mode).to_dict()
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except ProviderError as error:
        raise HTTPException(502, str(error)) from error

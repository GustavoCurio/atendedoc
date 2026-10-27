"""Ingestão de documentos e recuperação lexical por palavras e caracteres."""
from dataclasses import asdict, dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
import unicodedata

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

BASE_DIR = Path(__file__).resolve().parents[1] / "data" / "knowledge_base"
MAX_BYTES = 2 * 1024 * 1024
MAX_CHARS = 150_000
STOP_WORDS = set("a ao aos as o os de da das do dos em um uma uns umas e ou se que qual quais como quando onde por para com sem sobre no na nos nas eu meu minha voce voces me posso pode podem poderia quero saber funciona tem tenho faz fazer e ela ele isso esse essa este esta isto sao ser foi muito por favor quanto quantos ate".split())
ALIASES = {
    "devolver": "devolucao troca", "devolucoes": "devolucao troca",
    "trocar": "troca", "rastrear": "rastreamento", "rastreio": "rastreamento",
    "chegar": "entrega", "demora": "prazo", "atrasou": "atraso",
    "gratuito": "gratis frete", "gratuita": "gratis frete",
    "parcelar": "parcelamento cartao", "pagar": "pagamento",
    "quebrado": "avaria", "quebrada": "avaria", "danificado": "avaria",
    "lavar": "lavagem limpeza conservacao", "tamanho": "medidas capacidade",
    "cancelar": "cancelamento", "falar": "contato atendimento",
}


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


def terms(text):
    return {token for token in re.findall(r"\b\w{2,}\b", normalize(text)) if token not in STOP_WORDS}


def expanded_query(question):
    original = normalize(question)
    return original + " " + " ".join(ALIASES[token] for token in terms(question) if token in ALIASES)


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str
    title: str
    section: str
    text: str
    line_start: int
    line_end: int
    page: int | None = None

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


def chunks_from_text(text, source, page=None):
    if len(text) > MAX_CHARS:
        raise ValueError("Documento com texto muito longo. Limite: 150.000 caracteres por arquivo.")
    if not text.strip():
        return []
    result, buffer = [], []
    title, section = Path(source).stem, "Conteúdo"

    def flush():
        if not buffer:
            return
        body = "\n".join(line for _, line in buffer).strip()
        if len(terms(body)) >= 3:
            identifier = sha256(f"{source}|{page}|{section}|{buffer[0][0]}|{len(result)}|{body}".encode()).hexdigest()[:12]
            result.append(Chunk(identifier, source, title, section, body, buffer[0][0], buffer[-1][0], page))
        buffer.clear()

    for number, line in enumerate(text.splitlines(), 1):
        heading = re.match(r"^(#{1,3})\s+(.+)", line)
        if heading:
            flush()
            if len(heading[1]) == 1:
                title = heading[2].strip()
            section = heading[2].strip()
        else:
            for offset in range(0, max(len(line), 1), 900):
                piece = line[offset:offset + 900]
                if buffer and sum(len(value) for _, value in buffer) + len(piece) > 1000:
                    flush()
                if piece.strip():
                    buffer.append((number, piece))
    flush()
    return result


def ingest_bytes(name, payload):
    filename = name.replace("\\", "/").split("/")[-1]
    extension = Path(filename).suffix.lower()
    if len(payload) > MAX_BYTES:
        raise ValueError("Cada documento deve ter no máximo 2 MB.")
    if extension not in {".md", ".txt", ".pdf"}:
        raise ValueError("Use documentos Markdown, TXT ou PDF com texto selecionável.")
    if extension != ".pdf":
        try:
            return chunks_from_text(payload.decode("utf-8-sig"), filename)
        except UnicodeDecodeError as error:
            raise ValueError("O arquivo de texto deve estar em UTF-8.") from error
    from pypdf import PdfReader
    try:
        reader = PdfReader(BytesIO(payload))
        if reader.is_encrypted:
            raise ValueError("PDF protegido por senha. Use uma cópia sem senha.")
        if len(reader.pages) > 30:
            raise ValueError("Use um PDF com até 30 páginas.")
        result, total = [], 0
        for number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            total += len(text)
            if total > MAX_CHARS:
                raise ValueError("O PDF excede 150.000 caracteres extraídos.")
            result.extend(chunks_from_text(text, filename, page=number))
        if not result:
            raise ValueError("Não foi encontrado texto selecionável no PDF. Arquivos digitalizados precisam de OCR antes do envio.")
        return result
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("Não foi possível ler o PDF. Confira se o arquivo é válido.") from error


def demo_chunks():
    return [chunk for path in sorted(BASE_DIR.glob("*.md")) for chunk in ingest_bytes(path.name, path.read_bytes())]


class KnowledgeIndex:
    def __init__(self, chunks):
        unique = {chunk.id: chunk for chunk in chunks}
        self.chunks = list(unique.values())
        if not self.chunks:
            raise ValueError("A base precisa de pelo menos um trecho de texto legível.")
        if len(self.chunks) > 600 or sum(len(chunk.text) for chunk in self.chunks) > 300_000:
            raise ValueError("A base excede o limite de 600 trechos ou 300.000 caracteres. Reduza os documentos.")
        corpus = [f"{chunk.section}\n{chunk.text}" for chunk in self.chunks]
        self.word = TfidfVectorizer(strip_accents="unicode", ngram_range=(1, 2), stop_words=sorted(STOP_WORDS), max_features=20000)
        self.char = TfidfVectorizer(strip_accents="unicode", analyzer="char_wb", ngram_range=(3, 5), max_features=30000)
        self.word_matrix = self.word.fit_transform(corpus)
        self.char_matrix = self.char.fit_transform(corpus)

    def search(self, question, top_k=3, min_score=0.14):
        query = expanded_query(question)
        query_terms = terms(query)
        word_scores = (self.word_matrix @ self.word.transform([query]).T).toarray().ravel()
        char_scores = (self.char_matrix @ self.char.transform([query]).T).toarray().ravel()
        scores = 0.8 * word_scores + 0.2 * char_scores
        hits = []
        for position in np.argsort(-scores, kind="stable"):
            chunk = self.chunks[int(position)]
            overlap = query_terms & terms(chunk.section + " " + chunk.text)
            if float(scores[position]) >= min_score and overlap and len(overlap) / max(len(query_terms), 1) >= 0.2:
                hits.append(Hit(chunk, round(float(scores[position]), 5)))
            if len(hits) == top_k:
                break
        return hits

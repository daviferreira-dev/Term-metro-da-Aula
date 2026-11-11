from collections import Counter
from datetime import datetime
import io
from typing import Literal

import cv2
from fastapi import FastAPI, File, HTTPException, UploadFile
import numpy as np
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from transformers import pipeline

app = FastAPI(title="Termômetro da Aula")

# ------------------ Modelos de IA (carregados uma vez) ------------------
detector = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)
classificador = pipeline(
    "image-classification", model="trpakov/vit-face-expression"
)

MAX_ROSTOS = 5 # limite de rostos analisados por imagem

TRADUCAO = {
    "angry": "raiva",
    "disgust": "nojo",
    "fear": "medo",
    "happy": "feliz",
    "sad": "triste",
    "surprise": "surpresa",
    "neutral": "neutro",
}

# ------------------ Contrato de dados (Pydantic) ------------------
Emocao = Literal[
    "raiva", "nojo", "medo", "feliz", "triste", "surpresa", "neutro"
]
Polaridade = Literal["positivo", "negativo", "neutro"]

# Regra de negócio: fica no SERVIDOR, não no cliente
POLARIDADE: dict[str, str] = {
    "feliz": "positivo",
    "surpresa": "positivo",
    "raiva": "negativo",
    "nojo": "negativo",
    "medo": "negativo",
    "triste": "negativo",
    "neutro": "neutro",
}


class Rosto(BaseModel):  # um rosto encontrado na imagem
    emocao: Emocao
    confianca: float
    polaridade: Polaridade
    caixa: tuple[int, int, int, int]  # x, y, largura, altura do rosto


class Analise(BaseModel):
    encontrou_rosto: bool
    total_rostos: int
    rostos: list[Rosto]


class AvaliacaoEntrada(BaseModel):
    emocao: Emocao
    confianca: float = Field(ge=0, le=1)


class Avaliacao(AvaliacaoEntrada):
    id: int
    polaridade: Polaridade
    data_hora: datetime

avaliacoes: list[Avaliacao] = [] # "banco de dados" em memória"

# Cria uma avaliação e guarda na lista 
def guardar(dados: AvaliacaoEntrada) -> Avaliacao:
    nova = Avaliacao(
        id=len(avaliacoes) + 1,
        polaridade=POLARIDADE[dados.emocao],
        data_hora=datetime.now(),
        **dados.model_dump(),
    )
    avaliacoes.append(nova)
    return nova

# ----------- Endpoints -----------
# Detecta todos os rostos e classifica cada um (a imagem não é salva)
@app.post("/analisar", response_model=Analise)
def analisar(imagem: UploadFile = File(...), registrar: bool = False):
    try: 
        foto = Image.open(io.BytesIO(imagem.file.read())).convert("RGB")
    except UnidentifiedImageError: 
        raise HTTPException(status_code=400, detail="O arquivo enviado não é uma imagem")

    cinza = cv2.cvtColor(np.array(foto), cv2.COLOR_RGB2GRAY)
    caixas = detector.detectMultiScale(cinza, scaleFactor=1.1, minNeighbors=5, minSize=(48, 48))
    caixas = sorted(caixas, key=lambda c: c[2] * c[3], reverse=True) [:MAX_ROSTOS]
    if len(caixas) == 0:
        return Analise(encontrou_rosto=False, total_rostos=0, rostos=[])

    caixas = [tuple(int(v) for v in c) for c in caixas]
    recortes = [foto.crop((x,y,x + w, y + h)) for x,y,w,h in caixas]
    previsoes = classificador(recortes) 

    rostos = []
    for caixa, previsao in zip(caixas, previsoes):
        melhor = previsao[0]
        emocao = TRADUCAO[melhor["label"].lower()]
        confianca = float(melhor["score"])
        rostos.append(Rosto(emocao=emocao, confianca=confianca, polaridade=POLARIDADE[emocao], caixa=caixa))

        if registrar: 
            guardar(AvaliacaoEntrada(emocao=emocao, confianca=confianca))
        return Analise(encontrou_rosto=True, total_rostos=len(rostos), rostos=rostos)


@app.post("/avaliacoes", response_model=Avaliacao, status_code=201)
def criar_avaliacao(dados: AvaliacaoEntrada):
    return guardar(dados)

@app.get("/avaliacoes", response_model=list[Avaliacao])
def listar(polaridade: Polaridade | None = None):
    if polaridade:
        return [a for a in avaliacoes if a.polaridade == polaridade]
    return avaliacoes

@app.get("/avaliacoes/{id}", response_model=Avaliacao)
def buscar(id: int):
    for a in avaliacoes:
        if a.id == id:
            return a
    raise HTTPException(status_code=404, detail="Avaliação não encontrada")

@app.get("/resumo")
def resumo():
    return {
        "total": len(avaliacoes),
        "polaridade": dict(Counter(a.polaridade for a in avaliacoes)),
        "emocoes": dict(Counter(a.emocao for a in avaliacoes)),
    }

@app.delete("/avaliacoes", status_code=204)
def limpar():
    avaliacoes.clear()

@app.get("/")
def raiz():
    return {"mensagem": "API no ar!"}
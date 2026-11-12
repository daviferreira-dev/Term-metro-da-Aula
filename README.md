# Termômetro da Aula

Analisa as expressões faciais dos alunos em sala (feliz, triste, raiva, medo, surpresa, neutro) e mostra um "termômetro" do clima da aula.

- `api.py` — API FastAPI que recebe imagens e devolve a emoção detectada.
- `app.py` — painel Streamlit com upload de imagem, exemplos e modo ao vivo por câmeras IP.
- `exemplos/` — imagens de teste.

## Como rodar

```bash
pip install -r requirements.txt
uvicorn api:app --port 8000   # terminal 1
streamlit run app.py          # terminal 2
```

Edite o dicionário `CAMERAS` em `app.py` com os IPs reais das câmeras.

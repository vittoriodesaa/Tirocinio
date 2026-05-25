"""
Punto di ingresso del backend.
Avvia con: python main.py   oppure   uvicorn main:app --reload
"""
from pipeline.api.app import app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

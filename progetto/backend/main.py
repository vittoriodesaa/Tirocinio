from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
import time
import uuid
import asyncio
from datetime import timedelta

from utils import (
    User, Token, fake_users_db, authenticate_user, ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token, get_current_active_user, init_db, get_db_connection,
    salva_stato_processo, recupera_stato_processo, aggiungi_log, notifica_completamento
)

app = FastAPI(title="API con Processi Asincroni, SQLite e JWT")

# Inizializzazione del database all'avvio dell'applicazione
init_db()

# Funzione che verrà eseguita in background
async def elaborazione_lunga(task_id: str, callback_url: str = None):
    """
    Simula un'elaborazione che richiede 5 minuti per completarsi.
    Aggiorna lo stato del task durante il processo e salva i log nel database.
    Alla fine, invia una notifica all'URL specificato (se fornito).
    
    Args:
        task_id (str): L'ID del task
        callback_url (str, optional): L'URL a cui inviare la notifica di completamento
    """
    # Impostiamo lo stato iniziale
    stato_iniziale = {
        "status": "in_progress",
        "progress": 0,
        "start_time": time.time()
    }
    
    # Salviamo lo stato iniziale nel database
    salva_stato_processo(task_id, stato_iniziale)
    aggiungi_log(task_id, "Processo avviato")
    
    # Invece di un semplice sleep, aggiorniamo lo stato progressivamente
    for i in range(1, 11):
        # Dormiamo per 30 secondi (5 minuti / 10 = 30 secondi)
        await asyncio.sleep(30)
        
        # Aggiorniamo lo stato con la percentuale di completamento
        progress = i * 10
        stato_aggiornato = {
            "status": "in_progress",
            "progress": progress,
            "message": f"Elaborazione al {progress}%",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Salviamo lo stato aggiornato nel database
        salva_stato_processo(task_id, stato_aggiornato)
        aggiungi_log(task_id, f"Progresso: {progress}%")
    
    # Calcoliamo il tempo totale impiegato
    elapsed_time = time.time() - stato_iniziale["start_time"]
    
    # Aggiorniamo lo stato finale
    stato_finale = {
        "status": "completed", 
        "progress": 100,
        "result": "Elaborazione completata con successo",
        "elapsed_time": f"{elapsed_time:.2f} secondi",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Salviamo lo stato finale nel database
    salva_stato_processo(task_id, stato_finale)
    aggiungi_log(task_id, f"Processo completato in {elapsed_time:.2f} secondi")
    
    # Se è stato fornito un URL di callback, invia una notifica di completamento
    if callback_url:
        notifica_completamento(task_id, callback_url)
        aggiungi_log(task_id, f"Tentativo di notifica inviato a: {callback_url}")

# Endpoint per l'autenticazione e il rilascio del token JWT
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Endpoint per ottenere un token JWT tramite username e password."""
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username o password non corretti",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Endpoint per avviare un processo asincrono (protetto da JWT)
@app.get("/avvia-processo/")
async def avvia_processo(
    background_tasks: BackgroundTasks,
    callback_url: str = None,
    current_user: User = Depends(get_current_active_user)
):
    """
    Endpoint per avviare un nuovo processo asincrono.
    Restituisce immediatamente un ID task mentre il processo continua in background.
    Richiede autenticazione JWT.
    
    Args:
        background_tasks: Gestore dei task in background di FastAPI
        callback_url (str, optional): URL a cui inviare una notifica al completamento
        current_user: L'utente autenticato attualmente
    
    Returns:
        dict: Informazioni sul processo avviato
    """
    # Genera un ID univoco per questo task
    task_id = str(uuid.uuid4())
    
    # Registra l'utente che ha avviato il processo
    aggiungi_log(task_id, f"Processo avviato dall'utente: {current_user.username}")
    
    # Se fornito un URL di callback, registralo
    if callback_url:
        aggiungi_log(task_id, f"URL di callback registrato: {callback_url}")
    
    # Pianifica la funzione da eseguire in background con l'URL di callback (se presente)
    background_tasks.add_task(elaborazione_lunga, task_id, callback_url)
    
    # Restituisce l'ID del task che il client può utilizzare per verificare lo stato
    return {
        "task_id": task_id, 
        "message": "Processo avviato in background",
        "check_status_url": f"/stato-processo/{task_id}",
        "callback_url": callback_url if callback_url else None,
        "user": current_user.username
    }

# Endpoint per controllare lo stato di un processo (protetto da JWT)
@app.get("/stato-processo/{task_id}")
async def controlla_stato(
    task_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Endpoint per controllare lo stato di un processo avviato in precedenza.
    Utilizza l'ID task per recuperare informazioni sullo stato attuale dal database.
    Richiede autenticazione JWT.
    """
    # Recupera lo stato dal database
    stato = recupera_stato_processo(task_id)
    
    if stato is None:
        return {"error": "Task non trovato"}
    
    # Registra l'accesso dell'utente
    aggiungi_log(task_id, f"Stato controllato dall'utente: {current_user.username}")
    
    # Restituisce lo stato attuale del task
    return stato

# Endpoint per ottenere i log di un processo (protetto da JWT)
@app.get("/log-processo/{task_id}")
async def ottieni_log(
    task_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Endpoint per ottenere tutti i log di un processo specifico.
    Richiede autenticazione JWT.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, messaggio FROM log WHERE processo_key = ? ORDER BY timestamp",
            (task_id,)
        )
        logs = cursor.fetchall()
        
        # Converti i risultati in lista di dizionari
        log_list = [{"timestamp": row["timestamp"], "messaggio": row["messaggio"]} for row in logs]
    
    # Registra l'accesso dell'utente
    aggiungi_log(task_id, f"Log controllati dall'utente: {current_user.username}")
    
    return {"task_id": task_id, "logs": log_list, "user": current_user.username}

# Endpoint per ottenere la lista di tutti i processi (protetto da JWT)
@app.get("/tutti-processi/")
async def lista_processi(current_user: User = Depends(get_current_active_user)):
    """
    Endpoint per ottenere la lista di tutti i processi e i loro stati.
    Richiede autenticazione JWT.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM processi")
        rows = cursor.fetchall()
        
        # Converti i risultati in dizionario
        processi = {row["key"]: json.loads(row["value"]) for row in rows}
    
    return {"tasks": processi, "user": current_user.username}

# Endpoint per verificare informazioni sull'utente corrente
@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """
    Endpoint per ottenere informazioni sull'utente attualmente autenticato.
    Richiede autenticazione JWT.
    """
    return current_user

# Per eseguire l'applicazione:
# uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

import time
import json
import sqlite3
from typing import Dict, Any, Optional
from contextlib import contextmanager
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# Configurazione JWT
SECRET_KEY = "una_chiave_segreta_molto_lunga_e_complessa_da_cambiare_in_produzione"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Configurazione per la criptografia delle password
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Configurazione del database SQLite
DATABASE_NAME = "processi_asincroni_new.db"

# Modelli per l'autenticazione
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

# Utenti di esempio (in un'applicazione reale, usare il database)
# La password è "password"
password_hash = pwd_context.hash("password")

fake_users_db = {
    "admin": {
        "username": "admin",
        "full_name": "Administrator",
        "email": "admin@example.com",
        "hashed_password": password_hash,
        "disabled": False,
    }
}

# Funzione per creare la connessione al database
@contextmanager
def get_db_connection():
    """Crea una connessione al database e la chiude automaticamente al termine."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row  # Per ottenere i risultati come dizionari
    try:
        yield conn
    finally:
        conn.close()

# Inizializzazione del database
def init_db():
    """Inizializza il database creando le tabelle necessarie se non esistono."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Creazione della tabella per i processi
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS processi (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        ''')
        
        # Creazione della tabella per i log
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_key TEXT,
            timestamp TEXT,
            messaggio TEXT,
            FOREIGN KEY (processo_key) REFERENCES processi (key)
        )
        ''')
        conn.commit()

# Funzioni di autenticazione
def verify_password(plain_password, hashed_password):
    """Verifica se la password in chiaro corrisponde alla password hashata."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Genera l'hash di una password."""
    return pwd_context.hash(password)

def get_user(db, username: str):
    """Ottiene un utente dal database di esempio."""
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

def authenticate_user(fake_db, username: str, password: str):
    """Autentica un utente verificando username e password."""
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crea un token JWT con i dati specificati e la scadenza."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Ottiene l'utente corrente dal token JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenziali non valide",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    """Verifica se l'utente corrente è attivo."""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Utente inattivo")
    return current_user

# Funzione per salvare lo stato del processo nel database
def salva_stato_processo(key: str, value: Dict[str, Any]):
    """Salva lo stato di un processo nel database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Controlla se esiste già un record con questa chiave
        cursor.execute("SELECT 1 FROM processi WHERE key = ?", (key,))
        exists = cursor.fetchone() is not None
        
        # Converte il dizionario in JSON
        value_json = json.dumps(value)
        
        if exists:
            # Aggiorna il record esistente
            cursor.execute("UPDATE processi SET value = ? WHERE key = ?", (value_json, key))
        else:
            # Inserisce un nuovo record
            cursor.execute("INSERT INTO processi (key, value) VALUES (?, ?)", (key, value_json))
        
        conn.commit()

# Funzione per recuperare lo stato di un processo dal database
def recupera_stato_processo(key: str) -> Dict[str, Any]:
    """Recupera lo stato di un processo dal database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM processi WHERE key = ?", (key,))
        result = cursor.fetchone()
        
        if result:
            # Converte il JSON in dizionario
            return json.loads(result["value"])
        else:
            return None

# Funzione per aggiungere un log al database
def aggiungi_log(key: str, messaggio: str):
    """Aggiunge un messaggio di log per un processo specifico."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Ottiene il timestamp corrente
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Inserisce il messaggio di log
        cursor.execute(
            "INSERT INTO log (processo_key, timestamp, messaggio) VALUES (?, ?, ?)",
            (key, timestamp, messaggio)
        )
        conn.commit()


import requests

def notifica_completamento(task_id: str, callback_url: str):
    """
    Invia una notifica di completamento a un endpoint specificato.
    
    Args:
        task_id (str): L'ID del task completato
        callback_url (str): L'URL a cui inviare la notifica POST
        
    Returns:
        dict: La risposta dal server o un messaggio di errore
    """
    try:
        # Recupera lo stato corrente del processo
        stato_processo = recupera_stato_processo(task_id)
        
        if stato_processo is None:
            return {"error": "Stato del processo non trovato"}
        
        # Crea il payload per la richiesta POST
        payload = {
            "task_id": task_id,
            "status": stato_processo
        }
        
        # Invia la richiesta POST all'URL specificato
        response = requests.post(callback_url, json=payload)
        
        # Registra il tentativo di notifica
        aggiungi_log(task_id, f"Notifica inviata a {callback_url}: stato {response.status_code}")
        
        # Verifica se la richiesta è andata a buon fine
        if response.status_code in range(200, 300):
            return {"success": True, "message": f"Notifica inviata con successo, stato: {response.status_code}"}
        else:
            return {"success": False, "message": f"Errore nell'invio della notifica, stato: {response.status_code}"}
            
    except requests.RequestException as e:
        # Registra l'errore
        aggiungi_log(task_id, f"Errore nell'invio della notifica: {str(e)}")
        return {"success": False, "error": str(e)}
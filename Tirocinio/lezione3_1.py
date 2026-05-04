from typing import TypedDict
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START,END

load_dotenv() #carico le chiavi
llm= ChatGroq(model="llama-3.1-8b-instant")    #inizializzo ia

class StatoTraduttore(TypedDict):
    frase_noiosa: str
    traduzione_tamarra: str

def traduci(stato:StatoTraduttore):
    frase=stato["frase_noiosa"]
    prompt=f"Traduci questa frase in Spagnolo ,sii molto informale:{frase}"
    risposta = llm.invoke(prompt)

    return {"traduzione_tamarra":risposta.content}


builder=StateGraph(StatoTraduttore)
builder.add_node("traduci",traduci)
builder.add_edge(START,"traduci")
builder.add_edge("traduci",END)

graph=builder.compile()


input_utente={"frase_noiosa": "quanto è divertente l'utilizzo dell'ia?"}
risultato=graph.invoke(input_utente)

print(risultato["traduzione_tamarra"])
from datetime import datetime
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END

load_dotenv()

llm=ChatGroq(model="llama-3.1-8b-instant")

def traduciOrario(stato:dict):
    adesso=datetime.now()
    ore=adesso.hour
    minuti=adesso.minute

    if ore <12 or (ore==12 and minuti==0):
        return "nodo_spa"
    else:
        return "nodo_fra"
    

def traduciSpagnolo(stato: dict):
    prompt=f"Traduci la seguente frase in spagnolo: {stato["frase_originale"]}"
    risposta=llm.invoke(prompt)
    return {"risultato":risposta.content}

def traduciFrancese(stato:dict):
    prompt=f"Traduci la seguente frase in francese: {stato["frase_originale"]}"
    risposta=llm.invoke(prompt)
    return{"risultato":risposta.content}

builder=StateGraph(dict)
builder.add_node("nodo_spa",traduciSpagnolo)
builder.add_node("nodo_fra",traduciFrancese)

builder.add_conditional_edges(START,traduciOrario)
builder.add_edge("nodo_spa",END)
builder.add_edge("nodo_fra",END)

graph=builder.compile()

input_utente={"frase_originale":"Il miglior gioco pokemon è pokemon platino"}

res=graph.invoke(input_utente)
print(res["risultato"])
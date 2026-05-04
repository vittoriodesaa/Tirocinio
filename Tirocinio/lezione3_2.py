from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import MessagesState, StateGraph, START,END

load_dotenv()

llm=ChatGroq(model="llama-3.1-8b-instant")

def traduci(stato: dict):
    frase=stato["frase_noiosa"]
    prompt=f"Traduci la seguente frase in spagnolo: {frase}"
    risposta=llm.invoke(prompt)

    return {"traduzione_tamarra": risposta.content}


grafo = StateGraph(dict)
grafo.add_node("traduci",traduci)

grafo.add_edge(START,"traduci")
grafo.add_edge("traduci",END)

grafo_finale=grafo.compile()

input_utente={"frase_noiosa":"Oggi mi annoio e non so cosa fare"}
ris=grafo_finale.invoke(input_utente)

print(ris["traduzione_tamarra"])
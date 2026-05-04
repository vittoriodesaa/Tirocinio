import os
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode,tools_condition


load_dotenv()
llm = ChatGroq(model="llama-3.1-8b-instant")
@tool

def creaPassword(password:str):
    """
    Usa questo tool per verificare la sicurezza di una password.
    n.b. (una password è sicura se: Ha almeno 8 caratteri E se ha almeno una maiuscola E
    se ha almeno un carattere speciale).
    Restituisci OK se è valida, altrimenti l'errore specifico che rende la password non sicura.
    """

    errori=[]
    if len(password)<8:
        errori.append("La password non è abbastanza lunga")

    if not any(char.isdigit() for char in password):
        errori.append("La password non ha numeri")
    if not any(char in "!*.#@%&^$" for char in password):
        errori.append("La password non contiene caratteri speciali")
    
    if errori:
        return f"Errore: La password è {','.join(errori)}"
    
    return "La password è corretta"


llmConTool=llm.bind_tools([creaPassword])

def nodo_ia(stato:MessagesState):
    messaggi=stato["messages"]
    risposta=llmConTool.invoke(messaggi)
    return {"messages":[risposta]}

nodo_strumenti=ToolNode(tools=[creaPassword])

grafo=StateGraph(MessagesState)

grafo.add_node("nodo_ia",nodo_ia)
grafo.add_node("tools",nodo_strumenti)

grafo.add_edge(START,"nodo_ia")
grafo.add_conditional_edges("nodo_ia",tools_condition)
grafo.add_edge("tools","nodo_ia")

# Creiamo lo schedario
memoria = MemorySaver()

# Diciamo al grafo di usare questo schedario
agente = grafo.compile(checkpointer=memoria)


if __name__ == "__main__":
    config = {"configurable": {"thread_id": "vittorio_01"}}
    richiesta = "Genera una password sicura"
    
    
    istruzioni_di_sistema = """Sei un generatore di password. 
    DEVI usare il tool creaPassword per generare e testare la password. 
    Non scrivere testo normale, chiama SOLO il tool."""

    risultato = agente.invoke({
        "messages": [
            ("system", istruzioni_di_sistema), 
            ("user", richiesta)
        ]
    }, config=config)
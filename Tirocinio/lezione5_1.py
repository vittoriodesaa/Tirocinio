from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from typing import Literal

load_dotenv()


llm = ChatGroq(model="llama-3.1-8b-instant")

@tool
def controlla_meteo(posizione: Literal["Sud", "Centro-Nord"]):
    """Usa questo tool per capire che tempo fa in base alla zona geografica (Sud o Centro-Nord)"""
    if posizione == "Sud":
        return "Soleggiato e caldo"
    else:
        return "Nuvoloso con possibili piogge"

llm_con_tool = llm.bind_tools([controlla_meteo])


def nodo_ia(stato: MessagesState):
    messaggi = stato["messages"]
    risposta = llm_con_tool.invoke(messaggi)
    return {"messages": [risposta]}


nodo_strumenti = ToolNode(tools=[controlla_meteo])

grafo = StateGraph(MessagesState)

grafo.add_node("cervello", nodo_ia)
grafo.add_node("manovale", nodo_strumenti)


grafo.add_edge(START, "cervello")
grafo.add_conditional_edges("cervello", tools_condition)
grafo.add_edge("manovale", END)


agente = grafo.compile()


if __name__ == "__main__":
    domanda_utente = "Domani sono a Milano, prendo l'ombrello?"
    risultato = agente.invoke({"messages": [("user", domanda_utente)]})
    print(risultato["messages"][-1].content)
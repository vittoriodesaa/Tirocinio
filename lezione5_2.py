import requests
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.tools import tool

from langgraph.graph import MessagesState, START,END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

load_dotenv()
llm = ChatGroq(model="llama-3.1-8b-instant")

@tool
def controlla_meteo(citta: str):
    """Usa questo tool il meteo attuale in una città. 
    Passa solo il nome della cità es: Milano,Roma,Napoli"""

    url = f"https://it.wttr.in/{citta}?format=%C+%t"
    risposta=requests.get(url)

    if risposta.status_code==200:
        return risposta.text
    else:
        return "Errore nel trovare il meteo dal server"
    
llmConTool=llm.bind_tools([controlla_meteo])

def nodo_ia(stato:MessagesState):
    messaggi=stato["messages"]
    risposta=llmConTool.invoke(messaggi)
    return {"messages":[risposta]}

nodo_strumenti= ToolNode(tools=[controlla_meteo])

grafo= StateGraph(MessagesState)

grafo.add_node("nodo_ia",nodo_ia)
grafo.add_node("tools",nodo_strumenti)

grafo.add_edge(START, "nodo_ia")
grafo.add_conditional_edges("nodo_ia",tools_condition)
grafo.add_edge("tools",END)

agente=grafo.compile()

if __name__== "__main__":
    domanda= "Com'è il meteo a Roma in questo momento? rispondi in italiano"
    risultato=agente.invoke({"messages":[("user",domanda)]})
    print(risultato["messages"][-1].content)
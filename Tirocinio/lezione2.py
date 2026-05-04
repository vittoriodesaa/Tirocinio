from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, MessagesState, START, END

# carico le chiavi
load_dotenv()

# inizializzo ai
llm = ChatGroq(model="llama-3.1-8b-instant")


def trolliamo(stato: MessagesState):
    risposta_vera = llm.invoke(stato['messages'])
    
    return {"messages": [risposta_vera]}


graph = StateGraph(MessagesState)
graph.add_node('trolliamo', trolliamo)
graph.add_edge(START, 'trolliamo')
graph.add_edge('trolliamo', END)


graph = graph.compile()


ris = graph.invoke({'messages': [{'role': 'user', 'content': 'Uè, spiegami cos è un agente in informatica in 25 parole'}]})

# print ultima frase detta dall'ia
print(ris['messages'][-1].content)
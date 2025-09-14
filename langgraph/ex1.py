from typing import TypedDict
from langgraph.graph import StateGraph
from langgraph.graph import START, END

# 1. 상태 정의
class State(TypedDict):
    message: str
    result: str

# 2. 노드 함수 정의
def process_node(state: State):
    return {"result": f"처리됨: {state['message']}"}

# 3. 그래프 생성
graph = StateGraph(State)
graph.add_node("process", process_node)
graph.add_edge(START, "process")
graph.add_edge("process", END)

# 4. 컴파일 및 실행
app = graph.compile()
result = app.invoke({"message": "Hello LangGraph"})
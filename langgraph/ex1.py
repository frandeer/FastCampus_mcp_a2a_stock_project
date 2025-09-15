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

# 그래프 구조를 ASCII로 출력
try:
    print("=== 그래프 구조 ===")
    print(app.get_graph().draw_ascii())
except:
    print("ASCII 출력 지원 안됨")

# 그래프를 mermaid 형식으로 출력 (다이어그램용)
try:
    print("\n=== Mermaid 다이어그램 ===")
    print(app.get_graph().draw_mermaid())

    print("\n=== 간단한 흐름도 ===")
    print("시작 → process → 끝")
except:
    print("Mermaid 출력 지원 안됨")

result = app.invoke({"message": "Hello LangGraph"})
print(f"\n=== 실행 결과 ===")
print(result)
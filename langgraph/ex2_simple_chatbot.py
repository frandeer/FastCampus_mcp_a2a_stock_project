from typing import TypedDict
from langgraph.graph import StateGraph
from langgraph.graph import START, END

# 1. 상태 정의 - 채팅봇이 기억할 정보들
class ChatState(TypedDict):
    user_input: str      # 사용자 입력
    bot_response: str    # 봇 응답
    conversation_count: int  # 대화 횟수

# 2. 노드 함수들 정의

def greet_user(state: ChatState):
    """사용자를 인사하는 노드"""
    user_msg = state['user_input'].lower()

    if '안녕' in user_msg or 'hello' in user_msg:
        response = "안녕하세요! 저는 간단한 챗봇입니다. 무엇을 도와드릴까요?"
    else:
        response = "반갑습니다! 어떤 도움이 필요하신가요?"

    return {
        "bot_response": response,
        "conversation_count": state.get('conversation_count', 0) + 1
    }

def process_question(state: ChatState):
    """질문을 처리하는 노드"""
    user_msg = state['user_input'].lower()

    if '날씨' in user_msg:
        response = "죄송하지만 실시간 날씨 정보는 제공할 수 없어요. 날씨앱을 확인해보세요!"
    elif '시간' in user_msg:
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        response = f"현재 시간은 {current_time} 입니다."
    elif '이름' in user_msg:
        response = "저는 LangGraph로 만든 간단한 챗봇이에요!"
    else:
        response = f"'{state['user_input']}'에 대해 잘 모르겠어요. 다른 질문을 해보세요!"

    return {
        "bot_response": response,
        "conversation_count": state.get('conversation_count', 0) + 1
    }

def farewell(state: ChatState):
    """작별 인사하는 노드"""
    response = f"대화해주셔서 감사합니다! 총 {state.get('conversation_count', 0)}번 대화했네요. 안녕히 가세요!"

    return {
        "bot_response": response,
        "conversation_count": state.get('conversation_count', 0) + 1
    }

# 3. 조건부 라우팅 함수
def decide_next_node(state: ChatState):
    """사용자 입력에 따라 다음 노드를 결정"""
    user_msg = state['user_input'].lower()

    if '안녕' in user_msg or 'hello' in user_msg or '처음' in user_msg:
        return "greet"
    elif '잘가' in user_msg or 'bye' in user_msg or '종료' in user_msg:
        return "farewell"
    else:
        return "question"

# 4. 그래프 생성
def create_chatbot():
    graph = StateGraph(ChatState)

    # 노드 추가
    graph.add_node("greet", greet_user)
    graph.add_node("question", process_question)
    graph.add_node("farewell", farewell)

    # 조건부 엣지 - 시작에서 상황에 따라 다른 노드로
    graph.add_conditional_edges(
        START,
        decide_next_node,
        {
            "greet": "greet",
            "question": "question",
            "farewell": "farewell"
        }
    )

    # 모든 노드에서 END로
    graph.add_edge("greet", END)
    graph.add_edge("question", END)
    graph.add_edge("farewell", END)

    return graph.compile()

# 5. 실행 및 테스트
if __name__ == "__main__":
    chatbot = create_chatbot()

    # 그래프 구조 출력
    print("=== 챗봇 그래프 구조 ===")
    print(chatbot.get_graph().draw_mermaid())

    print("\n=== 챗봇 테스트 ===")

    test_inputs = [
        "안녕하세요",
        "지금 몇 시야?",
        "오늘 날씨는?",
        "너의 이름은?",
        "파이썬이 뭐야?",
        "잘가!"
    ]

    for user_input in test_inputs:
        print(f"\n사용자: {user_input}")

        result = chatbot.invoke({
            "user_input": user_input,
            "conversation_count": 0
        })

        print(f"봇: {result['bot_response']}")
        print(f"대화 횟수: {result['conversation_count']}")
        print("-" * 50)
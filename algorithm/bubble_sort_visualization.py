import matplotlib.pyplot as plt
import matplotlib.animation as animation
import random

def bubble_sort(arr):
    n = len(arr)
    # 정렬 과정의 각 스텝을 저장할 리스트
    # 각 스텝은 리스트의 현재 상태를 나타냅니다.
    history = []
    # history에 (리스트 상태, 스왑된 인덱스 튜플) 형태로 저장
    history.append((list(arr), None)) # 초기 상태 저장, 스왑 없음

    for i in range(n):
        swapped_in_pass = False # 이번 pass에서 스왑이 있었는지 확인
        for j in range(0, n - i - 1):
            current_swapped_indices = None
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped_in_pass = True
                current_swapped_indices = (j, j + 1) # 스왑된 인덱스 기록
            history.append((list(arr), current_swapped_indices)) # 스왑 정보와 함께 상태 저장
        if not swapped_in_pass:
            break
    return history

def visualize_bubble_sort(arr):
    history = bubble_sort(arr.copy()) # 원본 arr을 변경하지 않도록 copy 사용

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_title("Bubble Sort Visualization")
    ax.set_xlabel("Index")
    ax.set_ylabel("Value")
    ax.set_xticks(range(len(arr)))
    ax.set_ylim(0, max(arr) * 1.1) # Y축 범위 설정

    bar_rects = ax.bar(range(len(arr)), history[0][0], color='skyblue')

    def update(frame):
        current_list, swapped_indices = history[frame]
        
        # 모든 막대의 색상을 기본으로 초기화
        for rect in bar_rects:
            rect.set_color('skyblue')

        # 현재 리스트 상태로 막대 높이 업데이트
        for rect, val in zip(bar_rects, current_list):
            rect.set_height(val)
        
        # 스왑된 요소들의 색상 변경
        if swapped_indices:
            idx1, idx2 = swapped_indices
            bar_rects[idx1].set_color('red') # 스왑되는 요소는 빨간색으로 표시
            bar_rects[idx2].set_color('red')
        
        return bar_rects

    ani = animation.FuncAnimation(fig, update, frames=len(history), blit=True, interval=200) # interval을 늘려 애니메이션 속도 조절
    plt.show()

if __name__ == "__main__":
    # 무작위 숫자 리스트 생성
    data = random.sample(range(1, 100), 30) # 더 많은 데이터로 테스트
    visualize_bubble_sort(data)

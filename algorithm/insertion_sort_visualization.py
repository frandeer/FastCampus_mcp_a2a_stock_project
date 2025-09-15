import matplotlib.pyplot as plt
import matplotlib.animation as animation
import random

def insertion_sort(arr):
    n = len(arr)
    history = []
    history.append((list(arr), None, None)) # 초기 상태: (리스트, 현재 요소 인덱스, 이동 중인 요소 인덱스)

    for i in range(1, n):
        key = arr[i]
        j = i - 1
        
        # 현재 삽입될 요소와 그 위치를 기록
        history.append((list(arr), i, None)) # key가 될 요소 i 강조

        while j >= 0 and key < arr[j]:
            arr[j + 1] = arr[j]
            # 요소가 오른쪽으로 이동하는 것을 기록
            history.append((list(arr), i, j + 1)) # key_index, moved_index
            j -= 1
        arr[j + 1] = key
        # key가 최종 위치에 삽입된 후 상태 기록
        history.append((list(arr), j + 1, None)) # 최종 삽입 위치 강조
    return history

def visualize_insertion_sort(arr):
    history = insertion_sort(arr.copy())

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_title("Insertion Sort Visualization")
    ax.set_xlabel("Index")
    ax.set_ylabel("Value")
    ax.set_xticks(range(len(arr)))
    ax.set_ylim(0, max(arr) * 1.1)

    bar_rects = ax.bar(range(len(arr)), history[0][0], color='skyblue')

    def update(frame):
        current_list, key_idx, moved_idx = history[frame]
        
        # 모든 막대의 색상을 기본으로 초기화
        for i, rect in enumerate(bar_rects):
            rect.set_color('skyblue')
            rect.set_height(current_list[i])
        
        # 현재 삽입될 요소 또는 이동 중인 요소 강조
        if key_idx is not None:
            bar_rects[key_idx].set_color('red') # 현재 삽입될 요소 (key) 또는 그 최종 위치
        if moved_idx is not None:
            bar_rects[moved_idx].set_color('orange') # 오른쪽으로 이동하는 요소
        
        return bar_rects

    ani = animation.FuncAnimation(fig, update, frames=len(history), blit=True, interval=250)
    plt.show()

if __name__ == "__main__":
    data = random.sample(range(1, 100), 25)
    visualize_insertion_sort(data)

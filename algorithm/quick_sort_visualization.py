import matplotlib.pyplot as plt
import matplotlib.animation as animation
import random

def quick_sort_recursive(arr, low, high, history):
    if low < high:
        pi, pivot_val, swapped_indices, compare_indices = partition(arr, low, high, history)
        history.append((list(arr), low, high, pi, pivot_val, swapped_indices, compare_indices, None, "partition_done")) # highlight_indices 추가
        quick_sort_recursive(arr, low, pi - 1, history)
        quick_sort_recursive(arr, pi + 1, high, history)

def partition(arr, low, high, history):
    pivot = arr[high]
    pivot_val = pivot
    i = (low - 1)
    
    # 파티션 시작 상태 기록
    history.append((list(arr), low, high, high, pivot_val, None, None, None, "start_partition"))

    swapped_indices = None
    compare_indices = None
    highlight_indices = None # 스왑 직전 강조할 인덱스

    for j in range(low, high):
        compare_indices = (j, high) # 현재 비교하는 요소와 피벗 강조
        history.append((list(arr), low, high, high, pivot_val, swapped_indices, compare_indices, highlight_indices, "comparing"))

        if arr[j] <= pivot:
            i = i + 1
            # 스왑 직전 상태 기록 (노란색으로 강조)
            highlight_indices = (i, j)
            history.append((list(arr), low, high, high, pivot_val, None, compare_indices, highlight_indices, "pre_swap"))
            highlight_indices = None # 다음 스텝에서는 해제

            arr[i], arr[j] = arr[j], arr[i]
            swapped_indices = (i, j) # 스왑된 인덱스 기록 (빨간색으로 강조)
            history.append((list(arr), low, high, high, pivot_val, swapped_indices, compare_indices, highlight_indices, "swapped"))
            swapped_indices = None # 다음 스텝에서는 스왑 하이라이트 해제

    # 피벗의 최종 위치에 스왑되기 직전 상태 기록
    highlight_indices = (i + 1, high)
    history.append((list(arr), low, high, high, pivot_val, None, compare_indices, highlight_indices, "pre_pivot_place"))
    highlight_indices = None # 다음 스텝에서는 해제

    arr[i + 1], arr[high] = arr[high], arr[i + 1]
    swapped_indices = (i + 1, high) # 피벗 최종 위치 스왑 기록
    history.append((list(arr), low, high, high, pivot_val, swapped_indices, compare_indices, highlight_indices, "pivot_placed"))

    return i + 1, pivot_val, swapped_indices, compare_indices

def quick_sort(arr):
    history = []
    # history entries will be: (current_list, low, high, pivot_idx, pivot_val, swapped_indices, compare_indices, highlight_indices, state)
    quick_sort_recursive(arr, 0, len(arr) - 1, history)
    return history

def visualize_quick_sort(arr):
    history = quick_sort(arr.copy())

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_title("Quick Sort Visualization")
    ax.set_xlabel("Index")
    ax.set_ylabel("Value")
    ax.set_xticks(range(len(arr)))
    ax.set_ylim(0, max(arr) * 1.1)

    bar_rects = ax.bar(range(len(arr)), history[0][0], color='lightgray') # 초기 색상 lightgray

    # 현재 상태를 표시할 텍스트 추가
    state_text = ax.text(0.02, 0.95, '', transform=ax.transAxes, fontsize=12, verticalalignment='top')

    def update(frame):
        current_list, low, high, pivot_idx, pivot_val, swapped_indices, compare_indices, highlight_indices, state = history[frame]
        
        # 모든 막대의 색상을 기본으로 초기화
        for i, rect in enumerate(bar_rects):
            rect.set_color('lightgray') # 기본 색상을 lightgray로 설정
            if low <= i <= high: # 현재 처리 중인 서브 배열
                rect.set_color('skyblue') # 처리 중인 서브 배열은 skyblue
            
            rect.set_height(current_list[i])
        
        # 피벗 강조
        if pivot_idx is not None and low <= pivot_idx <= high: # 현재 서브 배열 내의 피벗만 강조
            bar_rects[pivot_idx].set_color('purple')
        
        # 현재 비교 중인 요소 강조
        if compare_indices:
            idx1, idx2 = compare_indices
            if low <= idx1 <= high: 
                bar_rects[idx1].set_color('green')
            if low <= idx2 <= high: 
                bar_rects[idx2].set_color('green')

        # 스왑 직전 강조 (노란색)
        if highlight_indices:
            idx1, idx2 = highlight_indices
            if low <= idx1 <= high: 
                bar_rects[idx1].set_color('yellow')
            if low <= idx2 <= high: 
                bar_rects[idx2].set_color('yellow')

        # 스왑된 요소 강조 (빨간색)
        if swapped_indices:
            idx1, idx2 = swapped_indices
            if low <= idx1 <= high: 
                bar_rects[idx1].set_color('red')
            if low <= idx2 <= high: 
                bar_rects[idx2].set_color('red')
        
        # 마지막으로 정렬이 완료된 피벗 위치는 다른 색상으로 고정
        if state == "pivot_placed" and pivot_idx is not None:
            bar_rects[pivot_idx].set_color('darkgreen')

        # 전체 정렬 완료 후 모든 막대를 정렬 완료 색상으로 변경
        if frame == len(history) - 1:
             for rect in bar_rects:
                 rect.set_color('orange')
             state_text.set_text("Sorting Complete!")
        else:
            # 텍스트 정보 업데이트
            text_info = f"Frame: {frame}/{len(history)-1}\n"
            text_info += f"Current Range: [{low}, {high}]\n"
            text_info += f"Pivot Value: {pivot_val} (at index {pivot_idx if pivot_idx is not None else 'N/A'})\n"
            
            if state == "start_partition":
                text_info += "Action: Partitioning started."
            elif state == "comparing":
                text_info += f"Action: Comparing index {compare_indices[0]} ({current_list[compare_indices[0]]}) with Pivot {pivot_val}"
            elif state == "pre_swap":
                text_info += f"Action: Preparing to swap index {highlight_indices[0]} and {highlight_indices[1]}"
            elif state == "swapped":
                text_info += f"Action: Swapped {swapped_indices[0]} ({current_list[swapped_indices[0]]}) and {swapped_indices[1]} ({current_list[swapped_indices[1]]})"
            elif state == "pre_pivot_place":
                 text_info += f"Action: Preparing to place Pivot {pivot_val} at index {highlight_indices[0]}"
            elif state == "pivot_placed":
                text_info += f"Action: Pivot {pivot_val} placed at final position {pivot_idx}. Partition complete."
            elif state == "partition_done":
                text_info += "Action: Recursively sorting sub-arrays."
            else:
                text_info += f"Action: {state}"
            state_text.set_text(text_info)

        return bar_rects, state_text

    ani = animation.FuncAnimation(fig, update, frames=len(history), blit=False, interval=200) # interval을 200ms로 조절
    plt.show()

if __name__ == "__main__":
    data = random.sample(range(1, 100), 15)
    visualize_quick_sort(data)

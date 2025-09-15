# O(n) time complexity
def print_list_elements(list):
    for element in list:
        print(element, end=" ")
    print()

# O(n^2) time complexity
def print_list_elements_squared(list):
    for element in list:
        for element in list:
            print(element, end=" ")
    print()


# 그래프로 그려보기 
# import matplotlib.pyplot as plt
# plt.xlabel("Time")
# plt.ylabel("Space")
# plt.title("Time Complexity")
# plt.legend()
# plt.show()


# vectors = plt.plot([1, 2, 3, 4])
# plt.legend(vectors, ["Vector"])

# plt.show()


# metrix = plt.plot([[1, 2, 3, 4], [5, 6, 7, 8]])
# plt.legend(metrix, ["Matrix"])
# plt.show()

# 복잡도 - O(log n)
def binary_search(list, target):
    left = 0
    right = len(list) - 1
    steps = [] # 탐색 과정에서 확인한 mid 인덱스를 저장할 리스트
    while left <= right:
        mid = (left + right) // 2
        steps.append(mid) # 현재 mid 인덱스 기록
        if list[mid] == target:
            return mid, steps # 인덱스와 탐색 단계 반환
        elif list[mid] < target:
            left = mid + 1
        else: # list[mid] > target
            right = mid - 1
    return -1, steps # 못 찾은 경우 -1과 탐색 단계 반환


# binary search 그래프로 그려보기
import matplotlib.pyplot as plt

# 예시 리스트와 목표 값 설정
test_list = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
target_value = 13

# binary_search 함수 실행
found_index, search_steps = binary_search(test_list, target_value)

plt.figure(figsize=(12, 7)) # 그래프 크기 설정

# 입력 리스트를 플롯 (인덱스 vs 값)
plt.plot(range(len(test_list)), test_list, 'o-', color='blue', label="Input List (Index vs Value)")

# 탐색 단계(중간 인덱스)를 플롯
# search_steps는 인덱스 리스트이므로, 해당 인덱스의 실제 값을 가져와서 플롯합니다.
plt.plot([step for step in search_steps], [test_list[step] for step in search_steps],
         'rx', markersize=10, markeredgewidth=2, label="Search Steps (Midpoints Checked)")

# 목표 값이 발견된 경우 해당 위치 표시
if found_index != -1:
    plt.plot(found_index, test_list[found_index], 'go', markersize=12,
             markeredgewidth=2, label=f"Target {target_value} Found at Index {found_index}")

plt.xlabel("Index")
plt.ylabel("Value")
plt.title(f"Binary Search Visualization for Target {target_value}")
plt.xticks(range(len(test_list))) # X축 눈금을 리스트 인덱스에 맞춤
plt.yticks(test_list) # Y축 눈금을 리스트 값에 맞춤
plt.grid(True)
plt.legend()
plt.show()

print(f"Target {target_value} found at index: {found_index}. Steps (mid-indices checked): {search_steps}")
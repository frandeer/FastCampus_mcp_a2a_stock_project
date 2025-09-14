# TODO(human) - Learning Examples 정리 작업

다음 작업들을 수행해주세요:

## 1. 중복 환경 파일 제거
```bash
rm learning_examples/.env
rm learning_examples/.env.example
```

## 2. 임시 파일 정리
```bash
find learning_examples/ -name "*.tmp" -delete
find learning_examples/ -name "*.bak" -delete
find learning_examples/ -name "*~" -delete
```

## 3. 각 step 폴더 점검
- step0_llm_basics/
- step1_basic_mcp/
- step2_langgraph_basics/
- step3_a2a_communication/
- step4_full_integration/

## 4. 불필요한 파일들 확인 및 제거
- 중복된 유틸리티 파일들
- 테스트 출력 파일들
- 임시 로그 파일들

## 5. README.md 업데이트
환경 설정 부분을 루트 디렉토리 파일을 참조하도록 수정

## 6. 프로젝트 구조 개선안
- learning_examples/ → examples/ (더 간결한 이름)
- 각 step별로 독립적인 환경이 아닌 공통 환경 사용
- 불필요한 중복 제거
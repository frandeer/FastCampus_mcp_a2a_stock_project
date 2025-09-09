"""
공통 유틸리티 - 환경변수 로딩 및 설정 관리

모든 학습 예제에서 공통으로 사용하는 유틸리티들을 제공합니다.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

class EnvironmentManager:
    """환경변수 관리 클래스"""
    
    def __init__(self, env_file: Optional[str] = None):
        """
        환경변수 매니저 초기화
        
        Args:
            env_file: .env 파일 경로. None이면 자동으로 찾기
        """
        self.loaded = False
        self.env_file = env_file
        self.load_environment()
    
    def load_environment(self):
        """환경변수 로딩"""
        if self.loaded:
            return
            
        # .env 파일 경로 결정
        if self.env_file:
            env_path = Path(self.env_file)
        else:
            # 현재 디렉토리부터 상위로 올라가면서 .env 파일 찾기
            current_dir = Path.cwd()
            env_path = None
            
            # learning_examples 디렉토리부터 시작
            search_paths = [
                current_dir / '.env',
                current_dir / 'learning_examples' / '.env',
                current_dir.parent / '.env',
                Path(__file__).parent / '.env',
            ]
            
            for path in search_paths:
                if path.exists():
                    env_path = path
                    break
        
        # .env 파일 로딩
        if env_path and env_path.exists():
            load_dotenv(env_path)
            print(f"✅ 환경변수 파일 로딩: {env_path}")
            self.loaded = True
        else:
            print("⚠️  .env 파일을 찾을 수 없습니다. 시스템 환경변수만 사용합니다.")
            self.loaded = True
    
    def get_api_key(self, key_name: str, required: bool = True) -> Optional[str]:
        """
        API 키 가져오기 (안전한 로깅 포함)
        
        Args:
            key_name: 환경변수 이름 (예: 'OPENAI_API_KEY')
            required: 필수 키인지 여부
            
        Returns:
            API 키 또는 None
        """
        api_key = os.getenv(key_name)
        
        if api_key:
            # 안전한 형태로 로깅 (앞 8자리 + ... + 뒤 4자리)
            if len(api_key) > 12:
                masked_key = f"{api_key[:8]}...{api_key[-4:]}"
            else:
                masked_key = "***"
            print(f"✅ {key_name}: {masked_key}")
            return api_key
        elif required:
            print(f"❌ {key_name}이(가) 설정되지 않았습니다!")
            print(f"💡 설정 방법:")
            print(f"   1. .env 파일에 {key_name}=your-key-here 추가")
            print(f"   2. 또는 export {key_name}=your-key-here")
            return None
        else:
            print(f"⚠️  {key_name} (선택사항): 설정되지 않음")
            return None
    
    def get_setting(self, key_name: str, default: Any = None, type_cast: type = str) -> Any:
        """
        일반 설정 값 가져오기
        
        Args:
            key_name: 환경변수 이름
            default: 기본값
            type_cast: 타입 변환 (str, int, bool 등)
            
        Returns:
            설정 값
        """
        value = os.getenv(key_name)
        
        if value is None:
            if default is not None:
                print(f"🔧 {key_name}: {default} (기본값)")
                return default
            else:
                return None
        
        # 타입 변환
        try:
            if type_cast == bool:
                # 불린 값 특별 처리
                converted_value = value.lower() in ('true', '1', 'yes', 'on')
            else:
                converted_value = type_cast(value)
                
            print(f"🔧 {key_name}: {converted_value}")
            return converted_value
            
        except (ValueError, TypeError) as e:
            print(f"⚠️  {key_name} 타입 변환 실패 ({e}). 문자열로 반환: {value}")
            return value
    
    def print_environment_status(self):
        """환경 설정 상태 출력"""
        print("=" * 50)
        print("🔧 환경 설정 상태")
        print("=" * 50)
        
        # 주요 API 키들 확인
        api_keys = [
            ('OPENAI_API_KEY', True),  # 필수
            ('TAVILY_API_KEY', False),  # 선택
            ('NAVER_CLIENT_ID', False),  # 선택
        ]
        
        for key_name, required in api_keys:
            self.get_api_key(key_name, required)
        
        # 설정값들 확인
        settings = [
            ('LEARNING_DEBUG_MODE', True, bool),
            ('LEARNING_API_DELAY', 1, int),
            ('LEARNING_MCP_PORT', 9000, int),
        ]
        
        for key_name, default, type_cast in settings:
            self.get_setting(key_name, default, type_cast)
        
        print("=" * 50)

# 전역 환경 매니저 인스턴스
_env_manager = None

def get_env_manager() -> EnvironmentManager:
    """환경 매니저 싱글턴 인스턴스 가져오기"""
    global _env_manager
    if _env_manager is None:
        _env_manager = EnvironmentManager()
    return _env_manager

def get_api_key(key_name: str, required: bool = True) -> Optional[str]:
    """편의 함수: API 키 가져오기"""
    return get_env_manager().get_api_key(key_name, required)

def get_setting(key_name: str, default: Any = None, type_cast: type = str) -> Any:
    """편의 함수: 설정값 가져오기"""
    return get_env_manager().get_setting(key_name, default, type_cast)

def print_environment_status():
    """편의 함수: 환경 설정 상태 출력"""
    get_env_manager().print_environment_status()

# 테스트용 함수
if __name__ == "__main__":
    print("🧪 환경변수 관리 테스트")
    print_environment_status()
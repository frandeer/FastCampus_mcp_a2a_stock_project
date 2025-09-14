# FastAPI Simplified Clean Architecture

A demonstration of simplified clean architecture using FastAPI with proper dependency injection, following best practices from the code-developer guidelines.

## Architecture Overview

This implementation demonstrates:

- **Dependency Injection Pattern**: Service container managing dependencies
- **Interface-Based Design**: Abstract base classes defining service contracts
- **Separation of Concerns**: Clear separation between API, business logic, and data layers
- **Error Handling**: Comprehensive error handling with proper HTTP status codes
- **OpenAPI Documentation**: Auto-generated API documentation with examples

## Project Structure

```
api/
├── main.py           # FastAPI application setup and configuration
├── dependencies.py   # Dependency injection container and service interfaces
├── routers.py        # API endpoint definitions with dependency injection
├── models.py         # Pydantic request/response models
├── __init__.py       # Package initialization
└── README.md         # This file
```

## API Endpoints

### Stock Analysis
- **POST** `/api/v1/analyze/{stock_code}` - Analyze a stock by symbol
  - Parameters: stock code (path), analysis options (body)
  - Returns: comprehensive stock analysis with recommendation

### Investment Management  
- **POST** `/api/v1/invest` - Execute an investment order
  - Parameters: investment details (body)
  - Returns: transaction details and execution status

### Portfolio Management
- **GET** `/api/v1/portfolio` - Get portfolio summary
  - Parameters: user_id, options (query)
  - Returns: complete portfolio overview with positions

### Health Check
- **GET** `/api/v1/health` - Service health status
- **GET** `/health` - Simple health check (not versioned)

## Key Features

### 1. Dependency Injection Container

```python
class DependencyContainer:
    """Service container managing all application dependencies"""
    
    async def startup(self) -> None:
        """Initialize all services with proper lifecycle management"""
        
    def get_stock_analysis_service(self) -> StockAnalysisService:
        """Get service instance with interface-based contract"""
```

### 2. Interface-Based Services

```python
class StockAnalysisService(ABC):
    """Abstract service interface defining contract"""
    
    @abstractmethod
    async def analyze_stock(self, stock_code: str) -> Dict[str, Any]:
        pass

class MockStockAnalysisService(StockAnalysisService):
    """Concrete implementation of service interface"""
```

### 3. Comprehensive Error Handling

- Input validation with detailed error messages
- Proper HTTP status codes (200, 201, 400, 404, 422, 500, 503)
- Standardized error response format
- Request tracking with unique IDs

### 4. OpenAPI Integration

- Comprehensive API documentation
- Request/response examples
- Parameter validation and descriptions
- Interactive documentation at `/docs` and `/redoc`

## Running the Application

### Prerequisites
```bash
# Install FastAPI and dependencies
pip install fastapi uvicorn pydantic
```

### Start the Server
```bash
# From the project root
cd simplified_architecture/api
python main.py

# Or using uvicorn directly
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Access Documentation
- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc
- **OpenAPI Schema**: http://127.0.0.1:8000/openapi.json

## Example Usage

### Analyze a Stock
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/analyze/AAPL" \
  -H "Content-Type: application/json" \
  -d '{
    "include_detailed_metrics": true,
    "analysis_period": "30d"
  }'
```

### Execute Investment
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/invest" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "AAPL",
    "amount": 1000.0,
    "strategy": "market"
  }'
```

### Get Portfolio Summary
```bash
curl "http://127.0.0.1:8000/api/v1/portfolio?user_id=user123&include_positions=true"
```

### Health Check
```bash
curl "http://127.0.0.1:8000/health"
```

## Architecture Benefits

1. **Testability**: Interface-based design enables easy mocking and unit testing
2. **Maintainability**: Clear separation of concerns and dependency injection
3. **Scalability**: Service container pattern supports easy service swapping
4. **Documentation**: Auto-generated OpenAPI docs with comprehensive examples
5. **Error Handling**: Consistent error responses with proper HTTP semantics
6. **Type Safety**: Pydantic models ensure runtime type validation

## Design Patterns Used

- **Dependency Injection**: Service container pattern for managing dependencies
- **Repository Pattern**: Service interfaces abstract data access
- **Factory Pattern**: Router and app creation functions
- **Strategy Pattern**: Different investment strategies (market, limit, etc.)
- **Result Pattern**: Standardized response format with success/error handling

This implementation follows the clean architecture principles while remaining simple and practical for FastAPI applications.
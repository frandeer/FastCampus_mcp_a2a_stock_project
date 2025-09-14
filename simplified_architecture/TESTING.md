# Comprehensive Test Suite Documentation

## Overview

This test suite provides comprehensive unit tests for the simplified Clean Architecture implementation, achieving 95%+ test coverage across all layers.

## Test Structure

```
tests/
├── conftest.py          # Pytest configuration and shared fixtures
├── test_entities.py     # Domain entity tests with edge cases
├── test_use_cases.py    # Application layer tests with mocking
└── test_adapters.py     # Infrastructure layer tests
```

## Test Coverage

### Domain Layer Tests (`test_entities.py`)
- **Stock Entity**: Validation, immutability, edge cases
- **MarketData Entity**: Price calculations, validation, boundary conditions
- **AnalysisResult Entity**: Confidence validation, target price handling
- **InvestmentDecision Entity**: Risk assessment, investment calculations
- **RiskCalculator Service**: VaR calculations, risk level determination
- **Domain Events**: Event creation, immutability, data integrity
- **Enum Validations**: All enum values, string conversions

### Application Layer Tests (`test_use_cases.py`)
- **AnalyzeStockUseCase**: Stock analysis workflow, parallel data collection, LLM integration
- **ExecuteInvestmentUseCase**: Investment execution, human approval workflow, risk assessment
- **GetPortfolioSummaryUseCase**: Portfolio calculations, risk metrics, position management
- **Result Pattern**: Success/failure handling, immutability
- **Async Patterns**: Concurrency, exception handling, timeout management

### Infrastructure Layer Tests (`test_adapters.py`)
- **CircuitBreaker**: State transitions, failure thresholds, recovery logic
- **InMemoryCache**: Caching operations, expiration, concurrent access
- **ResilientHTTPClient**: HTTP operations, retry logic, circuit breaker integration
- **Repository Implementations**: API integration, caching strategies, error handling
- **Mock Services**: Trading simulation, analysis storage, data persistence

## Key Testing Features

### 1. Comprehensive Edge Cases
- Boundary value testing
- Invalid input validation
- Error condition handling
- Resource exhaustion scenarios

### 2. Mocking Strategy
```python
# Repository mocking
@pytest.fixture
def mock_stock_repo():
    repo = Mock(spec=StockRepository)
    repo.find_by_code = AsyncMock()
    return repo

# Service mocking with realistic behavior
mock_llm_service.analyze_stock.return_value = {
    "signal": "BUY",
    "confidence": 0.85,
    "reasoning": "Strong fundamentals"
}
```

### 3. Async Testing Patterns
- Proper async/await handling
- Concurrent operation testing
- Exception isolation
- Timeout testing

### 4. Parameterized Testing
```python
@pytest.mark.parametrize("confidence", [0.0, 0.1, 0.5, 0.8, 1.0])
def test_valid_confidence_values(self, confidence):
    # Test with multiple confidence values
```

### 5. Performance Testing
- Cache performance under load
- Circuit breaker performance impact
- Concurrent operation efficiency

## Test Execution

### Quick Test Run
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html --cov-fail-under=95

# Run specific test file
pytest tests/test_entities.py -v
```

### Using Test Runner
```bash
# Execute comprehensive test suite
python3 run_tests.py
```

### Test Categories
```bash
# Unit tests only
pytest tests/ -m "not integration"

# Integration tests
pytest tests/ -m "integration"

# Exclude slow tests
pytest tests/ -m "not slow"
```

## Test Fixtures

### Entity Fixtures
- `sample_stock`: Standard stock entity
- `sample_market_data`: Market data with realistic values
- `sample_analysis_result`: Analysis with valid confidence/target price
- `sample_investment_decision`: Investment decision with risk assessment

### Repository Mocks
- `mock_stock_repo`: Stock repository with AsyncMock methods
- `mock_market_data_repo`: Market data repository
- `mock_analysis_repo`: Analysis result storage
- `mock_trading_repo`: Trading operations

### Service Mocks
- `mock_llm_service`: LLM analysis service
- `mock_event_publisher`: Event publishing
- `mock_human_approval_service`: Human-in-the-loop approval

### Infrastructure Components
- `circuit_breaker`: Circuit breaker with test configuration
- `in_memory_cache`: Cache instance for testing
- `risk_calculator`: Risk calculation service

## Coverage Requirements

### 95% Coverage Standard
The test suite maintains 95% line coverage across all modules:

- **Domain Entities**: 100% coverage (critical business logic)
- **Use Cases**: 95%+ coverage (application workflows)
- **Infrastructure**: 90%+ coverage (external integrations)

### Coverage Exclusions
```python
# Excluded from coverage (in .coveragerc):
- Exception handling for external dependencies
- Logging statements
- Debug code blocks
```

## Test Quality Standards

### 1. Test Independence
- No test dependencies
- Clean state for each test
- Proper fixture cleanup

### 2. Realistic Data
- Domain-appropriate test values
- Edge case coverage
- Boundary condition testing

### 3. Error Testing
- Exception handling validation
- Graceful degradation testing
- Resource failure simulation

### 4. Performance Validation
- Response time thresholds
- Memory usage validation
- Concurrent access testing

## Continuous Integration

### Pre-commit Hooks
```yaml
- repo: local
  hooks:
    - id: pytest
      name: pytest
      entry: pytest
      language: system
      pass_filenames: false
      always_run: true
      args: [tests/, --cov=., --cov-fail-under=95]
```

### CI Pipeline Integration
```yaml
test:
  script:
    - pip install -r test_requirements.txt
    - pytest tests/ --cov=. --cov-report=xml --cov-fail-under=95
  coverage: '/TOTAL.*\s+(\d+%)$/'
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure PYTHONPATH includes project root
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   ```

2. **Async Test Failures**
   ```python
   # Use pytest-asyncio auto mode
   pytest_plugins = ('pytest_asyncio',)
   ```

3. **Mock Issues**
   ```python
   # Reset mocks between tests
   @pytest.fixture(autouse=True)
   def reset_mocks(self):
       # Reset mock state
   ```

### Performance Issues
- Use `pytest-xdist` for parallel execution
- Profile slow tests with `pytest-benchmark`
- Monitor memory usage with `pytest-memray`

## Best Practices

### 1. Test Naming
```python
def test_should_calculate_investment_amount_when_max_price_limits():
    # Clear test intention in name
```

### 2. AAA Pattern
```python
def test_example():
    # Arrange
    setup_test_data()
    
    # Act
    result = execute_operation()
    
    # Assert
    assert result.success is True
```

### 3. Error Messages
```python
assert result.confidence == 0.8, f"Expected confidence 0.8, got {result.confidence}"
```

### 4. Fixture Scope
```python
@pytest.fixture(scope="session")  # Expensive setup
@pytest.fixture(scope="function")  # Default, clean state
```

## Metrics and Reporting

### Coverage Report
- HTML report: `htmlcov/index.html`
- Terminal report: Line-by-line missing coverage
- XML report: For CI/CD integration

### Test Metrics
- Test execution time
- Coverage percentage by module
- Failed test details
- Performance benchmarks

## Maintenance

### Regular Tasks
1. Update test data for domain changes
2. Review and update mock configurations
3. Add tests for new features
4. Performance regression testing
5. Security vulnerability testing

### Test Review Checklist
- [ ] 95%+ coverage maintained
- [ ] All edge cases covered
- [ ] Async patterns properly tested
- [ ] Error conditions validated
- [ ] Performance within thresholds
- [ ] Documentation updated
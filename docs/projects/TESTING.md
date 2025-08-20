# Testing TODO - Target: 75% Coverage

## Current Status
- **Current Coverage**: 50.67% (2395/4727 lines)
- **Target Coverage**: 75% (3545 lines needed)
- **Gap to Close**: 1150 lines of additional coverage needed

## Critical Issues Blocking Coverage

### 1. API Handler Import Errors (0% coverage - ~500 lines)
**BLOCKER**: All handler files have incorrect imports preventing module loading
- [ ] Fix `src/api/handlers/information.py` - Change `WhoRequestPacket` → `WhoPacket`
- [ ] Fix `src/api/handlers/information.py` - Change `FingerRequestPacket` → `FingerPacket`  
- [ ] Fix `src/api/handlers/information.py` - Change `LocateRequestPacket` → `LocatePacket`
- [ ] Fix `src/api/handlers/channels.py` - Verify all packet imports match actual packet classes
- [ ] Fix `src/api/handlers/admin.py` - Verify all packet imports match actual packet classes
- [ ] Write tests for CommunicationHandler methods (tell, emoteto, channel_send, channel_emote)
- [ ] Write tests for InformationHandler methods (who, finger, locate, mudlist)
- [ ] Write tests for ChannelHandler methods (join, leave, list, who, history)
- [ ] Write tests for AdministrativeHandler methods (ping, status, stats, reconnect)

### 2. Utility Module Tests (0% coverage - ~650 lines)
- [ ] Write tests for `src/utils/circuit_breaker.py` (175 lines)
  - [ ] Test circuit state transitions (CLOSED → OPEN → HALF_OPEN)
  - [ ] Test failure threshold tracking
  - [ ] Test automatic recovery
  - [ ] Test decorator functionality
- [ ] Write tests for `src/utils/retry.py` (191 lines)
  - [ ] Test exponential backoff strategy
  - [ ] Test linear backoff strategy
  - [ ] Test fibonacci backoff strategy
  - [ ] Test decorrelated jitter
  - [ ] Test retry policy enforcement
- [ ] Write tests for `src/network/connection_pool.py` (289 lines)
  - [ ] Test pool initialization
  - [ ] Test connection acquisition/release
  - [ ] Test connection health checking
  - [ ] Test idle timeout
  - [ ] Test pool expansion/contraction

### 3. Fix Failing API Tests (51 failures)
- [ ] Fix `test_queue.py` - MessageQueueManager tests need proper mocks
- [ ] Fix `test_server.py` - WebSocket authentication tests need async fixtures
- [ ] Fix `test_session.py` - SessionManager.auth attribute missing
- [ ] Fix `test_subscriptions.py` - SubscriptionManager.subscriptions attribute

### 4. Integration Test Fixes
- [ ] Mock I3 router connections to prevent timeouts
- [ ] Add fixtures for gateway mock in integration tests
- [ ] Fix async test event loop management
- [ ] Add connection pool mocks

### 5. Performance Test Fixes  
- [ ] Add resource limits to prevent hanging
- [ ] Mock heavy operations in stress tests
- [ ] Add timeout decorators to all performance tests

## Plan to Achieve 75% Coverage

### Phase 1: Quick Wins (Days 1-2)
**Expected Coverage Gain: +10% → 60%**

1. Fix all handler import errors (30 min)
2. Run tests with real handlers loaded (+500 lines coverage)
3. Fix remaining 51 failing API tests
4. Verify all fixed tests pass

### Phase 2: Utility Tests (Days 3-4)  
**Expected Coverage Gain: +13% → 73%**

1. Write circuit_breaker tests (+175 lines)
2. Write retry mechanism tests (+191 lines)
3. Write connection_pool tests (+289 lines)

### Phase 3: Integration Improvements (Day 5)
**Expected Coverage Gain: +2% → 75%**

1. Mock external connections in integration tests
2. Fix async test fixtures
3. Enable performance tests with mocks

## Test Implementation Priority

### HIGH PRIORITY (Must Complete)
1. Fix handler imports - **Immediate**
2. Write circuit_breaker tests
3. Write retry tests
4. Fix queue manager tests

### MEDIUM PRIORITY (Should Complete)
1. Write connection_pool tests
2. Fix WebSocket async tests
3. Mock integration test connections
4. Fix session manager tests

### LOW PRIORITY (Nice to Have)
1. Performance test improvements
2. Additional edge case tests
3. Security test expansions

## Specific Test Files to Create/Fix

### New Test Files Needed
- [ ] `tests/unit/utils/test_circuit_breaker.py`
- [ ] `tests/unit/utils/test_retry.py`
- [ ] `tests/unit/network/test_connection_pool.py`

### Existing Tests to Fix
- [ ] `tests/unit/api/test_queue.py` - 13 failures
- [ ] `tests/unit/api/test_server.py` - 10 failures
- [ ] `tests/unit/api/test_session.py` - 2 failures
- [ ] `tests/unit/api/test_subscriptions.py` - 1 failure

## Commands to Run

```bash
# After fixing handler imports
./venv/bin/python -m pytest tests/unit/api/test_handlers.py --cov=src/api/handlers -v

# After writing utility tests
./venv/bin/python -m pytest tests/unit/utils/ --cov=src/utils -v

# Check overall coverage progress
./venv/bin/python -m pytest tests/ --cov=src --cov-report=term-missing

# Generate HTML report
./venv/bin/python -m pytest tests/ --cov=src --cov-report=html
```

## Success Criteria
- [ ] Overall test coverage ≥ 75%
- [ ] All handler modules can be imported
- [ ] Zero failing tests in unit test suite
- [ ] Integration tests run without timeouts
- [ ] Coverage report shows no 0% modules in critical paths
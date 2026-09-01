import pytest
from sqlalchemy import select
from backend.execution.paper_engine import paper_engine
from backend.db.session import init_db, async_session_factory, commit_with_retry
from backend.db.models import AccountBalance

@pytest.mark.asyncio
async def test_paper_execution_cycle():
    await init_db()
    
    # Ensure test environment has sufficient test cash
    async with async_session_factory() as session:
        acc_res = await session.execute(select(AccountBalance))
        acc = acc_res.scalars().first()
        if acc:
            acc.cash = 1000.0
            await commit_with_retry(session)
    
    # 1. Check account balance
    summary = await paper_engine.get_account_summary()
    assert summary["cash"] >= 100.0
    assert summary["total_equity"] > 0
    
    # 2. Execute BUY order
    buy_res = await paper_engine.execute_order(
        symbol="TEST_UNIT",
        side="BUY",
        qty=0.5,
        current_price=50.0,
        reason="Unit Test Buy",
        catalyst="TEST_CATALYST"
    )
    assert buy_res["success"] is True
    assert buy_res["fill_price"] > 50.0 # Slippage test
    
    # 3. Check updated position
    updated_summary = await paper_engine.get_account_summary()
    assert updated_summary["open_positions_count"] >= 1
    
    # 4. Execute SELL order
    sell_res = await paper_engine.execute_order(
        symbol="TEST_UNIT",
        side="SELL",
        qty=0.5,
        current_price=55.0,
        reason="Unit Test Profit Sell"
    )
    assert sell_res["success"] is True
    assert sell_res["fill_price"] < 55.0 # Slippage test

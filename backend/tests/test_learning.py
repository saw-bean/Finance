import pytest
from starlette.testclient import TestClient
from backend.main import app
from backend.db.session import init_db, async_session_factory, commit_with_retry
from backend.db.models import Trade, TradeReflection, CatalystPerformance
from backend.agents.learning_agent import learning_agent

@pytest.mark.asyncio
async def test_learning_reflection_and_catalyst_calibration():
    await init_db()
    
    # 1. Insert a sample closed BUY + SELL trade pair
    async with async_session_factory() as session:
        buy_trade = Trade(
            symbol="TEST_LEARN",
            side="BUY",
            qty=10.0,
            price=50.0,
            slippage=0.1,
            commission=0.05,
            total_cost=500.15,
            realized_pnl=0.0,
            reason="CIO Synthesis: Form 4 Insider Accumulation (Conf: 85%)",
            broker="SIMULATED_PAPER"
        )
        session.add(buy_trade)
        
        sell_trade = Trade(
            symbol="TEST_LEARN",
            side="SELL",
            qty=10.0,
            price=55.0,
            slippage=0.1,
            commission=0.05,
            total_cost=549.85,
            realized_pnl=49.7,
            reason="CIO Exit: Form 4 Profit Target Reached",
            broker="SIMULATED_PAPER"
        )
        session.add(sell_trade)
        await commit_with_retry(session)

    # 2. Run Learning Agent iteration
    await learning_agent.run_iteration()
    
    # 3. Verify that TradeReflection was created
    async with async_session_factory() as session:
        from sqlalchemy import select
        res = await session.execute(select(TradeReflection).where(TradeReflection.symbol == "TEST_LEARN"))
        reflection = res.scalars().first()
        assert reflection is not None
        assert reflection.outcome == "WIN"
        assert reflection.realized_pnl == 49.7
        assert reflection.catalyst == "SEC_FORM4_CLUSTER_BUY"
        assert "Profitable exit" in reflection.reflection_summary

@pytest.mark.asyncio
async def test_learning_and_holdings_api_endpoints():
    await init_db()
    with TestClient(app) as client:
        # Test /api/learning/performance
        perf_res = client.get("/api/learning/performance")
        assert perf_res.status_code == 200
        perfs = perf_res.json()
        assert isinstance(perfs, list)
        assert len(perfs) >= 1
        assert "win_rate" in perfs[0]
        assert "calibrated_weight" in perfs[0]

        # Test /api/learning/reflections
        refl_res = client.get("/api/learning/reflections")
        assert refl_res.status_code == 200
        reflections = refl_res.json()
        assert isinstance(reflections, list)

        # Test /api/portfolio/holdings-summary
        holdings_res = client.get("/api/portfolio/holdings-summary")
        assert holdings_res.status_code == 200
        holdings = holdings_res.json()
        assert isinstance(holdings, list)

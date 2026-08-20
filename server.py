"""
server.py
FastAPI Server & WebSocket Backend for BSE Sensex Options Simulation Dashboard.
"""

import asyncio
import os
import json
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import SystemConfig, default_config
from main import SensexSimulationSystem
from data_feed import SimulatedLiveFeedAdapter, HistoricalCSVFeedAdapter, AngelOneFeedAdapter
from simulation_runner import create_sample_dataset

app = FastAPI(title="BSE Sensex Options Simulation System v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Simulation System State with Angel One SmartAPI feed
def create_initial_feed():
    try:
        return AngelOneFeedAdapter(
            api_key=default_config.angelone_api_key,
            client_code=default_config.angelone_client_code,
            pin=default_config.angelone_pin,
            totp_secret=default_config.angelone_totp_secret
        )
    except Exception as e:
        print(f"Fallback to simulated feed: {e}")
        return SimulatedLiveFeedAdapter()

system = SensexSimulationSystem(feed_adapter=create_initial_feed())
is_auto_running = True
tick_speed_seconds = 1.0

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect(dead)

manager = ConnectionManager()

class ConfigUpdateRequest(BaseModel):
    stop_loss_points: float = 50.0
    target_points: float = 100.0
    trail_trigger_points: float = 25.0
    trail_lock_points: float = 15.0
    enable_trailing_sl: bool = True
    max_trades_per_day: int = 5
    lot_size: int = 65
    auto_schedule: bool = True
    confirmation_candles: Optional[int] = 1
    min_holding_updates: Optional[int] = 3
    strike_distance_points: Optional[int] = 200

@app.get("/api/state")
async def get_system_state():
    summary = system.portfolio_manager.get_summary()
    trade_history = system.portfolio_manager.get_trade_history()
    latest_tick = system.process_market_update()
    return {
        "active_trade": system.simulation_engine.active_trade,
        "portfolio_summary": summary,
        "trade_history": trade_history,
        "trade_manager": system.trade_manager.get_state(),
        "config": system.config.to_dict(),
        "is_auto_running": is_auto_running,
        "tick_speed_seconds": tick_speed_seconds,
        "latest_tick": latest_tick,
        "option_quotes": latest_tick.get("option_quotes", {}),
        "market_open": latest_tick.get("market_open", True),
        "market_status": latest_tick.get("market_status", "OPEN")
    }

@app.post("/api/step")
async def step_simulation():
    system.feed_adapter.step()
    tick_result = system.process_market_update()
    await manager.broadcast({
        "type": "TICK_UPDATE",
        "data": tick_result
    })
    return tick_result

@app.post("/api/toggle_auto")
async def toggle_auto(enable: bool, speed: float = 1.0):
    global is_auto_running, tick_speed_seconds
    is_auto_running = enable
    tick_speed_seconds = max(0.05, speed)
    return {"is_auto_running": is_auto_running, "tick_speed_seconds": tick_speed_seconds}

@app.post("/api/reset")
async def reset_simulation():
    system.reset_session()
    system.feed_adapter = create_initial_feed()
    system.data_manager.feed = system.feed_adapter
    state = await get_system_state()
    await manager.broadcast({
        "type": "RESET",
        "data": state
    })
    return {"status": "RESET_SUCCESS", "state": state}

@app.post("/api/clear_trades")
async def clear_today_trades(date: Optional[str] = None):
    """
    Clears Closed Trades Audit Log for the day across in-memory portfolio,
    audit CSV logs, and MongoDB Atlas.
    """
    result = system.clear_today_trades(date)
    await manager.broadcast({
        "type": "TRADES_CLEARED",
        "data": {
            "trade_history": system.portfolio_manager.get_trade_history(),
            "portfolio_summary": result["portfolio_summary"],
            "cleared_stats": result
        }
    })
    return {
        "status": "TRADES_CLEARED",
        "result": result,
        "trade_history": system.portfolio_manager.get_trade_history(),
        "portfolio_summary": result["portfolio_summary"]
    }


@app.post("/api/load_replay")
async def load_replay(ticks: int = 400):
    global system
    sample_df = create_sample_dataset(num_bars=ticks + 100)
    feed = HistoricalCSVFeedAdapter(sample_df)
    system = SensexSimulationSystem(feed_adapter=feed)
    state = await get_system_state()
    await manager.broadcast({"type": "RESET", "data": state})
    return {"status": "REPLAY_LOADED", "ticks": ticks}

@app.post("/api/trigger_trade")
async def trigger_test_trade(side: str = "PUT"):
    """
    Triggers a test trade (PUT or CALL) for immediate simulation verification.
    Enforces strict CALL/PUT alternation rules and active trade constraints.
    """
    side_clean = side.upper()
    
    # 1. Check if position is already active
    if system.simulation_engine.active_trade is not None:
        active = system.simulation_engine.active_trade
        return {
            "status": "REJECTED",
            "event": "ALREADY_ACTIVE_TRADE",
            "message": f"Active {active['side']} position #{active['trade_id']} already open. Please exit current position first.",
            "trade": active
        }

    # 2. Check strict alternation
    if not system.trade_manager.can_take_trade(side_clean):
        next_req = system.trade_manager.get_next_required_trade()
        return {
            "status": "REJECTED",
            "event": "SIGNAL_REJECTED",
            "message": f"Alternation rule violation! Cannot take consecutive {side_clean} trades. Next required trade is {next_req}.",
            "next_required": next_req
        }

    tick_res = system.process_market_update()
    strikes = tick_res.get("strikes", {})
    quotes = tick_res.get("option_quotes", {})
    
    opt_type = "PE" if side_clean == "PUT" else "CE"
    strike = strikes.get("put_strike" if side_clean == "PUT" else "call_strike")
    if not strike:
        strike_info = system.strike_selector.get_strikes(tick_res.get("sensex_mid", 77500))
        strike = strike_info.get("put_strike" if side_clean == "PUT" else "call_strike")
        
    quote = system.data_manager.get_locked_option_quote(strike, opt_type)
    entry_price = float(quote.get("mid_price", quote.get("ltp", 0.0)))
    
    res = system.simulation_engine.open_trade(
        side=side_clean,
        strike=strike,
        entry_price=entry_price,
        timestamp=tick_res.get("timestamp", "")
    )
    
    if res.get("status") == "REJECTED":
        return {
            "status": "REJECTED",
            "event": res.get("event", "SIGNAL_REJECTED"),
            "message": res.get("message", res.get("reason", "Trade rejected by engine.")),
            "next_required": res.get("next_required", system.trade_manager.get_next_required_trade())
        }

    # Audit log
    system.audit_logger.log_signal_event(
        timestamp=tick_res.get("timestamp", ""),
        raw_signal=side_clean,
        confirmed_signal=side_clean,
        confirmation_count=1,
        next_required=system.trade_manager.get_next_required_trade(),
        action_taken="TRADE_OPENED",
        rejection_reason="MANUAL_TEST_TRIGGER"
    )
    
    # Broadcast event
    await manager.broadcast({
        "type": "TICK_UPDATE",
        "data": {
            **tick_res,
            "event": "TRADE_OPENED",
            "active_trade": system.simulation_engine.active_trade,
            "engine_result": res
        }
    })
    return {"status": "SUCCESS", "event": "TRADE_OPENED", "trade": system.simulation_engine.active_trade}

@app.post("/api/exit_trade")
async def exit_active_trade():
    """
    Manually closes any currently open position at market price.
    """
    global system
    if system.simulation_engine.active_trade is None:
        return {"status": "NO_ACTIVE_TRADE", "message": "No active trade to exit."}

    t = system.simulation_engine.active_trade
    opt_type = "CE" if t["side"] == "CALL" else "PE"
    quote = system.data_manager.get_locked_option_quote(t["strike"], opt_type)
    exit_price = float(quote.get("ltp", t.get("current_price", t["entry_price"])))

    from datetime import datetime, timedelta
    ist_ts = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    
    close_res = system.simulation_engine.close_trade(
        exit_price=exit_price,
        exit_reason="MANUAL_EXIT",
        timestamp=ist_ts
    )

    if system.db_manager and close_res.get("trade"):
        try:
            system.db_manager.save_closed_trade(close_res["trade"])
            system.db_manager.save_portfolio_summary(system.portfolio_manager.get_summary())
        except Exception as e:
            logger.warning(f"Error persisting manual exit to DB: {e}")

    # Broadcast closed event
    tick_res = system.process_market_update()
    await manager.broadcast({
        "type": "TICK_UPDATE",
        "data": {
            **tick_res,
            "event": "TRADE_CLOSED",
            "active_trade": None,
            "engine_result": close_res
        }
    })
    return {
        "status": "SUCCESS",
        "event": "TRADE_CLOSED",
        "trade": close_res.get("trade")
    }

@app.post("/api/update_config")
async def update_config(req: ConfigUpdateRequest):
    cfg = system.config
    cfg.stop_loss_points = float(req.stop_loss_points)
    cfg.target_points = float(req.target_points)
    cfg.trail_trigger_points = float(req.trail_trigger_points)
    cfg.trail_lock_points = float(req.trail_lock_points)
    cfg.enable_trailing_sl = bool(req.enable_trailing_sl)
    cfg.max_trades_per_day = int(req.max_trades_per_day)
    cfg.lot_size = int(req.lot_size)
    cfg.auto_schedule = bool(req.auto_schedule)

    if req.confirmation_candles is not None:
        cfg.confirmation_candles = req.confirmation_candles
        system.signal_engine.confirmation_candles = req.confirmation_candles
    if req.min_holding_updates is not None:
        cfg.min_holding_updates = req.min_holding_updates
        system.risk_manager.min_holding_updates = req.min_holding_updates
    if req.strike_distance_points is not None:
        cfg.strike_distance_points = req.strike_distance_points
        system.strike_selector.strike_distance = req.strike_distance_points

    system.risk_manager.stop_loss_points = cfg.stop_loss_points
    system.risk_manager.target_points = cfg.target_points
    system.risk_manager.trail_trigger_points = cfg.trail_trigger_points
    system.risk_manager.trail_lock_points = cfg.trail_lock_points
    system.risk_manager.enable_trailing_sl = cfg.enable_trailing_sl

    system.portfolio_manager.lot_size = cfg.lot_size
    system.simulation_engine.max_trades_per_day = cfg.max_trades_per_day
    system.simulation_engine.auto_schedule = cfg.auto_schedule

    # Persist updated configuration to MongoDB
    saved_to_db = False
    if getattr(system, "db_manager", None):
        try:
            saved_to_db = system.db_manager.save_configuration(cfg.to_dict())
        except Exception as e:
            print(f"Failed to persist updated config to MongoDB: {e}")

    # Broadcast updated configuration to WebSocket clients
    await manager.broadcast({
        "type": "CONFIG_UPDATE",
        "data": {
            "config": cfg.to_dict(),
            "saved_to_db": saved_to_db
        }
    })

    return {
        "status": "CONFIG_UPDATED",
        "config": cfg.to_dict(),
        "saved_to_db": saved_to_db,
        "message": "Parameters updated successfully"
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        init_state = await get_system_state()
        await websocket.send_json({"type": "INIT_STATE", "data": init_state})
        if "latest_tick" in init_state:
            await websocket.send_json({"type": "TICK_UPDATE", "data": init_state["latest_tick"]})
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Background auto-runner loop
_last_broadcast_ltp: float = 0.0
_last_broadcast_call_ltp: float = 0.0
_last_broadcast_put_ltp: float = 0.0

async def background_simulation_loop():
    global _last_broadcast_ltp, _last_broadcast_call_ltp, _last_broadcast_put_ltp
    while True:
        try:
            system.feed_adapter.step()
            tick_result = system.process_market_update()

            # Extract current LTPs
            cur_spot = float(tick_result.get("sensex_ltp") or tick_result.get("sensex_mid") or 0.0)
            opt_quotes = tick_result.get("option_quotes", {})
            call_q = opt_quotes.get("CALL") or {}
            put_q  = opt_quotes.get("PUT") or {}
            cur_call = float(call_q.get("ltp") or call_q.get("mid_price") or 0.0)
            cur_put  = float(put_q.get("ltp")  or put_q.get("mid_price")  or 0.0)

            # Only broadcast if something actually changed (≥0.05 pts on spot, ≥0.01 on valid premiums)
            spot_changed = cur_spot > 0 and abs(cur_spot - _last_broadcast_ltp) >= 0.05
            call_changed = cur_call > 0 and abs(cur_call - _last_broadcast_call_ltp) >= 0.01
            put_changed  = cur_put > 0 and abs(cur_put - _last_broadcast_put_ltp) >= 0.01
            has_event    = tick_result.get("event") not in (None, "NO_CHANGE", "MARKET_UPDATE")

            if spot_changed or call_changed or put_changed or has_event:
                if cur_spot > 0:
                    _last_broadcast_ltp = cur_spot
                if cur_call > 0:
                    _last_broadcast_call_ltp = cur_call
                if cur_put > 0:
                    _last_broadcast_put_ltp = cur_put
                await manager.broadcast({
                    "type": "TICK_UPDATE",
                    "data": tick_result
                })
        except Exception as e:
            print(f"Error in background market loop: {e}")
        await asyncio.sleep(tick_speed_seconds if is_auto_running else 1.0)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_simulation_loop())

# Serve static dashboard UI
web_dir = os.path.join(os.path.dirname(__file__), "web")
if os.path.exists(web_dir):
    app.mount("/static", StaticFiles(directory=web_dir), name="static")

@app.get("/")
async def serve_index():
    index_file = os.path.join(os.path.dirname(__file__), "web", "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "Web UI files not found."})

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 6001))
    uvicorn.run(app, host=host, port=port)

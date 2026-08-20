"""
db_manager.py
MongoDB Atlas Database Manager for BSE Sensex Options Simulation.
Connects to Cluster0 -> new_logic database -> Sensex collection.
Stores trade history, system configuration, and session metrics.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pymongo import MongoClient, UpdateOne

logger = logging.getLogger(__name__)

class MongoDatabaseManager:
    """
    Manages persistence to MongoDB Atlas collection `new_logic.Sensex`.
    """
    def __init__(
        self,
        mongo_uri: str,
        db_name: str = "new_logic",
        collection_name: str = "Sensex"
    ):
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.collection_name = collection_name
        self.client: Optional[MongoClient] = None
        self.db = None
        self.collection = None
        self.connected = False
        self._connect()

    def _connect(self):
        try:
            self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=6000)
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            # Quick ping to verify connectivity
            self.client.admin.command('ping')
            self.connected = True
            logger.info(f"Connected to MongoDB Atlas: database '{self.db_name}', collection '{self.collection_name}'.")
        except Exception as e:
            self.connected = False
            logger.warning(f"MongoDB connection failed: {e}. Offline mode active.")

    def save_configuration(self, config_dict: Dict[str, Any]) -> bool:
        """
        Saves or updates the system configuration document in MongoDB.
        """
        if not self.connected:
            self._connect()
        if not self.connected or self.collection is None:
            return False

        try:
            doc = {
                "type": "configuration",
                "symbol": config_dict.get("symbol", "SENSEX"),
                "config": config_dict,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp_utc": datetime.now(timezone.utc).isoformat()
            }
            self.collection.update_one(
                {"type": "configuration", "symbol": doc["symbol"]},
                {"$set": doc},
                upsert=True
            )
            logger.info("Successfully persisted system configuration to MongoDB (new_logic.Sensex).")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration to MongoDB: {e}")
            return False

    def save_closed_trade(self, trade: Dict[str, Any]) -> bool:
        """
        Persists a completed/closed trade document into MongoDB.
        """
        if not self.connected:
            self._connect()
        if not self.connected or self.collection is None:
            return False

        try:
            trade_id = trade.get("trade_id")
            doc = {
                "type": "trade",
                "trade_id": trade_id,
                "symbol": "SENSEX",
                "side": trade.get("side"),
                "strike": trade.get("strike"),
                "option_symbol": trade.get("symbol"),
                "entry_price": float(trade.get("entry_price", 0.0)),
                "exit_price": float(trade.get("exit_price", 0.0)),
                "pnl_points": float(trade.get("pnl_points", 0.0)),
                "pnl_rupees": float(trade.get("pnl_rupees", 0.0)),
                "exit_reason": trade.get("exit_reason"),
                "entry_time": trade.get("entry_time"),
                "exit_time": trade.get("exit_time"),
                "duration_seconds": float(trade.get("duration_seconds", 0.0)),
                "update_count": int(trade.get("update_count", 0)),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp_utc": datetime.now(timezone.utc).isoformat()
            }
            if trade_id is not None:
                self.collection.update_one(
                    {"type": "trade", "trade_id": trade_id},
                    {"$set": doc},
                    upsert=True
                )
            else:
                self.collection.insert_one(doc)

            logger.info(f"Persisted Trade #{trade_id} to MongoDB (new_logic.Sensex).")
            return True
        except Exception as e:
            logger.error(f"Failed to persist trade to MongoDB: {e}")
            return False

    def save_all_trades_history(self, trade_history: List[Dict[str, Any]]) -> bool:
        """
        Bulk upserts trade history list into MongoDB.
        """
        if not trade_history:
            return True
        if not self.connected:
            self._connect()
        if not self.connected or self.collection is None:
            return False

        try:
            ops = []
            for t in trade_history:
                trade_id = t.get("trade_id")
                doc = {
                    "type": "trade",
                    "trade_id": trade_id,
                    "symbol": "SENSEX",
                    "side": t.get("side"),
                    "strike": t.get("strike"),
                    "option_symbol": t.get("symbol"),
                    "entry_price": float(t.get("entry_price", 0.0)),
                    "exit_price": float(t.get("exit_price", 0.0)),
                    "pnl_points": float(t.get("pnl_points", 0.0)),
                    "pnl_rupees": float(t.get("pnl_rupees", 0.0)),
                    "exit_reason": t.get("exit_reason"),
                    "entry_time": t.get("entry_time"),
                    "exit_time": t.get("exit_time"),
                    "duration_seconds": float(t.get("duration_seconds", 0.0)),
                    "update_count": int(t.get("update_count", 0)),
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "timestamp_utc": datetime.now(timezone.utc).isoformat()
                }
                ops.append(
                    UpdateOne(
                        {"type": "trade", "trade_id": trade_id},
                        {"$set": doc},
                        upsert=True
                    )
                )
            if ops:
                self.collection.bulk_write(ops)
                logger.info(f"Bulk persisted {len(ops)} trades to MongoDB (new_logic.Sensex).")
            return True
        except Exception as e:
            logger.error(f"Failed to bulk write trades to MongoDB: {e}")
            return False

    def save_portfolio_summary(self, summary: Dict[str, Any]) -> bool:
        """
        Persists latest portfolio performance summary into MongoDB.
        """
        if not self.connected:
            self._connect()
        if not self.connected or self.collection is None:
            return False

        try:
            doc = {
                "type": "portfolio_summary",
                "symbol": "SENSEX",
                "summary": summary,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp_utc": datetime.now(timezone.utc).isoformat()
            }
            self.collection.update_one(
                {"type": "portfolio_summary", "symbol": "SENSEX"},
                {"$set": doc},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save portfolio summary to MongoDB: {e}")
            return False

    def get_saved_trades(self, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Retrieves trade records from MongoDB.
        """
        if not self.connected:
            self._connect()
        if not self.connected or self.collection is None:
            return []

        try:
            cursor = self.collection.find({"type": "trade"}).sort("trade_id", 1).limit(limit)
            trades = []
            for doc in cursor:
                doc.pop("_id", None)
                trades.append(doc)
            return trades
        except Exception as e:
            logger.error(f"Failed to fetch trades from MongoDB: {e}")
            return []

    def get_saved_config(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves saved configuration from MongoDB.
        """
        if not self.connected:
            self._connect()
        if not self.connected or self.collection is None:
            return None

        try:
            doc = self.collection.find_one({"type": "configuration", "symbol": "SENSEX"})
            if doc and "config" in doc:
                return doc["config"]
            return None
        except Exception as e:
            logger.error(f"Failed to fetch config from MongoDB: {e}")
            return None

    def clear_today_trades(self, date_str: Optional[str] = None) -> int:
        """
        Deletes trade documents matching today's date from MongoDB (or all if not date-scoped).
        """
        if not self.connected:
            self._connect()
        if not self.connected or self.collection is None:
            return 0

        try:
            if not date_str:
                from datetime import datetime, timedelta, timezone
                ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
                date_str = ist_now.strftime("%Y-%m-%d")

            query = {
                "type": "trade",
                "$or": [
                    {"created_at": {"$regex": f"^{date_str}"}},
                    {"entry_time": {"$regex": f"^{date_str}"}},
                    {"exit_time": {"$regex": f"^{date_str}"}}
                ]
            }
            res = self.collection.delete_many(query)
            deleted_count = res.deleted_count
            logger.info(f"Cleared {deleted_count} trade records for {date_str} from MongoDB (new_logic.Sensex).")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to clear trades for {date_str} from MongoDB: {e}")
            return 0



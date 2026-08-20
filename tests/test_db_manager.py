"""
test_db_manager.py
Unit tests for MongoDatabaseManager
"""

import unittest
from unittest.mock import MagicMock, patch
from db_manager import MongoDatabaseManager

class TestMongoDatabaseManager(unittest.TestCase):

    @patch("db_manager.MongoClient")
    def test_save_configuration(self, mock_client_cls):
        mock_client = MagicMock()
        mock_coll = MagicMock()
        mock_client.__getitem__.return_value.__getitem__.return_value = mock_coll
        mock_client_cls.return_value = mock_client

        mgr = MongoDatabaseManager(
            mongo_uri="mongodb://localhost:27017",
            db_name="new_logic",
            collection_name="Sensex"
        )
        self.assertTrue(mgr.connected)

        config_dict = {
            "symbol": "SENSEX",
            "lot_size": 20,
            "stop_loss_points": 50.0,
            "target_points": 100.0
        }
        res = mgr.save_configuration(config_dict)
        self.assertTrue(res)
        mock_coll.update_one.assert_called_once()

    @patch("db_manager.MongoClient")
    def test_save_closed_trade(self, mock_client_cls):
        mock_client = MagicMock()
        mock_coll = MagicMock()
        mock_client.__getitem__.return_value.__getitem__.return_value = mock_coll
        mock_client_cls.return_value = mock_client

        mgr = MongoDatabaseManager(
            mongo_uri="mongodb://localhost:27017",
            db_name="new_logic",
            collection_name="Sensex"
        )

        trade = {
            "trade_id": 1,
            "symbol": "SENSEX26AUG77500CE",
            "side": "CALL",
            "strike": 77500,
            "entry_price": 250.0,
            "exit_price": 350.0,
            "pnl_points": 100.0,
            "pnl_rupees": 2000.0,
            "exit_reason": "TARGET_HIT",
            "entry_time": "2026-08-18 10:00:00",
            "exit_time": "2026-08-18 10:15:00",
            "duration_seconds": 900.0,
            "update_count": 5
        }
        res = mgr.save_closed_trade(trade)
        self.assertTrue(res)
        mock_coll.update_one.assert_called_once()

    @patch("db_manager.MongoClient")
    def test_clear_today_trades(self, mock_client_cls):
        mock_client = MagicMock()
        mock_coll = MagicMock()
        mock_delete_res = MagicMock()
        mock_delete_res.deleted_count = 3
        mock_coll.delete_many.return_value = mock_delete_res
        mock_client.__getitem__.return_value.__getitem__.return_value = mock_coll
        mock_client_cls.return_value = mock_client

        mgr = MongoDatabaseManager(
            mongo_uri="mongodb://localhost:27017",
            db_name="new_logic",
            collection_name="Sensex"
        )

        deleted = mgr.clear_today_trades("2026-08-19")
        self.assertEqual(deleted, 3)
        mock_coll.delete_many.assert_called_once()

if __name__ == "__main__":
    unittest.main()


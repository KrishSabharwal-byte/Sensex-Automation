"""
test_trade_manager.py
Unit tests for TradeManager alternation rule and skip accounting.
"""

import unittest
from trade_manager import TradeManager

class TestTradeManager(unittest.TestCase):
    def setUp(self):
        self.tm = TradeManager()

    def test_first_trade_can_be_either_side(self):
        self.assertEqual(self.tm.get_next_required_trade(), "ANY")
        self.assertTrue(self.tm.can_take_trade("CALL"))
        self.assertTrue(self.tm.can_take_trade("PUT"))

    def test_alternation_after_call(self):
        # Open CALL
        proc = self.tm.process_signal("CALL")
        self.assertEqual(proc["status"], "ACCEPTED")
        self.tm.record_trade("CALL")

        # Next required MUST be PUT
        self.assertEqual(self.tm.get_next_required_trade(), "PUT")
        self.assertFalse(self.tm.can_take_trade("CALL"))
        self.assertTrue(self.tm.can_take_trade("PUT"))

    def test_skip_then_resume_sequence(self):
        # 1. Open first trade: CALL
        self.tm.record_trade("CALL")
        self.assertEqual(self.tm.get_next_required_trade(), "PUT")

        # 2. Receive 3 repeated CALL signals while waiting -> all rejected
        for i in range(3):
            res = self.tm.process_signal("CALL")
            self.assertEqual(res["status"], "REJECTED")
            self.assertEqual(res["skipped_count"], i + 1)
            self.assertEqual(res["next_required"], "PUT")

        self.assertEqual(self.tm.skipped_signals_count, 3)
        self.assertEqual(self.tm.skipped_call_count, 3)
        self.assertEqual(self.tm.skipped_put_count, 0)

        # 3. Receive valid PUT signal -> accepted!
        res_put = self.tm.process_signal("PUT")
        self.assertEqual(res_put["status"], "ACCEPTED")
        self.tm.record_trade("PUT")

        # 4. Next required MUST now be CALL
        self.assertEqual(self.tm.get_next_required_trade(), "CALL")
        
        # 5. Receive 2 PUT signals -> rejected
        self.tm.process_signal("PUT")
        self.tm.process_signal("PUT")
        self.assertEqual(self.tm.skipped_signals_count, 5)
        self.assertEqual(self.tm.skipped_put_count, 2)

    def test_session_reset(self):
        self.tm.record_trade("CALL")
        self.tm.process_signal("CALL")
        self.assertEqual(self.tm.skipped_signals_count, 1)

        self.tm.reset()
        self.assertIsNone(self.tm.last_trade)
        self.assertEqual(self.tm.get_next_required_trade(), "ANY")
        self.assertEqual(self.tm.skipped_signals_count, 0)

if __name__ == "__main__":
    unittest.main()

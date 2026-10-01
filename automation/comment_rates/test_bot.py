import datetime as dt
import unittest
from unittest.mock import patch
import bot

class Tests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 10, 1, 4, 13, tzinfo=bot.UTC)
        self.feed = dict(gold24_10g=151119, gold22_10g=138425, silver999_kg=227038,
                         quote_timestamp='2026-10-01T04:13:00Z')
        for k in bot.RATE_KEYS: self.feed[k + '_captured_at'] = self.feed['quote_timestamp']
    def test_template(self):
        text = bot.reply(self.feed, self.now)
        for word in ('01-10-2026, 09:43 AM IST', '₹1,51,100', '₹1,38,400', '₹2,27,000', 'GST extra', '@sonarkatta'):
            self.assertIn(word, text)
        self.assertNotIn('http', text)
        self.assertNotIn('AIB', text)
    def test_rounding(self):
        self.assertEqual(bot.money(150050), '1,50,100')
        self.assertEqual(bot.money(150049), '1,50,000')
    def test_trigger(self):
        for x in ['rate', 'Gold rates please', 'आजचा दर', 'चांदीचा भाव', 'price?', 'रेट पाठवा', 'live']:
            self.assertTrue(bot.eligible(x), x)
        for x in ['great video', 'सुंदर व्हिडिओ', 'my corporate meeting', 'fake rates', 'दर खोटे आहेत', 'wrong price', '']:
            self.assertFalse(bot.eligible(x), x)
    def test_stale(self):
        with self.assertRaises(bot.Stop): bot.reply(self.feed, self.now + dt.timedelta(minutes=11))
    def test_future(self):
        with self.assertRaises(bot.Stop): bot.reply(self.feed, self.now - dt.timedelta(minutes=2))
    def test_mixed(self):
        self.feed['silver999_kg_captured_at'] = '2026-10-01T04:08:00Z'
        with self.assertRaises(bot.Stop): bot.reply(self.feed, self.now)
    def test_bad_types(self):
        for x in [True, '151119', -1, 0, 1e9]:
            self.feed['gold24_10g'] = x
            with self.assertRaises(bot.Stop): bot.reply(self.feed, self.now)
    def test_bad_ratio(self):
        self.feed['gold22_10g'] = 100000
        with self.assertRaises(bot.Stop): bot.reply(self.feed, self.now)
    def test_disabled_no_reads(self):
        with patch.dict(bot.os.environ, {}, clear=True), patch.object(bot, 'request') as req:
            bot.main(); req.assert_not_called()
    def test_no_naive_timestamp(self):
        with self.assertRaises(bot.Stop): bot.timestamp('2026-10-01T04:13:00')
    def test_reservation_before_post(self):
        state = bot.State.__new__(bot.State)
        state.data = {'schema': 1, 'seen': {}, 'counts': {}}
        with patch.object(state, 'save') as save:
            key = state.reserve('youtube', 'comment-id')
            self.assertIsNotNone(key); save.assert_called_once()
            self.assertIsNone(state.reserve('youtube', 'comment-id'))
            self.assertNotIn('comment-id', str(state.data))
    def test_daily_cap(self):
        state = bot.State.__new__(bot.State)
        state.data = {'schema': 1, 'seen': {}, 'counts': {'youtube': [dt.datetime.now(bot.UTC).isoformat()] * 80}}
        with self.assertRaises(bot.Stop): state.reserve('youtube', 'another')

if __name__ == '__main__': unittest.main()

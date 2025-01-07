import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from unittest.mock import patch
from src.twitteragent import TwitterYieldStrategyBot

class TestTwitterBot(unittest.TestCase):
    @patch('tweepy.API')
    def test_bot_initialization(self, mock_twitter):
        # Test bot initialization
        bot = TwitterYieldStrategyBot()
        self.assertIsNotNone(bot)
        
    @patch('requests.post')
    def test_deepseek_api(self, mock_post):
        # Test DeepSeek API call
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "test response"}}]
        }
        
        bot = TwitterYieldStrategyBot()
        response = bot.call_deepseek_api("test prompt")
        self.assertEqual(response, "test response")

if __name__ == '__main__':
    unittest.main() 
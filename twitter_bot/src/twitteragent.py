import os
import tweepy
import requests
from ratelimit import limits, sleep_and_retry
import sqlite3
import re

TWITTER_RATE_LIMIT = 15   # Max tweets per 15 minutes

class TwitterYieldStrategyBot:
    def __init__(self):
        
        # Validate required variables
        required_vars = [
            'TWITTER_API_KEY',
            'TWITTER_API_SECRET',
            'TWITTER_ACCESS_TOKEN',
            'TWITTER_ACCESS_SECRET',
            'DEEPSEEK_API_KEY'
        ]
        
        # Check and load environment variables
        self.twitter_api_key = os.getenv('TWITTER_API_KEY')
        self.twitter_api_secret = os.getenv('TWITTER_API_SECRET')
        self.twitter_access_token = os.getenv('TWITTER_ACCESS_TOKEN')
        self.twitter_access_secret = os.getenv('TWITTER_ACCESS_SECRET')
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        
        # Verify all required variables are present
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )
        
        # Initialize APIs
        self.twitter_api = self._init_twitter_api()
        
        # Configure DeepSeek
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        self.deepseek_api_url = os.getenv('DEEPSEEK_API_URL')  
        self._init_db()

    def parse_tweet(self, text):
        """Extract crypto and sentiment from tweet"""
        cryptos = self._detect_cryptos(text)
        sentiment = self._detect_sentiment(text)
        return cryptos, sentiment

    def _detect_cryptos(self, text):
        """Detect crypto mentions using regex"""
        crypto_pattern = r'\b(BTC|ETH|BNB|XRP|ADA|SOL|MATIC|AVAX|DOT|DOGE|SHIB|USDT|USDC|DAI)\b'
        return re.findall(crypto_pattern, text.upper())

    def _detect_sentiment(self, text):
        """Basic sentiment detection"""
        text = text.lower()
        if 'bullish' in text:
            return 'bullish'
        elif 'bearish' in text:
            return 'bearish'
        return 'neutral'

    def generate_strategy(self, crypto, sentiment):
        """Generate strategy using DeepSeek API with detailed format"""
        strategy_prompt = f"""
        Provide a {sentiment} DeFi and Yield Farming strategy for {crypto}.
        Include:
        1. Brief description (1 sentence)
        2. Key action (1 step)
        3. Main benefit
        4. Risk level (1-5)
        5. One relevant link
        
        Format concisely for Twitter (max 280 chars).
        Example format:
        "[Crypto] Strategy: [1-sentence desc]. Action: [key step]. Benefit: [main benefit]. Risk: [level]. More: [link]"
        """
        
        try:
            # Get initial strategy
            strategy = self.call_deepseek_api(strategy_prompt)
            
            if not strategy:
                return None
            
            # Ensure it fits Twitter's limit
            formatted_strategy = self._format_for_twitter(strategy)
            return formatted_strategy
            
        except Exception as e:
            print(f"Error generating strategy: {e}")
            return None

    def _format_for_twitter(self, text):
        """Ensure text fits within Twitter's 280-character limit"""
        if len(text) <= 280:
            return text
        
        # If text contains a URL
        if 'http' in text:
            url_start = text.find('http')
            base_text = text[:url_start].strip()
            url = text[url_start:]
            
            # Calculate available space
            available = 280 - len(url) - 1  # -1 for space
            if available > 20:  # Minimum reasonable text length
                return f"{base_text[:available]} {url}"
        
        # If no URL or still too long
        return text[:277] + "..."

    @sleep_and_retry
    @limits(calls=TWITTER_RATE_LIMIT, period=900)  # 15 minutes = 900 seconds
    def on_tweet(self, tweet):
        """Process incoming tweet"""
        if '@AgentYieldDefi' in tweet.text.lower() and 'strategy' in tweet.text.lower():
            cryptos, sentiment = self.parse_tweet(tweet.text)
            
            if cryptos:
                for crypto in cryptos:
                    strategy = self.generate_strategy(crypto, sentiment)
                    if strategy:
                        response = f"@{tweet.user.screen_name} Here's a {sentiment} strategy for {crypto}:\n{strategy}"
                        
                        # Ensure the response doesn't exceed Twitter's limit
                        if len(response) > 280:
                            # Calculate available space after the mention
                            available_space = 280 - (len(tweet.user.screen_name) + 2)  # +2 for "@" and space
                            response = f"@{tweet.user.screen_name} {strategy[:available_space]}"
                        
                        self.api.update_status(
                            status=response,
                            in_reply_to_status_id=tweet.id
                        )
                    else:
                        # If strategy generation fails
                        self.api.update_status(
                            status=f"@{tweet.user.screen_name} Sorry, couldn't generate a strategy. Please try again!",
                            in_reply_to_status_id=tweet.id
                        )

    def start(self):
        """Start listening for tweets"""
        self.stream.filter(track=['@AgentYieldDefi strategy'])

    @sleep_and_retry
    def call_deepseek_api(self, prompt):
        """Call the DeepSeek API to generate insights or analyze data."""
        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a Crypto Finance Analyst specializing in DeFi and Yield Farming."},
                {"role": "user", "content": prompt}
            ],
            "stream": False
        }

        try:
            response = requests.post(
                f"{self.deepseek_api_url}/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except requests.exceptions.RequestException as e:
            print(f"Failed to call DeepSeek API: {str(e)}")
            return None

    def _init_db(self):
        """Initialize SQLite database on PythonAnywhere"""
        try:
            # Use absolute path in your home directory
            db_path = os.path.expanduser('~/twitter_bot/data/processed_tweets.db')
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            self.conn = sqlite3.connect(db_path)
            self.cursor = self.conn.cursor()
            
            # Enable WAL mode for better concurrency
            self.cursor.execute('PRAGMA journal_mode=WAL')
            
            # Create table with additional metadata
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_tweets (
                    tweet_id TEXT PRIMARY KEY,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    response_id TEXT
                )
            ''')
            self.conn.commit()
        except Exception as e:
            print(f"Database error: {e}")
            raise

if __name__ == "__main__":
    bot = TwitterYieldStrategyBot()
    bot.start() 
from tweepy import Tweet  # Import the Tweet class
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from src.twitteragent import (    
    fetch_tweets,_detect_cryptos)
def main():
    # Fetch tweets
    crypto = _detect_cryptos("I'm bullish SUI and I'm looking for a strategy")
    print(crypto)

if __name__ == "__main__":
    main()
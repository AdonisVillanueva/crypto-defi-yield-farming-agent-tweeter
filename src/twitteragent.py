import re
import time
import tweepy
from dotenv import load_dotenv
from ratelimit import limits, sleep_and_retry
import os
from datetime import datetime, timedelta
from tweepy import Tweet  # Import the Tweet class
import spacy
from openai import OpenAI  # Add this import at the top of the file

# Load environment variables from .env file
load_dotenv()

# Constants
PREFIX = "[Automated]: "
PREFIX_LENGTH = len(PREFIX)  # Length of "[Automated]: "
CUSTOM_STRATEGY_URL = "https://agentyield.streamlit.app/Custom_Strategy"

# Mock Twitter API response
MOCK_TWEETS = {
    "data": [
        {
            "id": "1234567890123456789",
            "text": "Bullish sentiment today! @AgentYieldDefi for $SOL",
            "author_id": "9876543210",
            "created_at": "2025-01-08T12:34:56Z",
            "lang": "en",
            "source": "Twitter Web App"
        },
        {
            "id": "9876543210987654321",
            "text": "Bearish sentiment for now. @AgentYieldDefi for $BTC",
            "author_id": "1234567890",
            "created_at": "2025-01-08T12:30:00Z",
            "lang": "en",
            "source": "Twitter for iPhone"
        }
    ],
    "meta": {
        "newest_id": "9876543210987654321",
        "oldest_id": "1234567890123456789",
        "result_count": 2
    }
}

# Grab credentials from .env
consumer_key = os.getenv("TWITTER_CONSUMER_KEY")
consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET")
access_token = os.getenv("TWITTER_ACCESS_TOKEN")
access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL")

# Global variable to cache the client
_client = None

# Authenticate with Twitter API
def initialize_twitter_client():
    """Initialize the Twitter client and cache it."""
    global _client
    
    # Return cached client if it exists
    if _client is not None:
        return _client
    
    # Load credentials from environment variables
    credentials = {
        "BEARER_TOKEN": BEARER_TOKEN,
        "consumer_key": consumer_key,
        "consumer_secret": consumer_secret,
        "access_token": access_token,
        "access_token_secret": access_token_secret,
    }
    
    # Validate credentials
    missing_keys = [key for key, value in credentials.items() if value is None]
    if missing_keys:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_keys)}")
    
    # Initialize the Tweepy Client
    _client = tweepy.Client(
        bearer_token=credentials["BEARER_TOKEN"],
        consumer_key=credentials["consumer_key"],
        consumer_secret=credentials["consumer_secret"],
        access_token=credentials["access_token"],
        access_token_secret=credentials["access_token_secret"]
    )

    return _client

@sleep_and_retry
@limits(calls=15, period=900)  # 15 calls per 15 minutes for free tier
def fetch_tweets(client):
    """Fetch the latest tweets mentioning @AgentYieldDefi with bullish or bearish sentiment."""
    all_tweets = []
    
    try:
        query = '@AgentYieldDefi (bullish OR bearish OR crash OR rocket OR long) (strategy OR plan OR "game plan" OR roadmap)'
        start_time = (datetime.now() - timedelta(minutes=30)).isoformat() + "Z"  # Set start_time to 30 minutes ago
        print(f"Fetching tweets with query: {query}, start_time: {start_time}")
        
        response = client.search_recent_tweets(
            query=query,
            tweet_fields=["author_id", "text"],
            max_results=10,
            start_time=start_time
        )
        
        # Debug: Check if response is None
        if response is None:
            print("Error: API call returned None. Check API key, permissions, and query parameters.")
            return all_tweets
        
        # Debug: Check response metadata
        if hasattr(response, 'meta') and response.meta:
            print(f"Response metadata: {response.meta}")
        else:
            print("No metadata found in response.")
        
        # Debug: Check for errors in the response
        if hasattr(response, 'errors') and response.errors:
            print(f"Response errors: {response.errors}")
            return all_tweets
        
        # Check if the response contains data
        if hasattr(response, 'data') and response.data:
            print(f"Fetched {len(response.data)} tweets.")
            all_tweets.extend(response.data)
        else:
            print("No tweets found for the given query.")
        
        print("Fetched tweets saved to temp_fetched_tweets.json")
    
    except tweepy.TweepyException as e:
        if "429" in str(e):  # Handle rate limit errors
            print("Rate limit reached. Sleeping for 900 seconds...")
            time.sleep(900)  # Sleep for 15 minutes
            print("Resuming after sleep...")
            return fetch_tweets(client)  # Retry
        else:
            print(f"Error fetching tweets: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    return all_tweets

@sleep_and_retry
@limits(calls=15, period=900)  # 15 calls per 15 minutes for free tier
def reply_to_tweet(tweet_id, user_handle, strategy, sentiment, crypto, client):
    """Reply to a tweet with the generated strategy."""
    if not strategy:
        print("No strategy provided. Skipping reply.")
        return    

    # Truncate the strategy text if necessary
    if len(strategy) > 280:
        print("Strategy is too long. Skipping reply.")
        return

    # Send the reply
    try:
        client.create_tweet(text=strategy, in_reply_to_tweet_id=tweet_id)
        print(f"Replied to tweet {tweet_id} by @{user_handle} with strategy: {strategy}")
    except tweepy.TweepyException as e:
        if "Too Many Requests" in str(e):
            print("Rate limit reached. Sleeping for 900 seconds...")
            time.sleep(900)  # Sleep for 15 minutes
            print("Resuming after sleep...")
            reply_to_tweet(tweet_id, user_handle, strategy, sentiment, crypto, client)  # Retry
        else:
            print(f"Error replying to tweet: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

def parse_tweet(text):
    """Extract crypto and sentiment from tweet."""
    crypto = _detect_cryptos(text)
    sentiment = _detect_sentiment(text)
    return crypto, sentiment

def _detect_cryptos(tweet_text, nlp):
    """Detect cryptocurrencies dynamically using spaCy's NER."""
    # Process the tweet text
    doc = nlp(tweet_text)
    
    # Look for entities that might represent cryptocurrencies
    for ent in doc.ents:
        # Check if the entity is an organization (common label for crypto symbols)
        if ent.label_ == "ORG":
            # Check if the entity text looks like a crypto symbol (e.g., 3-5 uppercase letters)
            if ent.text.isupper() and 2 <= len(ent.text) <= 5:
                return ent.text  # Return the first detected crypto

    # If no crypto is found, check for common crypto names using regex
    crypto_pattern = r'\b(BTC|ETH|BNB|XRP|ADA|SOL|MATIC|AVAX|DOT|DOGE|SHIB|USDT|USDC|DAI|SOLANA|SUI)\b'
    matches = re.findall(crypto_pattern, tweet_text.upper())
    return matches[0] if matches else None

def _detect_sentiment(tweet_text):
    """Detect sentiment (bullish, bearish, or neutral) from tweet text."""
    if not tweet_text:
        return "neutral"
    
    # Convert text to lowercase for case-insensitive matching
    tweet_text_lower = tweet_text.lower()
    
    # Bullish keywords
    bullish_keywords = ["bullish", "moon", "🚀", "rocket", "long", "buy", "up", "rise", "growth"]
    # Bearish keywords
    bearish_keywords = ["bearish", "crash", "dump", "😭", "short", "sell", "down", "drop", "fall"]
    
    # Count bullish and bearish keywords
    bullish_count = sum(keyword in tweet_text_lower for keyword in bullish_keywords)
    bearish_count = sum(keyword in tweet_text_lower for keyword in bearish_keywords)
    
    # Determine sentiment
    if bullish_count > bearish_count:
        return "bullish"
    elif bearish_count > bullish_count:
        return "bearish"
    else:
        return "neutral"

def generate_strategy(crypto, sentiment):
    """Generate a strategy using the DeepSeek API"""

    if not crypto:
        return None
    
    # Calculate remaining space for the strategy text
    total_tweet_limit = 280
    custom_link = f"{CUSTOM_STRATEGY_URL}?sentiment={sentiment}&crypto={crypto}"
    link_length = len(" More: ") + len(custom_link)  # Full link length
    remaining_space = total_tweet_limit - PREFIX_LENGTH - link_length

    # Prepare the prompt for DeepSeek
    prompt = f"""
    Provide a {sentiment} DeFi and Yield Farming strategy for {crypto}.
    Include:
    1. Brief description (1 sentence)
    2. Key action (1 step)
    3. Pros and Cons

    Format concisely for Twitter (max {remaining_space} chars, as {link_length} chars are reserved for the link and {PREFIX_LENGTH} chars for the prefix).
    Example format:
    "[Crypto] Strategy: [1-sentence desc]. Action: [key step]. Benefit: [main benefit]. Risk: [level]."

    IMPORTANT: The strategy text must be no longer than {remaining_space} characters, including all punctuation and spaces.
    """
    
    try:
        # Initialize OpenAI client with DeepSeek API
        client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_API_URL
        )
        
        # Call DeepSeek API
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a DeFi and Yield Farming strategy crypo financial expert."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,  # Adjust based on DeepSeek API limits
            temperature=0.7  # Adjust for creativity
        )
        
        # Extract the generated strategy
        strategy = response.choices[0].message.content.strip()
        strategy_with_link = f"{PREFIX}{strategy} More: {custom_link}"

        # Double-check the total length
        if len(strategy_with_link) > 280:
            # If it's still too long, truncate the strategy text further
            max_strategy_length = 280 - PREFIX_LENGTH - link_length
            strategy = strategy[:max_strategy_length] + "..."
            strategy_with_link = f"{PREFIX}{strategy} More: {custom_link}"
        
        return strategy_with_link
    
    except Exception as e:
        print(f"Error generating strategy with DeepSeek API: {e}")
        return None

def get_latest_tweet(tweets: list[Tweet]) -> Tweet | None:
    """Get the latest tweet from a list of tweets."""
    if not tweets:
        print("No tweets found.")
        return None
        
    # Return the first tweet (assumed to be the latest)
    return tweets[0]

def main():
    try:
        # Initialize the Twitter API client
        client = initialize_twitter_client()
    except ValueError as ve:
        print(f"Configuration error: {ve}")
        return
    except tweepy.TweepyException as te:
        print(f"Twitter API error: {te}")
        return
    except Exception as e:
        print(f"Unexpected error: {e}")
        return

    # Load the pre-trained English model
    nlp = spacy.load("en_core_web_sm")

    # Fetch tweets
    tweets = fetch_tweets(client)
    #tweets = MOCK_TWEETS["data"]
    if not tweets:
        print("No tweets found.")
        return
    # Get the latest tweet
    latest_tweet: Tweet | None = get_latest_tweet(tweets)
    if not latest_tweet:
        print("No latest tweet found.")
        return    
    
    # Extract tweet ID and user handle from the latest tweet
    tweet_id = latest_tweet["id"]  # Now safe to access
    user_handle = latest_tweet["author_id"]  # Note: This is the author ID, not the handle
        
    crypto = _detect_cryptos(latest_tweet["text"], nlp)
    sentiment = _detect_sentiment(latest_tweet["text"])

    # Generate strategies for all tweets
    strategy = generate_strategy(crypto, sentiment)
    if not strategy:
        print("No strategies generated.")
        return  
    
    # Reply to tweets with generated strategies
    reply_to_tweet(tweet_id, user_handle, strategy, sentiment, crypto, client)

if __name__ == "__main__":
    main()
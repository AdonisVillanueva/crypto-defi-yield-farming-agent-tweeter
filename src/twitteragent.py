import re
from flask import json
import time
import requests
from requests_oauthlib import OAuth1
import tweepy
from dotenv import load_dotenv
from ratelimit import limits, sleep_and_retry
import os
from datetime import datetime, timedelta
from tweepy import Tweet  # Import the Tweet class
import spacy

# Load environment variables from .env file
load_dotenv()

# Grab credentials from .env
consumer_key = os.getenv("TWITTER_CONSUMER_KEY")
consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET")
access_token = os.getenv("TWITTER_ACCESS_TOKEN")
access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Authenticate with Twitter API
def initialize_twitter_client():
    """
    Initializes and validates the Tweepy Client using environment variables.
    
    Returns:
        tweepy.Client: The initialized Tweepy Client instance.
    
    Raises:
        ValueError: If any required environment variable is missing.
        tweepy.TweepyException: If the client initialization fails.
    """
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
    client = tweepy.Client(
        bearer_token=credentials["BEARER_TOKEN"],
        consumer_key=credentials["consumer_key"],
        consumer_secret=credentials["consumer_secret"],
        access_token=credentials["access_token"],
        access_token_secret=credentials["access_token_secret"]
    )
    
    # Test client initialization
    try:
        user = client.get_me()
        print(f"Client initialized successfully. User: {user.data}")
    except tweepy.TweepyException as e:
        print(f"Error initializing client: {e}")
        raise
    
    return client

try:
    client = initialize_twitter_client()
    # Now you can use `client` for further operations
except ValueError as ve:
    print(f"Configuration error: {ve}")
except tweepy.TweepyException as te:
    print(f"Twitter API error: {te}")
except Exception as e:
    print(f"Unexpected error: {e}")

@sleep_and_retry
@limits(calls=450, period=900)  # 450 calls per 15 minutes
def fetch_tweets():
    """Fetch the latest tweets mentioning @AgentYieldDefi with bullish or bearish sentiment."""
    all_tweets = []
    
    try:
        query = "@AgentYieldDefi (bullish OR bearish OR crash OR rocket OR long) and (strategy OR plan OR game plan OR roadmap)"
        # Fetch tweets from the last 5 minutes
        start_time = (datetime.now() - timedelta(minutes=5)).isoformat() + "Z"
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
    
    except tweepy.TweepyException as e:
        print(f"Error fetching tweets: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    return all_tweets

def reply_to_tweet(tweet_id, user_handle, strategy):
    """Reply to a tweet with the generated strategy."""
    if not strategy:
        print("No strategy provided. Skipping reply.")
        return
    
    # Format the reply text
    reply_text = f"@{user_handle} {strategy}"
    
    # Send the reply
    try:
        client.create_tweet(text=reply_text, in_reply_to_tweet_id=tweet_id)
        print(f"Replied to tweet {tweet_id} by @{user_handle} with strategy: {strategy}")
    except Exception as e:
        print(f"Error replying to tweet: {e}")

def parse_tweet(text):
    """Extract crypto and sentiment from tweet."""
    crypto = _detect_cryptos(text)
    sentiment = _detect_sentiment(text)
    return crypto, sentiment

# Load the pre-trained English model
nlp = spacy.load("en_core_web_sm")

def _detect_cryptos(tweet_text):
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
    
    # If no crypto is found, return None
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


def generate_strategy(tweet):
    """Generate a strategy using the DeepSeek API for a single tweet."""
    if not tweet:
        return None
    
    # Extract tweet text
    tweet_text = tweet.text
    crypto = _detect_cryptos(tweet_text)
    sentiment = _detect_sentiment(tweet_text)
    
    if not crypto:
        return None
    
    # Prepare the prompt for DeepSeek
    prompt = f"""
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
        # Call DeepSeek API
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "prompt": prompt,
            "max_tokens": 150,  # Adjust based on DeepSeek API limits
            "temperature": 0.7  # Adjust for creativity
        }
        response = requests.post(
            "https://api.deepseek.com/v1/completions",  # Replace with actual DeepSeek API endpoint
            headers=headers,
            json=data
        )
        response.raise_for_status()
        
        # Extract the generated strategy
        strategy = response.json().get("choices", [{}])[0].get("text", "").strip()
        return strategy
    
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
    # Fetch tweets
    tweets = fetch_tweets()
    if not tweets:
        print("No tweets found.")
        return
    # Get the latest tweet
    latest_tweet: Tweet | None = get_latest_tweet(tweets)
    if not latest_tweet:
        print("No latest tweet found.")
        return
    
    
    # Extract tweet ID and user handle from the latest tweet
    tweet_id = latest_tweet.id  # Now safe to access
    user_handle = latest_tweet.author_id  # Note: This is the author ID, not the handle
        
    # Generate strategies for all tweets
    strategy = generate_strategy(latest_tweet)
    if not strategy:
        print("No strategies generated.")
        return  
    
    # Reply to tweets with generated strategies
    reply_to_tweet(tweet_id, user_handle, strategy)

if __name__ == "__main__":
    main()
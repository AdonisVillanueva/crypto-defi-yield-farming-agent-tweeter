import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from src.twitteragent import ( 
    _detect_cryptos,
    _detect_sentiment,
    generate_strategy,
    fetch_tweets,
    reply_to_tweet,
    client,  # Twitter API client
    DEEPSEEK_API_KEY,  # DeepSeek API key
)
import spacy

# Mock spaCy model for testing
@pytest.fixture
def mock_nlp(monkeypatch):
    class MockDoc:
        def __init__(self, ents):
            self.ents = ents

    class MockEnt:
        def __init__(self, text, label_):
            self.text = text
            self.label_ = label_

    def mock_nlp(text):
        if "BTC" in text:
            return MockDoc([MockEnt("BTC", "ORG")])
        elif "ETH" in text:
            return MockDoc([MockEnt("ETH", "ORG")])
        elif "SOL" in text:
            return MockDoc([MockEnt("SOL", "ORG")])
        elif "UNKNOWN" in text:
            return MockDoc([MockEnt("UNKNOWN", "ORG")])
        else:
            return MockDoc([])

    monkeypatch.setattr("src.twitteragent.nlp", mock_nlp) 

# Test cases for _detect_cryptos
def test_detect_cryptos_with_btc(mock_nlp):
    tweet_text = "Thinking about going long on BTC and ETH."
    result = _detect_cryptos(tweet_text)
    assert result == "BTC"

def test_detect_cryptos_with_no_crypto(mock_nlp):
    tweet_text = "The weather is nice today."
    result = _detect_cryptos(tweet_text)
    assert result is None

# Test cases for _detect_sentiment
def test_detect_sentiment_bullish():
    tweet_text = "BTC is going to the moon! 🚀"
    result = _detect_sentiment(tweet_text)
    assert result == "bullish"

def test_detect_sentiment_bearish():
    tweet_text = "BTC is crashing hard. 😭"
    result = _detect_sentiment(tweet_text)
    assert result == "bearish"

def test_detect_sentiment_neutral():
    tweet_text = "BTC is stable right now."
    result = _detect_sentiment(tweet_text)
    assert result == "neutral"

# Test cases for generate_strategy
@patch("src.twitteragent.requests.post")  
def test_generate_strategy_success(mock_post):
    # Mock DeepSeek API response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"text": "Strategy: Buy BTC. Action: Long. Benefit: High returns. Risk: 3."}]
    }
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    # Mock tweet
    tweet = MagicMock()
    tweet.text = "BTC is bullish!"

    # Call the function
    result = generate_strategy(tweet)
    assert result == "Strategy: Buy BTC. Action: Long. Benefit: High returns. Risk: 3."

@patch("src.twitteragent.requests.post")
def test_generate_strategy_api_error(mock_post):
    # Mock API error
    mock_post.side_effect = Exception("API error")

    # Mock tweet
    tweet = MagicMock()
    tweet.text = "BTC is bullish!"

    # Call the function
    result = generate_strategy(tweet)
    assert result is None

# Test cases for fetch_tweets
@patch("src.twitteragent.client.search_recent_tweets")
def test_fetch_tweets_success(mock_search):
    # Mock Twitter API response
    mock_response = MagicMock()
    mock_response.data = [MagicMock(text="BTC is bullish!")]
    mock_response.headers = {
        "x-rate-limit-remaining": "450",
        "x-rate-limit-reset": str(int(datetime.now().timestamp()) + 900),
    }
    mock_search.return_value = mock_response

    # Call the function
    result = fetch_tweets()
    assert len(result) == 1
    assert result[0].text == "BTC is bullish!"

@patch("src.twitteragent.client.search_recent_tweets")
def test_fetch_tweets_rate_limit(mock_search):
    # Mock rate limit response
    mock_response = MagicMock()
    mock_response.headers = {
        "x-rate-limit-remaining": "0",
        "x-rate-limit-reset": str(int(datetime.now().timestamp()) + 900),
    }
    mock_search.return_value = mock_response

    # Call the function
    result = fetch_tweets()
    assert len(result) == 0

# Test cases for reply_to_tweet
@patch("src.twitteragent.client.create_tweet")
def test_reply_to_tweet_success(mock_create_tweet):
    # Mock tweet ID and user handle
    tweet_id = "12345"
    user_handle = "CryptoTrader"
    strategy = "Strategy: Buy BTC. Action: Long. Benefit: High returns. Risk: 3."

    # Call the function
    reply_to_tweet(tweet_id, user_handle, strategy)

    # Verify the reply was sent
    mock_create_tweet.assert_called_once_with(
        text=f"@{user_handle} {strategy}\n\nFor more details, visit: https://agentyield.streamlit.app/Custom_Strategy",
        in_reply_to_tweet_id=tweet_id,
    )

@patch("src.twitteragent.client.create_tweet")
def test_reply_to_tweet_no_strategy(mock_create_tweet):
    # Call the function with no strategy
    reply_to_tweet("12345", "CryptoTrader", None)

    # Verify no reply was sent
    mock_create_tweet.assert_not_called() 

nlp = spacy.load("en_core_web_sm")
print("Model loaded successfully!") 
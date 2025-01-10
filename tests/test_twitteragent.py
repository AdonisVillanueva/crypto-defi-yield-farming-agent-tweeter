import pytest
from unittest.mock import MagicMock, patch
from src.twitteragent import initialize_twitter_client, fetch_tweets, reply_to_tweet

# Mock the tweepy.Client to avoid making real API calls
@pytest.fixture
def mock_client():
    return MagicMock()

def test_initialize_twitter_client_success():
    """Test successful initialization of the Twitter client."""
    with patch("tweepy.Client") as mock_tweepy_client:
        mock_client_instance = MagicMock()
        mock_tweepy_client.return_value = mock_client_instance
        client = initialize_twitter_client()
        assert client == mock_client_instance

def test_initialize_twitter_client_failure():
    """Test failure to initialize the Twitter client."""
    with patch("tweepy.Client", side_effect=Exception("API error")):
        with pytest.raises(Exception, match="API error"):
            initialize_twitter_client()

def test_fetch_tweets_success(mock_client):
    """Test successful fetching of tweets."""
    mock_response = MagicMock()
    mock_response.data = ["tweet1", "tweet2"]
    mock_client.search_recent_tweets.return_value = mock_response
    tweets = fetch_tweets(mock_client)
    assert len(tweets) == 2

def test_fetch_tweets_rate_limit(mock_client):
    """Test handling of rate limits when fetching tweets."""
    mock_client.search_recent_tweets.side_effect = Exception("429 Too Many Requests")
    with pytest.raises(Exception, match="429 Too Many Requests"):
        fetch_tweets(mock_client)

def test_reply_to_tweet_success(mock_client):
    """Test successful reply to a tweet."""
    reply_to_tweet(123, "example_user", "Buy BTC", mock_client)
    mock_client.create_tweet.assert_called_once_with(
        text="@example_user Buy BTC",
        in_reply_to_tweet_id=123
    )

def test_reply_to_tweet_failure(mock_client):
    """Test failure to reply to a tweet."""
    mock_client.create_tweet.side_effect = Exception("API error")
    with pytest.raises(Exception, match="API error"):
        reply_to_tweet(123, "example_user", "Buy BTC", mock_client) 
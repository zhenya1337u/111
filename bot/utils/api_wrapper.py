#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API wrapper classes for external services like OpenWeatherMap, Reddit, etc.
"""

import os
import json
import logging
import aiohttp
import asyncio
import random
from urllib.parse import urlencode

logger = logging.getLogger('bot.api_wrapper')

class APIError(Exception):
    """Exception raised for API errors"""
    pass

class BaseAPI:
    """Base class for API wrappers"""
    
    def __init__(self, api_key=None):
        """
        Initialize the API wrapper.
        
        Args:
            api_key (str, optional): API key. If None, tries to get from environment.
        """
        self.session = None
        self.api_key = api_key
    
    async def ensure_session(self):
        """Ensure an aiohttp session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _request(self, method, url, **kwargs):
        """
        Make an HTTP request.
        
        Args:
            method (str): HTTP method (get, post, etc.)
            url (str): URL to request
            **kwargs: Additional arguments for the request
        
        Returns:
            dict: Response JSON
        
        Raises:
            APIError: If the request fails
        """
        session = await self.ensure_session()
        
        try:
            async with session.request(method, url, **kwargs) as response:
                if response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 1))
                    logger.warning(f"Rate limited by API. Retrying after {retry_after} seconds.")
                    await asyncio.sleep(retry_after)
                    return await self._request(method, url, **kwargs)
                
                if response.status >= 400:
                    text = await response.text()
                    logger.error(f"API error ({response.status}): {text}")
                    raise APIError(f"API returned error {response.status}: {text}")
                
                if response.headers.get('Content-Type', '').startswith('application/json'):
                    return await response.json()
                else:
                    return await response.text()
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error: {e}")
            raise APIError(f"HTTP error: {e}")

class OpenWeatherMapAPI(BaseAPI):
    """Wrapper for OpenWeatherMap API"""
    
    def __init__(self, api_key=None):
        """
        Initialize OpenWeatherMap API wrapper.
        
        Args:
            api_key (str, optional): API key. If None, gets from environment.
        """
        super().__init__(api_key or os.environ.get('OPENWEATHERMAP_API_KEY'))
        self.base_url = 'https://api.openweathermap.org/data/2.5'
    
    async def get_current_weather(self, location, units='metric', lang='en'):
        """
        Get current weather for a location.
        
        Args:
            location (str): City name or coordinates
            units (str, optional): Units (metric, imperial, standard). Defaults to 'metric'.
            lang (str, optional): Language code. Defaults to 'en'.
        
        Returns:
            dict: Weather data
        """
        params = {
            'q': location,
            'units': units,
            'lang': lang,
            'appid': self.api_key
        }
        
        # If location is coordinates (lat,lon)
        if ',' in location and all(c.replace('.', '').replace('-', '').isdigit() for c in location.split(',')):
            lat, lon = location.split(',')
            params = {
                'lat': lat.strip(),
                'lon': lon.strip(),
                'units': units,
                'lang': lang,
                'appid': self.api_key
            }
        
        url = f"{self.base_url}/weather?{urlencode(params)}"
        return await self._request('get', url)
    
    async def get_forecast(self, location, units='metric', lang='en'):
        """
        Get 5-day weather forecast for a location.
        
        Args:
            location (str): City name or coordinates
            units (str, optional): Units (metric, imperial, standard). Defaults to 'metric'.
            lang (str, optional): Language code. Defaults to 'en'.
        
        Returns:
            dict: Forecast data
        """
        params = {
            'q': location,
            'units': units,
            'lang': lang,
            'appid': self.api_key
        }
        
        # If location is coordinates (lat,lon)
        if ',' in location and all(c.replace('.', '').replace('-', '').isdigit() for c in location.split(',')):
            lat, lon = location.split(',')
            params = {
                'lat': lat.strip(),
                'lon': lon.strip(),
                'units': units,
                'lang': lang,
                'appid': self.api_key
            }
        
        url = f"{self.base_url}/forecast?{urlencode(params)}"
        return await self._request('get', url)

class RedditAPI(BaseAPI):
    """Wrapper for Reddit API"""
    
    def __init__(self, client_id=None, client_secret=None, user_agent='DiscordBot/1.0'):
        """
        Initialize Reddit API wrapper.
        
        Args:
            client_id (str, optional): Reddit client ID. If None, gets from environment.
            client_secret (str, optional): Reddit client secret. If None, gets from environment.
            user_agent (str, optional): User agent. Defaults to 'DiscordBot/1.0'.
        """
        self.client_id = client_id or os.environ.get('REDDIT_CLIENT_ID')
        self.client_secret = client_secret or os.environ.get('REDDIT_CLIENT_SECRET')
        self.user_agent = user_agent
        self.access_token = None
        self.token_expires_at = 0
        
        super().__init__()
    
    async def _ensure_token(self):
        """Ensure access token is valid, fetching a new one if needed"""
        now = asyncio.get_event_loop().time()
        
        if self.access_token and now < self.token_expires_at:
            return
        
        session = await self.ensure_session()
        
        auth = aiohttp.BasicAuth(self.client_id, self.client_secret)
        headers = {'User-Agent': self.user_agent}
        data = {'grant_type': 'client_credentials'}
        
        try:
            async with session.post(
                'https://www.reddit.com/api/v1/access_token',
                auth=auth,
                headers=headers,
                data=data
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    logger.error(f"Reddit auth error ({response.status}): {text}")
                    raise APIError(f"Reddit auth error {response.status}: {text}")
                
                token_data = await response.json()
                self.access_token = token_data['access_token']
                self.token_expires_at = now + token_data['expires_in'] - 60  # Refresh 60s before expiry
        except aiohttp.ClientError as e:
            logger.error(f"Reddit auth error: {e}")
            raise APIError(f"Reddit auth error: {e}")
    
    async def _request(self, method, url, **kwargs):
        """Make an authenticated request to Reddit API"""
        await self._ensure_token()
        
        # Add headers
        headers = kwargs.get('headers', {})
        headers.update({
            'User-Agent': self.user_agent,
            'Authorization': f'Bearer {self.access_token}'
        })
        kwargs['headers'] = headers
        
        return await super()._request(method, url, **kwargs)
    
    async def get_memes(self, subreddit='memes', limit=25):
        """
        Get memes from a subreddit.
        
        Args:
            subreddit (str, optional): Subreddit name. Defaults to 'memes'.
            limit (int, optional): Number of posts to fetch. Defaults to 25.
        
        Returns:
            list: List of meme posts
        """
        url = f"https://oauth.reddit.com/r/{subreddit}/hot.json?limit={limit}"
        data = await self._request('get', url)
        
        # Extract relevant post data
        posts = []
        for post in data['data']['children']:
            post_data = post['data']
            if post_data.get('post_hint') == 'image' or post_data.get('url', '').endswith(('.jpg', '.jpeg', '.png', '.gif')):
                posts.append({
                    'title': post_data['title'],
                    'url': post_data['url'],
                    'permalink': f"https://reddit.com{post_data['permalink']}",
                    'score': post_data['score'],
                    'author': post_data['author'],
                    'created_utc': post_data['created_utc'],
                    'is_video': post_data.get('is_video', False),
                    'over_18': post_data.get('over_18', False)
                })
        
        return posts
    
    async def get_random_meme(self, subreddit='memes', allow_nsfw=False):
        """
        Get a random meme from a subreddit.
        
        Args:
            subreddit (str, optional): Subreddit name. Defaults to 'memes'.
            allow_nsfw (bool, optional): Whether to allow NSFW posts. Defaults to False.
        
        Returns:
            dict: Meme post data
        """
        memes = await self.get_memes(subreddit)
        
        # Filter out NSFW if not allowed
        if not allow_nsfw:
            memes = [m for m in memes if not m['over_18']]
        
        if not memes:
            return None
        
        return random.choice(memes)

class YouTubeAPI(BaseAPI):
    """Wrapper for YouTube Data API"""
    
    def __init__(self, api_key=None):
        """
        Initialize YouTube API wrapper.
        
        Args:
            api_key (str, optional): API key. If None, gets from environment.
        """
        super().__init__(api_key or os.environ.get('YOUTUBE_API_KEY'))
        self.base_url = 'https://www.googleapis.com/youtube/v3'
    
    async def search_videos(self, query, max_results=5):
        """
        Search for videos.
        
        Args:
            query (str): Search query
            max_results (int, optional): Maximum number of results. Defaults to 5.
        
        Returns:
            list: Video search results
        """
        params = {
            'part': 'snippet',
            'type': 'video',
            'q': query,
            'maxResults': max_results,
            'key': self.api_key
        }
        
        url = f"{self.base_url}/search?{urlencode(params)}"
        data = await self._request('get', url)
        
        videos = []
        for item in data.get('items', []):
            videos.append({
                'id': item['id']['videoId'],
                'title': item['snippet']['title'],
                'description': item['snippet']['description'],
                'thumbnail': item['snippet']['thumbnails']['high']['url'],
                'channel': item['snippet']['channelTitle'],
                'published_at': item['snippet']['publishedAt'],
                'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}"
            })
        
        return videos
    
    async def get_video_details(self, video_id):
        """
        Get details for a specific video.
        
        Args:
            video_id (str): YouTube video ID
        
        Returns:
            dict: Video details
        """
        params = {
            'part': 'snippet,contentDetails,statistics',
            'id': video_id,
            'key': self.api_key
        }
        
        url = f"{self.base_url}/videos?{urlencode(params)}"
        data = await self._request('get', url)
        
        if not data.get('items'):
            return None
        
        item = data['items'][0]
        return {
            'id': item['id'],
            'title': item['snippet']['title'],
            'description': item['snippet']['description'],
            'thumbnail': item['snippet']['thumbnails']['high']['url'],
            'channel': item['snippet']['channelTitle'],
            'published_at': item['snippet']['publishedAt'],
            'duration': item['contentDetails']['duration'],
            'views': item['statistics']['viewCount'],
            'likes': item['statistics'].get('likeCount', 0),
            'url': f"https://www.youtube.com/watch?v={item['id']}"
        }

class GrokAPI(BaseAPI):
    """Wrapper for Grok (xAI) API"""
    
    def __init__(self, api_key=None):
        """
        Initialize Grok API wrapper.
        
        Args:
            api_key (str, optional): API key. If None, gets from environment.
        """
        super().__init__(api_key or os.environ.get('GROK_API_KEY'))
        self.base_url = 'https://api.grok.x.ai/v1'
    
    async def generate_response(self, prompt, system_message=None, max_tokens=1000):
        """
        Generate a response from Grok AI.
        
        Args:
            prompt (str): User prompt
            system_message (str, optional): System message/instructions
            max_tokens (int, optional): Maximum tokens to generate. Defaults to 1000.
        
        Returns:
            str: Generated response
        """
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "top_p": 0.9
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}/chat/completions"
        try:
            data = await self._request('post', url, json=payload, headers=headers)
            if 'choices' in data and data['choices']:
                return data['choices'][0]['message']['content']
            return "Sorry, I couldn't generate a response."
        except APIError as e:
            logger.error(f"Grok API error: {e}")
            return f"Sorry, there was an error: {e}"

# Factory function to get API instances
def get_api(api_name):
    """
    Get an API wrapper instance.
    
    Args:
        api_name (str): API name (openweathermap, reddit, youtube, grok)
    
    Returns:
        BaseAPI: API wrapper instance
    """
    api_name = api_name.lower()
    
    if api_name == 'openweathermap':
        return OpenWeatherMapAPI()
    elif api_name == 'reddit':
        return RedditAPI()
    elif api_name == 'youtube':
        return YouTubeAPI()
    elif api_name == 'grok':
        return GrokAPI()
    
    raise ValueError(f"Unknown API: {api_name}")

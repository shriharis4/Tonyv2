from typing import Literal
import os
import asyncio
import aiohttp
import webbrowser
from livekit.agents import function_tool
import logging
logger = logging.getLogger(__name__)
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

@function_tool()
async def play_media(media_name: str, media_type: Literal["song", "video"] = "song") -> str:
    """
    Plays a specific song or video on YouTube.
    USE THIS TOOL when the user asks to play a specific song, artist, or video by name.
    
    Args:
        media_name: Name of song/video to search and play
        media_type: Content type (default: "song")
    """
    try:
        print(f"🎵 Playing media: {media_name} (type: {media_type})")
        
        if YOUTUBE_API_KEY:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={media_name}&type=video&key={YOUTUBE_API_KEY}",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    data = await response.json()
            
            if data.get('items'):
                video = data['items'][0]
                await asyncio.create_task(asyncio.to_thread(webbrowser.open, f"https://www.youtube.com/watch?v={video['id']['videoId']}"))
                return f"🎵 अब बज रहा है: {video['snippet']['title']}"

        # FAST Fallback: Scrape the first real video ID without API key.
        import urllib.request
        import urllib.parse
        import re

        query_string = urllib.parse.urlencode({"search_query": media_name})
        req = urllib.request.Request(
            "https://www.youtube.com/results?" + query_string,
            headers={"User-Agent": "Mozilla/5.0"},  # avoid consent/alt layouts
        )
        html_content = await asyncio.to_thread(urllib.request.urlopen, req)
        html_text = await asyncio.to_thread(html_content.read)
        html_text = html_text.decode("utf-8", errors="ignore")

        # Prefer the structured videoId from YouTube's embedded JSON (the
        # genuine top video result), falling back to the raw watch-link
        # regex. De-duplicate so we take the first UNIQUE id, skipping
        # repeated thumbnail/preview references to the same clip.
        video_id = None
        json_ids = re.findall(r'"videoId":"([\w-]{11})"', html_text)
        if json_ids:
            video_id = json_ids[0]
        else:
            link_ids = re.findall(r"/watch\?v=([\w-]{11})", html_text)
            if link_ids:
                video_id = link_ids[0]

        if video_id:
            # Direct watch URL auto-plays the top result — no UI automation
            # needed, which keeps latency low and avoids the "shows but
            # doesn't play" problem.
            await asyncio.to_thread(webbrowser.open, f"https://www.youtube.com/watch?v={video_id}")
            return f"🎵 YouTube पर '{media_name}' बज रहा है..."

        await asyncio.to_thread(webbrowser.open, f"https://www.youtube.com/results?search_query={urllib.parse.quote(media_name)}")
        return f"YouTube पर '{media_name}' खोल रहा हूँ..."
    except Exception as e:
        logger.error(f"मीडिया त्रुटि: {e}")
        return f"❌ मीडिया चलाने में समस्या आई: {str(e)}"

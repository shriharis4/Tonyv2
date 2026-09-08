import pyautogui
import time
import subprocess
import os
from livekit.agents import function_tool
import pygetwindow as gw

# ==================== SPOTIFY CONTROL ====================

@function_tool()
async def open_spotify() -> str:
    """Open Spotify application"""
    try:
        # Method 1: Check if already running (loose match)
        spotify_windows = [w for w in gw.getAllWindows() if 'spotify' in w.title.lower()]
        if spotify_windows:
            spotify_windows[0].activate()
            time.sleep(1)
            return "✅ Spotify already open, brought to foreground."
        
        # Method 2: Use Windows Start Menu search
        print(f"🚀 Opening app: spotify")
        original_pos = pyautogui.position()

        # Step 1: Press Win key to open start menu
        pyautogui.press('win')
        time.sleep(1)

        # Step 2: Type app name
        pyautogui.typewrite("spotify", interval=0.1)
        time.sleep(1)

        # Step 3: Press Enter to open the app
        pyautogui.press('enter')
        
        # Return to original position
        pyautogui.moveTo(original_pos.x, original_pos.y, duration=0.1)
        
        time.sleep(3)  # Wait for Spotify to open
        return "✅ Spotify opened successfully."

    except Exception as e:
        return f"❌ Error opening Spotify: {str(e)}"

@function_tool()
async def spotify_play() -> str:
    """Play or resume Spotify music"""
    try:
        # Check if Spotify is open (loose match)
        spotify_windows = [w for w in gw.getAllWindows() if 'spotify' in w.title.lower()]
        
        if not spotify_windows:
            # Open Spotify first
            result = await open_spotify()
            if "✅" not in result:
                return result
            time.sleep(3)
        else:
            # Activate Spotify window if found
            spotify_windows[0].activate()
            time.sleep(0.5)
        
        # Press space to play/pause
        pyautogui.press('space')
        return "▶️ Playing Spotify"
        
    except Exception as e:
        return f"❌ Error: {str(e)}"

@function_tool()
async def spotify_pause() -> str:
    """Pause Spotify music"""
    try:
        # Check if Spotify is open (loose match)
        spotify_windows = [w for w in gw.getAllWindows() if 'spotify' in w.title.lower()]
        
        if not spotify_windows:
            return "❌ Spotify not open. Say 'open spotify' first."
        
        # Activate and pause
        spotify_windows[0].activate()
        time.sleep(0.5)
        pyautogui.press('space')
        return "⏸️ Spotify paused"
        
    except Exception as e:
        return f"❌ Error: {str(e)}"

@function_tool()
async def spotify_next() -> str:
    """Next track in Spotify"""
    try:
        # Check if Spotify is open (loose match)
        spotify_windows = [w for w in gw.getAllWindows() if 'spotify' in w.title.lower()]
        
        if not spotify_windows:
            # Don't open automatically for next/previous
            # Just try the keyboard shortcut (might work if Spotify is in background)
            pyautogui.hotkey('ctrl', 'right')
            return "⏭️ Next track (sent keyboard shortcut)"
        
        # Activate and send next command
        spotify_windows[0].activate()
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'right')
        return "⏭️ Next track"
        
    except Exception as e:
        return f"❌ Error: {str(e)}"

@function_tool()
async def spotify_previous() -> str:
    """Previous track in Spotify"""
    try:
        # Check if Spotify is open (loose match)
        spotify_windows = [w for w in gw.getAllWindows() if 'spotify' in w.title.lower()]
        
        if not spotify_windows:
            # Don't open automatically for next/previous
            # Just try the keyboard shortcut
            pyautogui.hotkey('ctrl', 'left')
            return "⏮️ Previous track (sent keyboard shortcut)"
        
        # Activate and send previous command
        spotify_windows[0].activate()
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'left')
        return "⏮️ Previous track"
        
    except Exception as e:
        return f"❌ Error: {str(e)}"

@function_tool()
async def spotify_play_song(song_name: str) -> str:
    """Search and play a specific song on Spotify"""
    try:
        # Check if Spotify is open (loose match)
        spotify_windows = [w for w in gw.getAllWindows() if 'spotify' in w.title.lower()]
        
        if not spotify_windows:
            # Open Spotify first
            result = await open_spotify()
            if "✅" not in result:
                return result
            time.sleep(3)
            
            # Get window again after opening
            spotify_windows = [w for w in gw.getAllWindows() if 'spotify' in w.title.lower()]
        
        if spotify_windows:
            spotify_windows[0].activate()
            time.sleep(1)
            
            # Search for song (Ctrl + L)
            pyautogui.hotkey('ctrl', 'l')
            time.sleep(0.5)
            
            # Clear and type song name
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.press('delete')
            pyautogui.write(song_name, interval=0.05)
            time.sleep(1)
            
            # Select first result
            pyautogui.press('enter')
            time.sleep(2)
            
            # Play the song
            pyautogui.press('space')
            
            return f"🎵 Playing: {song_name}"
        
        return "❌ Could not open Spotify"
        
    except Exception as e:
        return f"❌ Error: {str(e)}"

@function_tool()
async def spotify_play_liked() -> str:
    """Play Liked Songs playlist"""
    try:
        # Check if Spotify is open (loose match)
        spotify_windows = [w for w in gw.getAllWindows() if 'spotify' in w.title.lower()]
        
        if not spotify_windows:
            # Open Spotify first
            result = await open_spotify()
            if "✅" not in result:
                return result
            time.sleep(3)
            
            # Get window again after opening
            spotify_windows = [w for w in gw.getAllWindows() if 'spotify' in w.title.lower()]
        
        if spotify_windows:
            spotify_windows[0].activate()
            time.sleep(1)
            
            # Search for Liked Songs
            pyautogui.hotkey('ctrl', 'l')
            time.sleep(0.5)
            pyautogui.write("Liked Songs")
            time.sleep(1)
            pyautogui.press('enter')
            time.sleep(2)
            pyautogui.press('space')
            
            return "❤️ Playing Liked Songs"
        
        return "❌ Spotify not open"
        
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ==
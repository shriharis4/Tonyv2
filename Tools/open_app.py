from livekit.agents import function_tool
import pyautogui
import asyncio
import os
import subprocess

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

@function_tool()
async def open_app(app_name: str) -> str:
    """
    Launches applications via direct OS execution, AppID search, or fast Start Menu search.
    
    Args:
        app_name: Application name (e.g., "chrome")
        
    Returns:
        str: Launch confirmation or error
    """
    try:
        name = app_name.strip().lower()
        print(f"🚀 app open request: {name}")
        
        # 1. Try Direct Protocol / Shell Launch
        launched = False
        if name in ["settings", "ms-settings", "open settings"]:
            os.startfile("ms-settings:")
            launched = True
        elif name == "spotify":
            try:
                os.startfile("spotify:")
                launched = True
            except:
                pass
        elif name == "whatsapp":
            try:
                os.startfile("whatsapp:")
                launched = True
            except:
                pass
        
        if not launched:
            app_map = {
                "chrome": "chrome",
                "google chrome": "chrome",
                "browser": "chrome",
                "notepad": "notepad",
                "calculator": "calc",
                "vs code": "code",
                "vscode": "code",
                "file explorer": "explorer",
                "explorer": "explorer",
                "task manager": "taskmgr",
                "taskmanager": "taskmgr",
                "word": "winword",
                "excel": "excel",
                "powerpoint": "powerpnt",
                "paint": "mspaint",
            }
            if name in app_map:
                cmd = app_map[name]
                subprocess.Popen(f"start {cmd}", shell=True)
                launched = True
                
        # 2. Try AppID lookup using Get-StartApps
        if not launched:
            try:
                ps_cmd = f'Get-StartApps | Where-Object {{ $_.Name -like "*{name}*" }} | Select-Object -ExpandProperty AppID -First 1'
                result = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    appid = result.stdout.strip()
                    if appid:
                        print(f"🔍 Found AppID for '{name}': {appid}")
                        subprocess.Popen(f"explorer.exe shell:AppsFolder\\{appid}", shell=True)
                        launched = True
            except Exception as e:
                print(f"⚠️ AppID search failed: {e}")
        
        if launched:
            return f"✅ '{app_name}' has been launched."

    except Exception as e:
        print(f"⚠️ Direct launch failed: {e}. Falling back to Start Menu search.")

    # 3. Fallback: Fast Windows Start Menu search using PyAutoGUI
    try:
        print(f"🔍 Falling back to fast Start Menu search for: {app_name}")
        original_pos = await asyncio.to_thread(pyautogui.position)

        # Press Win key to open start menu
        await asyncio.to_thread(pyautogui.press, 'win')
        await asyncio.sleep(0.2)

        # Type app name quickly
        await asyncio.to_thread(pyautogui.typewrite, app_name, interval=0.02)
        await asyncio.sleep(0.2)

        # Press Enter to open the app
        await asyncio.to_thread(pyautogui.press, 'enter')

        return f"✅ '{app_name}' has been launched."

    except Exception as e:
        return f"❌ Error launching app: {str(e)}"

    finally:
        try:
            await asyncio.to_thread(pyautogui.moveTo, original_pos.x, original_pos.y, duration=0.05)
        except:
            pass


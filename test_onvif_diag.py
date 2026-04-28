import asyncio
import sys
import os

# Add current directory to path so we can import onvif_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from onvif_utils import get_onvif_rtsp_url
    from onvif import ONVIFCamera
    print("[SUCCESS] ONVIF Library imported successfully.")
except ImportError as e:
    print(f"[ERROR] Could not import libraries: {e}")
    sys.exit(1)

async def diagnostic():
    print("\n--- SENTINEL ONVIF DIAGNOSTIC TOOL ---")
    print("This script will check if your IP camera is responding to ONVIF commands.\n")
    
    ip = input("Enter Camera IP (e.g. 192.168.1.100): ").strip()
    port = input("Enter ONVIF Port (default 80): ").strip() or "80"
    user = input("Enter Username (default admin): ").strip() or "admin"
    password = input("Enter Password: ").strip()
    
    print(f"\n[STEP 1] Connecting to {ip}:{port}...")
    try:
        # Basic connection test
        cam = ONVIFCamera(ip, int(port), user, password)
        print("[OK] Connected to Camera object.")
        
        print("[STEP 2] Fetching Device Information...")
        dev_info = await cam.devicemgmt.GetDeviceInformation()
        print(f"Manufacturer: {dev_info.Manufacturer}")
        print(f"Model: {dev_info.Model}")
        print(f"Firmware: {dev_info.FirmwareVersion}")
        
        print("\n[STEP 3] Fetching RTSP Stream URL...")
        rtsp_url = await get_onvif_rtsp_url(ip, int(port), user, password)
        
        if rtsp_url:
            print(f"\n[SUCCESS] Found Stream URL: {rtsp_url}")
            print("\nYou can now use this IP in the Sentinel Dashboard with 'ONVIF Auto-Discovery' enabled.")
        else:
            print("\n[FAILED] Could not retrieve RTSP URL. The camera might not support standard Media service or credentials might be wrong.")
            
    except Exception as e:
        print(f"\n[FATAL ERROR] Connection failed: {e}")
        print("\nSuggestions:")
        print("1. Check if the IP address is correct and reachable (ping it).")
        print("2. Verify the ONVIF port (some cameras use 80, 8080, 888, or 5000).")
        print("3. Ensure 'ONVIF' is enabled in your camera's internal web settings.")
        print("4. Double check the password.")

if __name__ == "__main__":
    try:
        asyncio.run(diagnostic())
    except KeyboardInterrupt:
        print("\nExiting...")

import socket
import asyncio
import sys
import cv2
from onvif_utils import get_onvif_rtsp_url

COMMON_PORTS = [80, 554, 8000, 8080, 888, 37777, 5000]

BRANDS = {
    "1": {"name": "Hikvision", "template": "rtsp://{user}:{pass}@{ip}:554/Streaming/Channels/101"},
    "2": {"name": "CP Plus / Dahua", "template": "rtsp://{user}:{pass}@{ip}:554/cam/realmonitor?channel=1&subtype=0"},
    "3": {"name": "XMeye / Generic Chinese", "template": "rtsp://{user}:{pass}@{ip}:554/user={user}&password={pass}&channel=1&stream=0.sdp"},
    "4": {"name": "Honeywell", "template": "rtsp://{user}:{pass}@{ip}:554/h264"},
    "5": {"name": "Sony", "template": "rtsp://{user}:{pass}@{ip}:554/media/video1"},
    "6": {"name": "Use ONVIF Auto-Discovery (Best for unknown brands)", "template": "AUTO"}
}

def scan_ports(ip):
    print(f"\n[SCAN] Scanning {ip} for common CCTV ports...")
    open_ports = []
    for port in COMMON_PORTS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            if s.connect_ex((ip, port)) == 0:
                print(f"  [+] Port {port} is OPEN")
                open_ports.append(port)
    return open_ports

async def main():
    print("="*50)
    print("       SENTINEL CCTV FINDER & URL GENERATOR")
    print("="*50)

    ip = input("\nEnter Camera IP Address: ").strip()
    if not ip: return

    open_ports = scan_ports(ip)
    if not open_ports:
        print("[!] Warning: No common ports found. Make sure the IP is correct and camera is powered on.")

    print("\nSelect Camera Brand:")
    for key, val in BRANDS.items():
        print(f"{key}. {val['name']}")
    
    choice = input("\nChoice (1-6): ").strip()
    brand = BRANDS.get(choice)
    
    if not brand:
        print("Invalid Choice.")
        return

    user = input("Username (default admin): ").strip() or "admin"
    password = input("Password: ").strip()

    final_url = ""

    if brand["template"] == "AUTO":
        port = input("Enter ONVIF Port (default 80): ").strip() or "80"
        print("\n[ONVIF] Attempting to fetch URL automatically...")
        final_url = await get_onvif_rtsp_url(ip, int(port), user, password)
    else:
        # Use template
        final_url = brand["template"].format(ip=ip, user=user, **{"pass": password})

    if not final_url:
        print("\n[ERROR] Could not generate URL. Please check credentials or try ONVIF mode.")
        return

    print(f"\n[GENERATED URL]: {final_url}")
    
    verify = input("\nDo you want to test this stream? (y/n): ").lower()
    if verify == 'y':
        print("[TEST] Attempting to open stream with OpenCV...")
        cap = cv2.VideoCapture(final_url)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print("[SUCCESS] Stream is ACTIVE and readable!")
                cv2.imshow("Sentinel CCTV Preview", frame)
                print("Press any key on the video window to close.")
                cv2.waitKey(0)
                cv2.destroyAllWindows()
            else:
                print("[FAILED] Connected to stream, but could not read frames.")
        else:
            print("[FAILED] Could not open stream. Check URL or network.")
        cap.release()

    # --- NEW: AUTO-CONNECT LOGIC ---
    connect = input("\nDo you want to APPLY this URL to Sentinel Dashboard and connect now? (y/n): ").lower()
    if connect == 'y':
        owner_id = input("Enter your Owner ID (default 1): ").strip() or "1"
        api_url = input("Enter API Base URL (default http://localhost:8000): ").strip() or "http://localhost:8000"
        
        print(f"[API] Sending protocol to {api_url}...")
        try:
            import httpx
            payload = {
                "name": "Gym_Camera",
                "url": final_url,
                "owner_id": int(owner_id),
                "use_p2p": False,
                "use_onvif": False 
            }
            with httpx.Client() as client:
                response = client.post(f"{api_url}/api/nodes/add", json=payload)
                if response.status_code == 200:
                    print("[SUCCESS] Camera connected to Sentinel Engine successfully!")
                else:
                    print(f"[ERROR] API returned error: {response.text}")
        except Exception as e:
            print(f"[ERROR] Could not connect to API: {e}")

    print("\n[FINISH] Script completed.")

if __name__ == "__main__":
    asyncio.run(main())

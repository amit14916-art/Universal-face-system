import asyncio
from onvif import ONVIFCamera
import logging

logger = logging.getLogger("ONVIF-Utils")

async def get_onvif_rtsp_url(ip, port, user, password):
    """
    Connects to an ONVIF camera and retrieves the primary RTSP stream URL.
    """
    try:
        # Default ONVIF port is usually 80 or 8080 or 888
        cam = ONVIFCamera(ip, port, user, password)
        
        # Create media service
        media = await cam.create_media_service()
        
        # Get profiles
        profiles = await media.GetProfiles()
        if not profiles:
            return None
            
        # Get the first profile (usually the highest resolution)
        profile_token = profiles[0].token
        
        # Get stream URI
        obj = await media.GetStreamUri({
            'StreamSetup': {
                'Stream': 'RTP-Unicast',
                'Transport': {'Protocol': 'RTSP'}
            },
            'ProfileToken': profile_token
        })
        
        rtsp_url = obj.Uri
        
        # Some cameras return URL without credentials, we might need to inject them
        if user and password and "@" not in rtsp_url:
            # Example: rtsp://192.168.1.100/stream -> rtsp://user:pass@192.168.1.100/stream
            prefix = "rtsp://"
            if rtsp_url.startswith(prefix):
                rtsp_url = f"rtsp://{user}:{password}@{rtsp_url[len(prefix):]}"
        
        return rtsp_url
    except Exception as e:
        logger.error(f"ONVIF Error for {ip}: {e}")
        return None

if __name__ == "__main__":
    # Test stub (for local testing if you have a camera)
    # asyncio.run(get_onvif_rtsp_url("192.168.1.10", 80, "admin", "12345"))
    pass

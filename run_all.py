import os
import threading
import time
import cv2
import uvicorn
from api import app
import main as engine

def run_api_server():
    print(">> Starting API and Dashboard...")
    # Run uvicorn in this thread (shares memory with main thread!)
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="error")
    server = uvicorn.Server(config)
    server.run()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("========================================")
    print("   UNIVERSAL FACE SYSTEM - READY")
    print("========================================")
    print("Dashboard: http://localhost:8000")
    print("OpenCV Windows will appear automatically.")
    print("Press 'q' inside any camera window to stop.")
    print("----------------------------------------")

    # Start API in background thread
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()

    # Wait for API to initialize the engine and database
    time.sleep(3)
    
    # Run OpenCV GUI in the MAIN thread
    try:
        while True:
            has_active_nodes = False
            for name, node in list(engine.global_nodes.items()):
                if node.running:
                    has_active_nodes = True
                    if node.last_frame is not None:
                        cv2.imshow(f"Sentinel AI: {name}", node.last_frame)
            
            if not has_active_nodes:
                time.sleep(0.5)
                continue
                
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Shutdown requested...")
                break
                
            time.sleep(0.03)
            
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        for node in engine.global_nodes.values():
            node.stop()
        os._exit(0) # Force clean exit to kill Uvicorn background thread

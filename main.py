import cv2
import asyncio
import numpy as np

from database import init_db
import face_service

async def process_frame(frame: np.ndarray):
    """
    Main loop logic utilizing the cleanly separated match checks.
    """
    face_locations, face_encodings = await face_service.get_face_embeddings(frame)
    if not face_encodings:
        return frame
        
    face_names = []
    
    for encoding in face_encodings:
        # Database check for known encoding
        face_id, name = await face_service.match_face(encoding)
        
        if face_id is not None:
            print(f"✅ Access Granted: {name}")
            face_names.append(name)
        else:
            # Register unknown to DB if it doesn't match
            await face_service.register_new_face("Unknown_ID", "Unknown", encoding)
            face_names.append("Unknown_ID")
            
    # Draw physical boxes on frame
    frame = face_service.draw_metadata(frame, face_locations, face_names)
    return frame

async def capture_loop():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    print("Started face capture loop. Press 'q' to stop.")
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to capture frame.")
                break
                
            frame = await process_frame(frame)
            cv2.imshow('Universal Face System', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
            await asyncio.sleep(0.01) 
            
    except KeyboardInterrupt:
        pass
    finally:
        print("Stopping capture loop...")
        cap.release()
        cv2.destroyAllWindows()

async def main():
    await init_db()
    await capture_loop()

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program shut down.")

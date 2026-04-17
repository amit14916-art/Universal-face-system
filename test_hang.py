import sys
print("Starting...", flush=True)
try:
    import database
    print("DB imported", flush=True)
    import face_service
    print("Face Service imported", flush=True)
    from deep_sort_realtime.deepsort_tracker import DeepSort
    print("DeepSort imported", flush=True)
    print("All good!", flush=True)
except Exception as e:
    print("Error:", e, flush=True)

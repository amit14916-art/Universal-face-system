import cv2
import sys

url = "http://10.115.83.118:8080/video"
cap = cv2.VideoCapture(url)

if not cap.isOpened():
    print("Could not open stream.")
    sys.exit(1)

ret, frame = cap.read()
if ret:
    cv2.imwrite("phone_test.jpg", frame)
    print("Successfully captured phone_test.jpg")
else:
    print("Connected but could not read frame.")

cap.release()

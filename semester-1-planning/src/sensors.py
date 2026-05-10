import os, time, json, cv2, numpy as np
import carla
import torch
from ultralytics import YOLO

# ---------- Settings ----------
KEEP = {0, 1, 2, 3, 5, 7}          # person, bicycle, car, motorcycle, bus, truck
MODEL = "yolov8n.pt"               # use 'yolov8s.pt' if you have headroom
IMG_W, IMG_H = 640, 360
CAMERA_FPS = 30                    # reduce CARLA frame rate
CONF_TH = 0.45
SHOW_WINDOW = True                # turn on only if needed
OUT_DIR = "out/live"
# ------------------------------

os.makedirs(OUT_DIR, exist_ok=True)

# ---------- GPU Setup ----------
DEVICE = "cuda:0"
print(f"Running YOLO on {DEVICE}")

model = YOLO(MODEL).to(DEVICE)
torch.backends.cudnn.benchmark = True

# ---------- Helper ----------
def to_bgr(image):
    arr = np.frombuffer(image.raw_data, dtype=np.uint8)
    arr = arr.reshape((image.height, image.width, 4))
    return arr[:, :, :3]  # BGR

# ---------- Main ----------
def main():
    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    bp = world.get_blueprint_library()

    # Ego vehicle
    veh_bp = bp.filter('vehicle.*model3*')[0]
    spawn = np.random.choice(world.get_map().get_spawn_points())
    vehicle = world.spawn_actor(veh_bp, spawn)
    vehicle.set_autopilot(True)

    # Camera
    cam_bp = bp.find('sensor.camera.rgb')
    cam_bp.set_attribute("image_size_x", str(IMG_W))
    cam_bp.set_attribute("image_size_y", str(IMG_H))
    cam_bp.set_attribute("sensor_tick", f"{1.0 / CAMERA_FPS}")  # limit FPS
    cam_tf = carla.Transform(carla.Location(x=1.5, z=2.2))
    camera = world.spawn_actor(cam_bp, cam_tf, attach_to=vehicle)

    print("Streaming… press Ctrl+C to stop.")

    def on_frame(image):
        frame = to_bgr(image).copy()
        # YOLO inference on GPU
        r = model.predict(
            source=frame,
            imgsz=max(IMG_W, IMG_H),
            conf=CONF_TH,
            device=DEVICE,
            half=DEVICE.startswith("cuda"),   # <— enable FP16 safely here
            verbose=False
        )[0]

        # Collect boxes
        boxes_json = []
        for b in r.boxes:
            cls = int(b.cls)
            if cls not in KEEP: continue
            x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())
            conf = float(b.conf[0])
            boxes_json.append({"cls": cls, "conf": conf, "xyxy": [x1, y1, x2, y2]})
            if SHOW_WINDOW:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"{r.names[cls]} {conf:.2f}",
                            (x1, max(10, y1 - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # Optional live window
        if SHOW_WINDOW:
            cv2.imshow("CARLA Live YOLO", frame)
            cv2.waitKey(1)

        # Save JSON (every frame or every Nth)
        with open(f"{OUT_DIR}/{image.frame:06d}.json", "w") as f:
            json.dump({"frame": int(image.frame), "boxes": boxes_json}, f)

    camera.listen(on_frame)

    try:
        while True:
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        camera.stop()
        camera.destroy()
        vehicle.destroy()
        if SHOW_WINDOW:
            cv2.destroyAllWindows()
        print("Clean shutdown.")

if __name__ == "__main__":
    main()

import sys
import json
import cv2
import numpy as np
import os

def process_video(video_in, json_in, video_out):
    if not os.path.exists(video_in):
        print(f"Error: {video_in} not found.")
        return
    if not os.path.exists(json_in):
        print(f"Error: {json_in} not found.")
        return

    with open(json_in, 'r') as f:
        events = json.load(f)

    # Separate events
    clicks = [e for e in events if e.get('type') == 'click']
    moves = [e for e in events if e.get('type') == 'move']

    cap = cv2.VideoCapture(video_in)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0 or np.isnan(fps):
        fps = 30.0
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # FourCC for mp4
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_out, fourcc, fps, (width, height))

    # State variables
    is_zoomed = False
    
    # Target variables (what we want to reach)
    target_scale = 1.0 # 1.0 = full screen, 2.0 = zoomed 2x
    # Center of target window. Initialize at center
    target_cx = width / 2
    target_cy = height / 2

    # Current smoothed variables
    curr_scale = 1.0
    curr_cx = width / 2
    curr_cy = height / 2

    # Smoothing factors
    # Exponential moving average (smaller = slower/smoother)
    smooth_scale = 0.1
    smooth_pos = 0.15

    # Helper function to get event state at time t
    def get_latest_event_before(event_list, t):
        valid = [e for e in event_list if e['t'] <= t]
        return valid[-1] if valid else None

    print(f"Processing {video_in} -> {video_out} at {fps} fps ({width}x{height})")
    
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Time in ms
        t = (frame_idx / fps) * 1000.0

        latest_click = get_latest_event_before(clicks, t)
        latest_move = get_latest_event_before(moves, t)
        
        last_click_t = latest_click['t'] if latest_click else -9999
        last_move_t = latest_move['t'] if latest_move else -9999
        
        last_activity_t = max(last_click_t, last_move_t)

        # Logic for target_scale
        # Enter zoom if we clicked recently (and haven't idled out since)
        if latest_click and t >= last_click_t:
            # Did we idle since the last click?
            if t - last_activity_t > 500:
                is_zoomed = False
            else:
                is_zoomed = True

        target_scale = 2.0 if is_zoomed else 1.0
        
        # Position logic
        if latest_move:
            target_cx = latest_move['x']
            target_cy = latest_move['y']
        
        # Update current values via EMA
        curr_scale += (target_scale - curr_scale) * smooth_scale
        curr_cx += (target_cx - curr_cx) * smooth_pos
        curr_cy += (target_cy - curr_cy) * smooth_pos

        # Calculate crop boundaries
        crop_w = width / curr_scale
        crop_h = height / curr_scale

        # If not zoomed at all, center should just be screen center
        # We also lerp the center towards screen-center when scale is close to 1.0
        # to ensure it perfectly aligns when zoomed out.
        scale_t = (curr_scale - 1.0) # 0 to 1
        
        effective_cx = curr_cx * scale_t + (width/2) * (1.0 - scale_t)
        effective_cy = curr_cy * scale_t + (height/2) * (1.0 - scale_t)

        # Clamp crop box to screen boundaries
        min_cx = crop_w / 2
        max_cx = width - crop_w / 2
        min_cy = crop_h / 2
        max_cy = height - crop_h / 2

        clamped_cx = max(min(effective_cx, max_cx), min_cx)
        clamped_cy = max(min(effective_cy, max_cy), min_cy)

        x1 = int(clamped_cx - crop_w / 2)
        y1 = int(clamped_cy - crop_h / 2)
        x2 = int(clamped_cx + crop_w / 2)
        y2 = int(clamped_cy + crop_h / 2)

        # Ensure indices are within bounds (due to int casting)
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(width, x2)
        y2 = min(height, y2)

        # Crop and resize
        cropped = frame[y1:y2, x1:x2]
        
        # If crop logic fails completely (e.g. 0 width), fallback
        if cropped.size == 0 or cropped.shape[0] == 0 or cropped.shape[1] == 0:
            resized = frame
        else:
            resized = cv2.resize(cropped, (width, height), interpolation=cv2.INTER_LINEAR)

        out.write(resized)
        frame_idx += 1
        
        if frame_idx % 30 == 0:
            print(f"Processed {frame_idx}/{total_frames} frames...")

    cap.release()
    out.release()
    print(f"Done processing. Output saved to {video_out}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: process.py <video_in> <json_in> <video_out>")
        sys.exit(1)
        
    process_video(sys.argv[1], sys.argv[2], sys.argv[3])

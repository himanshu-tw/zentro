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

    # Note: Event separation is done after mapping timestamps to frames


    cap = cv2.VideoCapture(video_in)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0 or np.isnan(fps):
        fps = 30.0
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Map timestamps to frame index using FPS to perfectly sync
    for e in events:
        e['frame'] = (e.get('t', 0) / 1000.0) * fps

    # Separate events
    clicks = [e for e in events if e.get('type') == 'click']
    moves = [e for e in events if e.get('type') == 'move']

    # FourCC for mp4
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_out, fourcc, fps, (width, height))

    # State variables
    is_zoomed = False
    prev_target_scale = 1.0
    zoom_start_scale = 1.0
    zoom_start_frame = -9999
    zoom_duration_frames = int(0.3 * fps) # 300ms ease-in-out transition
    idle_frames = int(0.5 * fps) # 500ms threshold for idle
    
    target_scale = 1.0 # 1.0 = full screen, 2.0 = zoomed 2x
    curr_scale = 1.0
    curr_cx = width / 2
    curr_cy = height / 2

    # Helper function to get the latest event
    def get_latest_event_before(event_list, f_idx):
        valid = [e for e in event_list if e['frame'] <= f_idx]
        return valid[-1] if valid else None

    # Helper function to LERP position for smooth cursor tracking
    def get_interpolated_pos(event_list, f_idx):
        if not event_list: return None, None
        if f_idx <= event_list[0]['frame']: return event_list[0]['x'], event_list[0]['y']
        
        for i in range(len(event_list) - 1):
            e1 = event_list[i]
            e2 = event_list[i+1]
            if e1['frame'] <= f_idx <= e2['frame']:
                d_frames = e2['frame'] - e1['frame']
                max_gap_frames = 0.1 * fps # Max 100ms gap to interpolate
                if d_frames > max_gap_frames or d_frames == 0: 
                    return e1['x'], e1['y']
                alpha = (f_idx - e1['frame']) / d_frames
                x = e1['x'] + (e2['x'] - e1['x']) * alpha
                y = e1['y'] + (e2['y'] - e1['y']) * alpha
                return x, y
                
        return event_list[-1]['x'], event_list[-1]['y']

    print(f"Processing {video_in} -> {video_out} at {fps} fps ({width}x{height})")
    
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        latest_click = get_latest_event_before(clicks, frame_idx)
        latest_move = get_latest_event_before(moves, frame_idx)
        
        last_click_f = latest_click['frame'] if latest_click else -9999
        last_move_f = latest_move['frame'] if latest_move else -9999
        last_activity_f = max(last_click_f, last_move_f)

        # Logic for zoom presence based on idle detection
        if last_activity_f != -9999 and (frame_idx - last_activity_f <= idle_frames):
            is_zoomed = True
        else:
            is_zoomed = False

        target_scale = 2.0 if is_zoomed else 1.0
        
        # Smooth zoom transition (ease-in / ease-out)
        if target_scale != prev_target_scale:
            zoom_start_scale = curr_scale
            zoom_start_frame = frame_idx
            prev_target_scale = target_scale

        if frame_idx < zoom_start_frame + zoom_duration_frames:
            progress = (frame_idx - zoom_start_frame) / max(1, zoom_duration_frames)
            ease = progress * progress * (3.0 - 2.0 * progress)
            curr_scale = zoom_start_scale + (target_scale - zoom_start_scale) * ease
        else:
            curr_scale = target_scale
        
        # Position logic via LERP for smooth cursor tracking
        p_x, p_y = get_interpolated_pos(moves, frame_idx)
        if p_x is not None and p_y is not None:
            curr_cx = p_x
            curr_cy = p_y

        # Calculate crop boundaries (integer exact for centering)
        crop_w = int(width / curr_scale)
        crop_h = int(height / curr_scale)

        # Interpolate scale influence (0 to 1) for perfect framing
        scale_t = max(0.0, min(1.0, curr_scale - 1.0))
        
        effective_cx = curr_cx * scale_t + (width/2) * (1.0 - scale_t)
        effective_cy = curr_cy * scale_t + (height/2) * (1.0 - scale_t)

        # Clamp crop box to screen boundaries
        min_cx = crop_w // 2
        max_cx = width - (crop_w - min_cx)
        min_cy = crop_h // 2
        max_cy = height - (crop_h - min_cy)

        clamped_cx = max(min_cx, min(int(effective_cx), max_cx))
        clamped_cy = max(min_cy, min(int(effective_cy), max_cy))

        x1 = clamped_cx - crop_w // 2
        y1 = clamped_cy - crop_h // 2
        x2 = x1 + crop_w
        y2 = y1 + crop_h

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

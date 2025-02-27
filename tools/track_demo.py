import argparse
from pathlib import Path
import cv2
from ultralytics import YOLO

from tracker.config import io
from tracker.update import Tracker
from tracker.associations.collections import ASSOCIATIONS
from ultralytics.utils.plotting import Annotator
from ultralytics.utils.plotting import colors


def make_parser():
    parser = argparse.ArgumentParser("Tracker")
    mot_choices = ['mix_17', 'mix_20', 'dancetrack','kitti']
    project_choices = [f'yolov8{x}-mix' for x in ('n', 's', 'm', 'l', 'x')]
    parser.add_argument("--project", type=str, default='yolov8l-mix', choices=project_choices,
                        help="yolov8-mix pre-trained model")
    parser.add_argument("--exp", type=str, default='dancetrack', choices=mot_choices, help="experiment name")
    parser.add_argument("--association", type=str, default='uk_botsort', choices=list(ASSOCIATIONS.keys()),
                        help="association model")
    parser.add_argument("--config", type=str, default='./tracker/config/track_dancetrack.yaml',
                        help="path to config .yaml for the experiment")
    parser.add_argument("--video_path", type=str, help="path to input video")
    parser.add_argument("--output_path", type=str, help="path to annotated video with tracks")
    parser.add_argument("--gpu_id", type=int, default=3, help="cuda device")
    return parser.parse_args()


if __name__ == '__main__':

    # Parse arguments
    args = make_parser()
    cli_association = args.association
    
    args = io.merge_with_cli_args(args)
    args.tracker.association = cli_association
    
    # Load the YOLOv8 model
    model = YOLO(Path(args.project) / args.exp / 'weights/best.pt').to(args.yolo.device)

    # Load tracker
    tracker = Tracker(args.tracker)

    # Open the video file
    cap = cv2.VideoCapture(args.video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)

    # Get the width and height of the video frames
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Define the codec and create VideoWriter object
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec for .mp4
    out = cv2.VideoWriter(args.output_path, fourcc, fps, (width, height))

    while cap.isOpened():
        success, frame = cap.read()
        if success:
            # Run inference on the frame
            results = model(frame)
            
            annotator = Annotator(frame, line_width=1)
            # Run tracking
            if results[0] is not None:
                online_targets = tracker.update(results[0])
                if not online_targets:
                    continue
                for t in online_targets:
                    tlwh = t.tlwh
                    tid = int(t.track_id)
                    vertical = tlwh[2] / tlwh[3] > 1.6
                    if tlwh[2] * tlwh[3] > args.tracker.min_box_area and not vertical:
                        annotator.box_label(t.tlbr, f'{tid}', color=colors(tid))

            # Display the tracked frame                        
            annotated = annotator.result()  
             
            # Write the processed frame to the output video
            out.write(annotated)
            
            # Break the loop if 'q' is pressed
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        else:
            break

    # Release the video capture and writer objects
    cap.release()
    out.release()
    cv2.destroyAllWindows()
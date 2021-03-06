"""
Main starter class
Authors: Diana Mendes, Samuel Pedro, Jason Bolito & FIKALAB DeepLens future project members :-)
Notes: Some model loading code snippets were adapted from AWS DeepLens sample projects.
"""

# import os

import awscam
import cv2
import base64
import requests

from cpdl import AwsCaptureProcessDisplayLoop

from collections import Counter
from TrackingPeople import TrackingPeople, BoundingBox

RESOLUTION = {'1080p': (1920, 1080), '720p': (1280, 720), '480p': (858, 480), '240p': (426, 240)}

TIMEOUT = 5


# load_aws_pretrained_model(model_path: str, use_gpu: bool = True)
def load_aws_pretrained_model(mpath, use_gpu=True):
    return awscam.Model(mpath, {'GPU': 1 if use_gpu else 0})


def main():
    resolution = RESOLUTION['240p']
    print "output resolution is {}".format(resolution)

    """
    # !!!!!!!!!!!!! OUTPUT SETUP !!!!!!!!!!!!!!

    # Path to the FIFO file. The lambda only has permissions to the tmp
    # directory. Pointing to a FIFO file in another directory
    # will cause the lambda to crash.
    result_path = '/tmp/results.mjpeg'

    print "making fifo: {}".format(result_path)

    # Create the FIFO file if it doesn't exist.
    if not os.path.exists(result_path):
        os.mkfifo(result_path)
    """

    # !!!!!!!!!!!!! MODEL SETUP !!!!!!!!!!!!!!

    # This object detection model is implemented as single shot detector (ssd), since
    # the number of labels is small we create a dictionary that will help us convert
    # the machine labels to human readable labels.
    model_type = 'ssd'
    output_map = {1: 'aeroplane', 2: 'bicycle', 3: 'bird', 4: 'boat', 5: 'bottle', 6: 'bus',
                  7: 'car', 8: 'cat', 9: 'chair', 10: 'cow', 11: 'dinning table',
                  12: 'dog', 13: 'horse', 14: 'motorbike', 15: 'person',
                  16: 'pottedplant', 17: 'sheep', 18: 'sofa', 19: 'train',
                  20: 'tvmonitor'}

    print "model output map: {}".format(output_map)

    # The sample projects come with optimized artifacts, hence only the artifact
    # path is required.
    model_path = '/opt/awscam/artifacts/mxnet_deploy_ssd_resnet50_300_FP16_FUSED.xml'
    print "loading model from file: {}".format(model_path)
    model = load_aws_pretrained_model(model_path)
    print "loaded!"

    # Set the threshold for detection
    detection_threshold = 0.35

    # The height and width of the training set images
    model_input_height = 300
    model_input_width = 300

    # fifo_file = open(result_path, 'w')

    tracker = TrackingPeople()

    # !!!!!!!!!!!!!!!!! HANDLERS !!!!!!!!!!!!!!!!!!!!!! (handlers are defined as closures)
    # CAPTURE HANDLER: handles inference part of program

    # def classify_frame(frame: np.ndarray, frame_timestamp: float):
    def classify_frame(frame, frame_timestamp):
        # Resize frame to the same size as the training set.
        frame_resize = cv2.resize(frame, (model_input_height, model_input_width))

        # Run the images through the inference engine and parse the results using
        # the parser API, note it is possible to get the output of doInference
        # and do the parsing manually, but since it is a ssd model,
        # a simple API is provided.
        parsed_inference_results = model.parseResult(model_type,
                                                     model.doInference(frame_resize))
        # Compute the scale in order to draw bounding boxes on the full resolution
        # image.
        yscale = float(frame.shape[0] / model_input_height)
        xscale = float(frame.shape[1] / model_input_width)

        # Get the detected objects and probabilities
        for obj in parsed_inference_results[model_type]:
            if obj['prob'] > detection_threshold:
                # Add bounding boxes to full resolution frame
                xmin = int(xscale * obj['xmin'])  # + int((obj['xmin'] - model_input_width / 2) + model_input_width / 2)
                ymin = int(yscale * obj['ymin'])
                xmax = int(xscale * obj['xmax'])  # + int((obj['xmax'] - model_input_width / 2) + model_input_width / 2)
                ymax = int(yscale * obj['ymax'])

                # See https://docs.opencv.org/3.4.1/d6/d6e/group__imgproc__draw.html
                # for more information about the cv2.rectangle method.
                # Method signature: image, point1, point2, color, and tickness.
                cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (255, 165, 20), 10)

                # Amount to offset the label/probability text above the bounding box.
                text_offset = 15

                # See https://docs.opencv.org/3.4.1/d6/d6e/group__imgproc__draw.html
                # for more information about the cv2.putText method.
                # Method signature: image, text, origin, font face, font scale, color,
                # and tickness
                cv2.putText(frame, "{}: {:.2f}%".format(output_map[obj['label']],
                                                        obj['prob'] * 100),
                            (xmin, ymin - text_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 2.5, (255, 165, 20), 6)
        return frame

    # def counter_classify_frame(frame: np.ndarray, frame_timestamp: float):
    def counter_classify_frame(frame, frame_timestamp):
        # Resize frame to the same size as the training set.
        frame_resize = cv2.resize(frame, (model_input_height, model_input_width))

        # Run the images through the inference engine and parse the results using
        # the parser API, note it is possible to get the output of doInference
        # and do the parsing manually, but since it is a ssd model,
        # a simple API is provided.
        parsed_inference_results = model.parseResult(model_type,
                                                     model.doInference(frame_resize))

        filtered_peeps = [obj for obj in parsed_inference_results[model_type]
                          if (obj['label'] == 15) and (obj['prob'] > detection_threshold)]

        # Compute the scale in order to draw bounding boxes on the full resolution
        # image.
        yscale = float(frame.shape[0] / model_input_height)
        xscale = float(frame.shape[1] / model_input_width)

        counter_objects = Counter()

        # Get the detected objects and probabilities
        for obj in parsed_inference_results[model_type]:
            if obj['prob'] > detection_threshold:
                counter_objects[output_map[obj['label']]] += 1

                # Add bounding boxes to full resolution frame
                xmin = int(xscale * obj['xmin']) + int((obj['xmin'] - model_input_width / 2) + model_input_width / 2)
                ymin = int(yscale * obj['ymin'])
                xmax = int(xscale * obj['xmax']) + int((obj['xmax'] - model_input_width / 2) + model_input_width / 2)
                ymax = int(yscale * obj['ymax'])

                xmin = max([0, xmin])
                xmax = max([0, xmax])
                ymin = max([0, ymin])
                ymax = max([0, ymax])

                if obj['label'] == 15:
                    cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (75, 251, 75), 10)
                    center_circle = (((xmax - xmin) / 2) + xmin, ((ymax - ymin) / 2) + ymin)
                    frame_cut = frame[ymin:ymax, xmin:xmax, :]
                    tracker.find_closest_person_v2(frame_cut, center_circle, frame_timestamp,
                                                   BoundingBox(xmin, xmax, ymin, ymax), frame.shape)

                # Amount to offset the label/probability text above the bounding box.
                text_offset = 15
                # See https://docs.opencv.org/3.4.1/d6/d6e/group__imgproc__draw.html
                # for more information about the cv2.putText method.
                # Method signature: image, text, origin, font face, font scale, color,
                # and tickness
                cv2.putText(frame, "{}: {:.2f}%".format(output_map[obj['label']],
                                                        obj['prob'] * 100),
                            (xmin, ymin - text_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 2.5, (255, 165, 20), 6)

        # print counter_objects
        # print len(tracker.people)

        for person in tracker.people:
            for idx, position in enumerate(person.positions):
                if frame_timestamp - person.timestamps[idx] > TIMEOUT:
                    del (person.positions[idx])
                    del (person.timestamps[idx])
                else:
                    cv2.circle(frame, position, 25, person.colour, 20)

            if len(person.positions) == 0:
                del person

        return frame, filtered_peeps

    # PROCESS HANDLER (writes image to video fifo file)
    def write_to_video(frame):
        success, jpeg = cv2.imencode('.jpg', cv2.resize(frame[0], resolution))

        if not success:
            raise Exception('Failed to set frame data')

        """
        # Write the data to the FIFO file. This call will block
        # meaning the code will come to a halt here until a consumer
        # is available.
        try:
            fifo_file.write(jpeg.tobytes())
        except IOError:
            pass
        """

        # encode64
        jpeg_as_text = base64.b64encode(jpeg).decode()

        # send newframe
        requests.put('http://10.8.10.248:5000/video_stream', json={'frame': jpeg_as_text, 'objects': frame[1]})

    # start Capture Process Display Loop (capture and processing handlers are executed on separate threads whenever
    # possible)
    loop = AwsCaptureProcessDisplayLoop()

    # register handlers
    loop.register_capture_handler(capture_handler=counter_classify_frame, process_handler=write_to_video)

    # close fifo file after the CPDL is stopped
    # loop.register_on_stop_handler(fifo_file.close)

    # run the event loop (this call blocks until interrupted (in this case, forever)
    loop.start_loop(blocking=True)

    # stops the loop (technically unreachable code but may be useful in future iterations of the project)
    loop.stop_loop()


if __name__ == '__main__':
    main()

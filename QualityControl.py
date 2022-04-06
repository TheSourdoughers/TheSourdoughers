import cv2
import depthai as dai
import numpy as np
import math

modelPath = './models/yolo_v4_tiny_openvino_2021.3_6shave.blob'
modelLabels = ["Empty: Add elements to the container",
               "Good Quality: Let the sourdough rest",
               "Bad Quality: Need to feed sourdough", ]
white = (255, 255, 255)
green = (0, 255, 0)
red = (255, 0, 0)
blue = (0, 0, 255)
yellow = (255, 255, 0)
colorsl = [yellow, red, blue]

# Create pipeline
pipeline = dai.Pipeline()

# RGB Camera
camRgb = pipeline.create(dai.node.ColorCamera)
camRgb.setPreviewSize(512, 320)
camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
camRgb.setInterleaved(False)
camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
camRgb.setFps(35)

# Detection Network
detectionNetwork = pipeline.create(dai.node.YoloSpatialDetectionNetwork)
detectionNetwork.setConfidenceThreshold(0.5)
detectionNetwork.setNumClasses(3)
detectionNetwork.setCoordinateSize(4)
detectionNetwork.setAnchors(np.array([10, 14, 23, 27, 37, 58, 81, 82, 135, 169, 344, 319]))
detectionNetwork.setAnchorMasks({"side16": np.array([3, 4, 5]), "side32": np.array([0, 1, 2])})
detectionNetwork.setIouThreshold(0.5)
detectionNetwork.setBlobPath(modelPath)
detectionNetwork.setNumInferenceThreads(2)
detectionNetwork.input.setBlocking(False)
detectionNetwork.setBoundingBoxScaleFactor(0.5)
detectionNetwork.setDepthLowerThreshold(200)
detectionNetwork.setDepthUpperThreshold(3000)

# Stereo Cameras
left = pipeline.create(dai.node.MonoCamera)
left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
left.setBoardSocket(dai.CameraBoardSocket.LEFT)
right = pipeline.create(dai.node.MonoCamera)
right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
right.setBoardSocket(dai.CameraBoardSocket.RIGHT)

stereo = pipeline.create(dai.node.StereoDepth)
stereo.initialConfig.setConfidenceThreshold(240)
stereo.setExtendedDisparity(True)

# Links
xoutRgb = pipeline.create(dai.node.XLinkOut)
xoutRgb.setStreamName("rgb")
camRgb.preview.link(detectionNetwork.input)

nnOut = pipeline.create(dai.node.XLinkOut)
nnOut.setStreamName("nn")
detectionNetwork.passthrough.link(xoutRgb.input)
detectionNetwork.out.link(nnOut.input)

left.out.link(stereo.left)
right.out.link(stereo.right)
stereo.depth.link(detectionNetwork.inputDepth)


with dai.Device(pipeline) as device:
    qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
    qDet = device.getOutputQueue(name="nn", maxSize=4, blocking=False)

    frame = None
    detections = []

    while True:
        inRgb = qRgb.get()
        inDet = qDet.get()

        if inDet is not None:
            detections = inDet.detections

        if inRgb is not None:
            frame = inRgb.getCvFrame()

            if frame is not None:
                for detection in detections:
                    # Color bbox
                    colorsel = colorsl[detection.label]

                    # Distance calculation
                    coords = detection.spatialCoordinates
                    dist = math.sqrt(coords.x ** 2 + coords.y ** 2 + coords.z ** 2)
                    dis = 2.38 - (dist / 1000)
                    dis = round(dis, 2)

                    # ODI detection
                    bbox = (detection.xmin, detection.ymin, detection.xmax, detection.ymax)
                    normVals = np.full(len(bbox), frame.shape[0])
                    normVals[::2] = frame.shape[1]
                    bbox = (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

                    cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), colorsel, 2)
                    cv2.putText(frame,
                                "(" + str(int(detection.confidence * 100)) + "%) " + modelLabels[detection.label],
                                (bbox[0] - 200, bbox[1] + 120),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                colorsel, 2)
                    cv2.putText(frame, " Height sourdough: {:.2f} cm".format(dis), (bbox[0] - 150, bbox[1] + 150),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, green, 2)

                cv2.imshow("The Sourdoughers", frame)

        if cv2.waitKey(1) == ord('q'):
            break

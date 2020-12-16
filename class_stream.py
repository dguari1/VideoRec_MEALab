
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, Qt
from PyQt5.QtGui import QImage
import cv2 
import time
import pyaudio
import numpy as np
import platform


class CameraWorker(QThread):

    changePixmap = pyqtSignal(QImage, int, int)
    frameforvideo = pyqtSignal(np.ndarray)

    def __init__(self, cam_id=0, fps=30, height=720, width=1280):
        super(CameraWorker, self).__init__()
    
        self.fps = fps
        self.cam_id = cam_id
        self.isCapture = False
        self.isRecording = False
        self.width = width
        self.height = height 
        self.camera = None
        self.platform = platform.system()
    
    def camera_set_up(self):
        self.interval = (1/self.fps)*1000
        if self.platform == 'Darwin':
            self.camera = cv2.VideoCapture(self.cam_id)
        elif self.platform == 'Windows':
            self.camera = cv2.VideoCapture(self.cam_id, cv2.CAP_DSHOW)
            self.camera.set(cv2.CAP_PROP_FPS, self.fps)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH,self.width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT,self.height)
            self.camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('M','J','P','G'))
            self.camera.set(cv2.CAP_PROP_AUTOFOCUS, 0)

    @pyqtSlot()
    def run(self):

        time_of_frame = 0
        framenum = 0 
        while self.isCapture:
            passed_time = (time.time()-time_of_frame)*1000
            if passed_time >= self.interval: 
            #only read if enough time has passed 
                time_of_frame = time.time()
                #valid, frame = self.camera.read()
                valid, frame = self.camera.retrieve(self.camera.grab())
                if valid: #there is an image
                    frame = cv2.flip(frame,1)
                    if self.isRecording:
                        self.frameforvideo.emit(frame) #emit frame to be recorded
                    rgbImage = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgbImage.shape
                    bytesPerLine = ch * w
                    convertToQtFormat = QImage(rgbImage.data, w, h, bytesPerLine, QImage.Format_RGB888)
                    p = convertToQtFormat.scaled(w//2, h//2, Qt.KeepAspectRatio)
                    self.changePixmap.emit(p, h, w) #emit frame to show in screen 
                    
                    #print(f"Yes frame {framenum} - took {passed_time} miliseconds")
                    framenum+=1
                else:
                    self.isCapture = False
                    #st = time.time() #update the time 
                
            else:
                pass
                #print((current_time-st)*1000)
                #st=time.time()


    def stop_camera(self):
        self.isCapture = False
        self.isRecording = False
        self.camera.release()

    # def __del__(self):



class MicrophoneWorker(QThread):

    datatoplot = pyqtSignal(np.ndarray)
    #datatosave = pyqtSignal(object)

    def __init__(self, microphone_id=0, rate=44100):
        super(MicrophoneWorker, self).__init__()
    
        self.microphone_id = microphone_id
        self.rate = rate
        self.chunk = 512*6
        self.channels = 1
        self.format = pyaudio.paInt16
        self.audio = None
        self.stream = None

        # self.audio  = pyaudio.PyAudio()
        # self.stream = self.audio.open(
        #                 format=self.format,
        #                 channels=self.channels,
        #                 rate=self.rate,
        #                 input=True,
        #                 input_device_index = self.microphone_id,
        #                 frames_per_buffer=self.chunk
        #                 )

        self.isCapture = False
        self.isRecording = False
        self.recorded_data = []


    def microphone_set_up(self):
        if self.audio is None:
            self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(
            format = self.format,
            channels = self.channels, 
            rate = self.rate,
            input = True, 
            input_device_index = self.microphone_id,
            frames_per_buffer = self.chunk
        )

    @pyqtSlot()
    def run(self):

        recorded_data = []
        while self.isCapture:
           data = self.stream.read(self.chunk, exception_on_overflow=False) 
           self.datatoplot.emit(np.frombuffer(data, dtype = np.int16)) #emit data to plot
           if self.isRecording:
               recorded_data.append(data)

        #if self.isRecording:
        #       self.datatosave.emmit(np.fromstring(recorded_data, dtype = np.int16))


    def stop_microphone(self):
        self.isCapture = False
        self.isRecording = False

        self.stream.stop_stream()
        self.stream.close()
        #self.audio.terminate()

        # wf = wave.open('out.wav', 'wb')
        # wf.setnchannels(self.channels)
        # wf.setsampwidth(self.audio.get_sample_size(self.format))
        # wf.setframerate(self.rate)
        # wf.writeframes(b''.join(frames))
        # wf.close()

    # def __del__(self):
    #     self.stream.stop_stream()
    #     self.stream.close()
    #     self.audio.terminate()

        


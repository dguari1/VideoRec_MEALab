from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtGui import QRegExpValidator, QIntValidator, QImage, QPixmap
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from pyqtgraph import PlotWidget
import pyqtgraph as pg
import sys
import time
import os
from pathlib import Path
import platform
import shlex
import yaml
import numpy as np

from class_stream import CameraWorker, MicrophoneWorker


def message_box(message):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Critical)
    msg.setText(message)
    #msg.setInformativeText("This is additional information")
    msg.setWindowTitle("Error")
    retval = msg.exec_()

def message_box_with_options(message, message2=''):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setText(message)
    msg.setInformativeText(message2)
    msg.setWindowTitle("Warning")
    msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    retval = msg.exec_()

    return retval

class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        self.platform = platform.system()
        self.pathToFFmpeg = None
        self.pathToSubject = None
        self.TrialNumberCounter = 0  #this counter will take care of updating the trial number
        self.listoftask = None
        self.dictwithtaskandsubtasks = None
        self.file_path = None #path to video file 
        self.file_video_path = None
        self.file_audio_path = None
        
        #Load the UI Page
        self.ui = uic.loadUi('form.ui', self)
        self.set_up_mainWindow()

        #define QProcess that will handle ffmpeg 
        self.p = QtCore.QProcess()  # Keep a reference to the QProcess (e.g. on self) while it's running.
        self.p.readyReadStandardOutput.connect(self.handle_stdout)
        self.p.readyReadStandardError.connect(self.handle_stderr)
        self.p.stateChanged.connect(self.handle_state)
        self.p.finished.connect(self.process_finished) 

        self.p_ffmpeg_rec = QtCore.QProcess()  # Keep a reference to the QProcess (e.g. on self) while it's running.
        self.p_ffmpeg_rec.readyReadStandardOutput.connect(self.handle_stdout_rec)
        self.p_ffmpeg_rec.readyReadStandardError.connect(self.handle_stderr_rec)
        self.p.stateChanged.connect(self.handle_state)
        self.p_ffmpeg_rec.finished.connect(self.process_finished_rec) 

        #define another process that will handle ffplay -- This is really ugly but is taking to much time to solve so i'll leave it like it is
        self.ffplay = QtCore.QProcess() 
        self.p_ffmpeg_rec.setStandardOutputProcess(self.ffplay)




        #check for devices 
        self.ui.ffmpeg_FindDevice.pressed.connect(self.List_Devices)
        self.ui.ffmpeg_LocateFolder.pressed.connect(lambda x='FFMPEG': self.Locate_Folder(x))
        self.ui.ffmpeg_Formats.pressed.connect(self.List_Formats)
        self.ui.ffmpeg_Clear.pressed.connect(self.Clear_text)

        self.isCapturing= False
        self.CameraWorker = CameraWorker()
        self.CameraWorker.changePixmap.connect(self.Update_ImageLabel)

        self.MicrophoneWorker = MicrophoneWorker()
        self.MicrophoneWorker.datatoplot.connect(self.update_plot)
        self.line_plot = None #holds the mic data for ploting 

        self.ui.TestButton.pressed.connect(self.Test_Audio_Video)

        self.ui.RecordButton.pressed.connect(self.Record_audio_and_video)
        self.ui.StopButton.pressed.connect(self.quit)


        #handle subject
        self.ui.SubjectFindFolder.pressed.connect(lambda x='Subject': self.Locate_Folder(x))

        self.ui.comboBox_Task.currentIndexChanged.connect(self.change_combobox_task)

        self.ui.show()

    def set_up_mainWindow(self):
        self.ui.graphWidget.setBackground('w')
        self.ui.graphWidget.setYRange(-15000, 15000)
        self.ui.graphWidget.setXRange(0, 2)

        spaceVal = QtCore.QRegExp("^[A-Za-z0-9_]+")
        validator_spaceVal = QRegExpValidator(spaceVal, self)
        self.ui.SubjectID.setValidator(validator_spaceVal)

        
        numberVal = QtCore.QRegExp("^[0-9_]+")
        validator_numberVal = QRegExpValidator(numberVal, self)
        self.ui.Date.setValidator(validator_numberVal)
        self.ui.Date.setText(time.strftime("%d_%m_%Y"))
        self.ui.Date.setMaxLength(10)

        self.ui.Location.setText('FIT')

        self.ui.TrialNumber.setText(str(self.TrialNumberCounter))

        #intValidator = QIntValidator(0,9,self)
        #self.ui.CameraID.setValidator(intValidator)
        #self.ui.CameraID.setMaxLength(1)
        #self.ui.MicrophoneID.setValidator(intValidator)
        #self.ui.MicrophoneID.setMaxLength(1)

        intValidator = QIntValidator(0,10000,self)
        self.ui.CameraFPS.setValidator(intValidator)
        self.ui.CameraFPS.setMaxLength(3)
        self.ui.CameraFrameWidth.setValidator(intValidator)
        self.ui.CameraFrameHeight.setValidator(intValidator)

        self.read_yaml()
        

        if self.platform == 'Darwin':
            #avfoundations cannot provide formats for input device :/
            if os.path.exists(Path('/usr/local/bin/ffmpeg')):
                self.ui.ffmpeg_LocateFolder.setEnabled(False)
                self.ui.lineEdit.setText('/usr/local/bin/ffmpeg')
            else:
                self.ui.ffmpeg_LocateFolder.setEnabled(False)
                self.ui.lineEdit.setText('FFmpeg not found -- Please find the containing folder')
        elif self.platform == 'Windows':
            self.ui.ffmpeg_LocateFolder.setEnabled(True)
            self.ui.ffmpeg_Formats.setEnabled(True)
    
    def Locate_Folder(self, button_idx):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        if button_idx == 'FFMPEG':
            #fileName, _ = QFileDialog.getOpenFileName(self,"QFileDialog.getOpenFileName()", "","Executable Files (*.exe)", options=options)
            base = "C:/Users/dguarinlopez/Documents/ffmpeg-2020-11-18-git-e3081d6f4f-full_build/bin/"
            folderName = str(QFileDialog.getExistingDirectory(self, "Select Directory",base))
            if folderName:
                self.pathToFFmpeg = Path(folderName)
                self.ui.lineEdit.setText(str(self.pathToFFmpeg))
        elif button_idx == 'Subject':
            #fileName, _ = QFileDialog.getOpenFileName(self,"QFileDialog.getOpenFileName()", "","Executable Files (*.exe)", options=options)
            base = "C:/Users/dguarinlopez/Documents/Subjects"
            folderName = str(QFileDialog.getExistingDirectory(self, "Select Directory",base))
            if folderName:
                self.pathToSubject = Path(folderName)
                self.ui.SubjectFolder.setText(str(self.pathToSubject))
      
    def List_Devices(self):
        self.Clear_text()
        if self.platform == 'Darwin':
            format = '-hide_banner -f avfoundation -list_devices true -i ""'
            argument = shlex.split(format)
            self.p.start('ffmpeg', argument)
        elif self.platform == 'Windows':
            format = '-hide_banner -list_devices true -f dshow -i dummy'
            argument = shlex.split(format)
            self.p.start(str(self.pathToFFmpeg / 'ffmpeg'), argument)

    def List_Formats(self):
        self.Clear_text()
        video_name = self.ui.CameraID.text()
        video_name = video_name.replace('"','')
        if len(video_name) != 0:
            if self.platform == 'Darwin':
                format = f'-hide_banner -f avfoundation -framerate 100000 -i {video_name}'
                argument = shlex.split(format)
                self.p.start('ffmpeg', argument)
            elif self.platform == 'Windows':
                format = f'-hide_banner -f dshow -list_options true -i video="{video_name}"'
                argument = shlex.split(format)
                self.p.start(str(self.pathToFFmpeg / 'ffmpeg'), argument)
        else:
            self.ui.text.setPlainText("Provide a camera index")

    def create_file_name(self):
        #create a file name based on the information provided in the GUI
        if self.ui.SubjectFolder.text():
            path = Path(self.ui.SubjectFolder.text())
            if self.SubjectID.text():
                path = path / self.SubjectID.text()
                if not path.exists():
                    path.mkdir(parents=True, exist_ok=True)
                if self.Date.text():
                    nn = self.SubjectID.text() + '__' + self.Date.text()
                    path = path / nn
                    if not path.exists():
                        path.mkdir(parents=True, exist_ok=True)
                    if self.ui.TrialNumber.text():
                        if self.Location.text():
                            file_name = self.SubjectID.text() + '__' + self.ui.comboBox_Task.currentText()+'_' + self.ui.comboBox_SubTask.currentText() + '__' + self.Location.text() + '__' + self.Date.text() + '__' + 'Trial_'+self.ui.TrialNumber.text()+'.mkv'
                        else:
                            file_name = self.SubjectID.text() + '__' + self.ui.comboBox_Task.currentText()+'_' + self.ui.comboBox_SubTask.currentText() + '__' + self.Date.text() + '__' + 'Trial_'+self.ui.TrialNumber.text()+'.mkv'
                        
                        file_path = path / file_name
                        if file_path.exists():
                             retval  = message_box_with_options('The file already exists', 'Press Ok to overwrite it.')
                             if retval != QMessageBox.Ok:
                                 self.file_path = None
                                 return
                        
                        self.file_path = file_path
                        

                    else:
                        message_box("Please enter a trial number")
                        return 
                else:
                    message_box("Please enter a date")
                    return 
            else:
                message_box("Please Enter a subject ID")
                return 


        else:
            message_box("Please select a folder to save the files")
            return

    def Record_audio_and_video(self):

        self.create_file_name()

        if self.file_path:

            
            if self.ui.CameraID.text():
                camera_name = self.ui.CameraID.text()
                camera_name = camera_name.replace('"','')
            else:
                message_box("Please provide the Camera ID")
                return
            
            if  self.ui.MicrophoneID.text():
                microphone_name = self.ui.MicrophoneID.text()
                microphone_name = microphone_name.replace('"','')
            else:
                message_box("Please provide the Microphone ID")
                return

            if self.ui.CameraFPS.text():
                framerate = int(self.ui.CameraFPS.text())
            else:
                message_box("Please provide the desired FPS")
                return

            if self.ui.CameraFrameWidth.text() and self.ui.CameraFrameHeight.text():
                width = int(self.ui.CameraFrameWidth.text())
                height = int(self.ui.CameraFrameHeight.text())
            else:
                message_box("Please provide the desired camera Width and Height")
                return


            if self.ui.CameraCodec_Copy.isChecked():
                video_codec = 'copy'
                audio_codec = 'flac'
            else:
                video_codec = 'libx264'
                audio_codec= 'aac'
                self.file_path =  self.file_path.with_suffix('.mp4')


            if self.platform == 'Darwin':
                pass
            elif self.platform == 'Windows':
                """
                Available -presents for codec are:
                - ultrafast 
                - superfast 
                - veryfast 
                - faster 
                - fast 
                - medium 
                - slow 
                - slower 
                - veryslow

                -crf defines the quality preserving of the codec i can take a value between 0 (lossless - no compression) and 51 (max compression)
                According to this: Tip: If you're looking for an output that is roughly "visually lossless" but not technically lossless, use a -crf value of around 17 or 18 (you'll have to experiment to see which value is acceptable for you). It will likely be indistinguishable from the source and not result in a huge, possibly incompatible file like true lossless mode. (https://trac.ffmpeg.org/wiki/Encode/H.264)
                we set -crf 17 to preserve best quality and keep a small size
                
                aac -ac 1 -ab 32k -ar 44100

                """

                #format = '-hide_banner -y -rtbufsize 1024M -f dshow -framerate 60 -video_size 1280x720 -vcodec mjpeg -i video="c922 Pro Stream Webcam":audio="Microphone (Yeti Stereo Microphone)" -preset ultrafast -tune zerolatency -acodec aac -ac 1 -ab 32k -ar 44100 -f tee -map 0:v -map 0:a -c:v copy -c:a copy "out.mkv|[f=nut]pipe:" | ffplay -an pipe: -vf hflip'
                format_ffmpeg = f'-hide_banner -y -rtbufsize 1024M -f dshow -framerate {framerate} -video_size {width}x{height} -vcodec mjpeg -i video="{camera_name}":audio="{microphone_name}" -preset ultrafast -tune zerolatency -acodec aac -ac 1 -ab 32k -ar 44100 -f tee -map 0:v -map 0:a -c:v {video_codec} -probesize 32 "[onfail=ignore]{str(self.file_path.as_posix())}|[f=nut]pipe:"'
                format_ffmpeg = f'-hide_banner -y -rtbufsize 1024M -f dshow -framerate {framerate} -video_size {width}x{height} -vcodec mjpeg -i video="{camera_name}":audio="{microphone_name}" -preset ultrafast -crf 17 -tune zerolatency -c:a {audio_codec} -ac 1 -ab 32k -ar 44100 -c:v {video_codec} -f tee -map 0:v -map 0:a "[onfail=ignore]{str(self.file_path.as_posix())}|[f=nut]pipe:"'
                #format_ffmpeg = f'-hide_banner -y -rtbufsize 1024M -f dshow -framerate {framerate} -video_size {width}x{height} -vcodec mjpeg -i video="{camera_name}" -preset ultrafast -tune zerolatency -f tee -map 0:v -c:v {codec} -probesize 32 "[onfail=ignore]{str(self.file_path.as_posix())}|[f=nut:onfail=ignore]pipe:"'
                format_ffplay = '-an -autoexit -vf hflip -analyzeduration 0 -fflags -nobuffer -probesize 32 -sync ext -i pipe: -x 604 -y 360'
                argument_ffmpeg = shlex.split(format_ffmpeg)
                argument_ffplay = shlex.split(format_ffplay)
                self.p_ffmpeg_rec.start(str(self.pathToFFmpeg / 'ffmpeg'), argument_ffmpeg)
                self.ffplay.start(str(self.pathToFFmpeg / 'ffplay'), argument_ffplay)
    
    
    def quit(self):
        self.p_ffmpeg_rec.write('q'.encode())

    def Test_Audio_Video(self):

        if not self.isCapturing :
            fps = None 
            FrameWidth = None 
            FrameHeight = None
            MicrophoneRate = None

            if self.ui.CameraFPS.text():
                fps = int(self.ui.CameraFPS.text())
 
            if self.ui.CameraFrameWidth.text():
                FrameWidth = int(int(self.ui.CameraFrameWidth.text()))

            if self.ui.CameraFrameHeight.text():
                FrameHeight = int(int(self.ui.CameraFrameHeight.text()))

            if self.ui.MicrophoneRate.text():
                MicrophoneRate = int(self.ui.MicrophoneRate.text())
                self.set_up_plot(MicrophoneRate)

            if (fps is not None) and (FrameWidth is not None ) and (FrameHeight is not None) and (MicrophoneRate is not None):
                #Webcam
                self.CameraWorker.fps = fps
                self.CameraWorker.width = FrameWidth
                self.CameraWorker.height = FrameHeight 
                self.CameraWorker.cam_id = self.ui.CameraIndex.value()
                self.CameraWorker.camera_set_up()
                self.CameraWorker.isCapture = True

                #Microphone
                self.MicrophoneWorker.microphone_id  = self.ui.MicrophoneIndex.value()
                self.MicrophoneWorker.rate = MicrophoneRate
                self.MicrophoneWorker.microphone_set_up()
                self.MicrophoneWorker.isCapture = True 
                #start the threads
                self.CameraWorker.start()
                self.MicrophoneWorker.start()

                self.ui.TestButton.setText('Stop Test')
                self.isCapturing = True
        else:
            self.CameraWorker.stop_camera()
            self.MicrophoneWorker.stop_microphone()
            self.ui.TestButton.setText('Test')
            self.isCapturing = False

    @pyqtSlot(QImage, int, int)
    def Update_ImageLabel(self, qImg, h, w):
        self.ui.ImageLabel.setPixmap(QPixmap.fromImage(qImg))
        self.frameHeight = h
        self.frameWidth = w

    def set_up_plot(self, microphone_rate):
        duration = 2 #the plot will always show 2 s of data
        time_vec = np.array(range(microphone_rate*duration -1))*(1/microphone_rate)
        self.timetoshow = time_vec[::50]
        self.datatoshow = np.array([0]*len(self.timetoshow))
        if self.line_plot is None:
            self.line_plot = self.ui.graphWidget.plot(self.timetoshow, self.datatoshow)
        else:
            self.line_plot.setData(self.timetoshow, self.datatoshow)

    @pyqtSlot(np.ndarray)
    def update_plot(self, data):
        #replace the first elements and elinate the last ones
        self.datatoshow = np.append(data[::50], self.datatoshow[:-len(data[::50])])
        self.line_plot.setData(self.timetoshow, self.datatoshow)

    def Clear_text(self):
        self.ui.text.clear()

    def message(self, s):
        self.ui.text.appendPlainText(s)

    def handle_stderr(self):
        data = self.p.readAllStandardError()
        stderr = bytes(data).decode("utf8")
        self.message(stderr)

    def handle_stdout(self):
        data = self.p.readAllStandardOutput()
        stdout = bytes(data).decode("utf8")
        self.message(stdout)

    def handle_state(self, state):
        states = {   
            QtCore.QProcess.NotRunning: 'Not running',
            QtCore.QProcess.Starting: 'Starting',
            QtCore.QProcess.Running: 'Running',
        }
        state_name = states[state]
        self.message(f"State changed: {state_name}")

    def process_finished(self):
        self.message("Process finished.")

    def handle_stderr_rec(self):
        data = self.p_ffmpeg_rec.readAllStandardError()
        stderr = bytes(data).decode("utf8")
        self.message(stderr)

    def handle_stdout_rec(self):
        data = self.p_ffmpeg_rec.readAllStandardOutput()
        stdout = bytes(data).decode("utf8")
        self.message(stdout)

    def process_finished_rec(self):
        self.message("Process finished.")
        if self.file_path.exists():
            suffix = self.file_path.suffix
            if suffix == '.mkv':
                self.file_video_path = self.file_path.with_suffix('')
                self.file_video_path = Path(str(self.file_video_path) + '__video.avi')
                self.file_audio_path = self.file_path.with_suffix('')
                self.file_audio_path = Path(str(self.file_audio_path) + '__audio.flac')
            else:
                self.file_video_path = self.file_path.with_suffix('')
                self.file_video_path = Path(str(self.file_video_path) + '__video.avi')
                self.file_audio_path = self.file_path.with_suffix('')
                self.file_audio_path = Path(str(self.file_audio_path) + '__audio.aac')

            self.split_audio_and_video()

    def split_audio_and_video(self):
        #use ffmpeg to split audio and video 
        format_ffmpeg = f'-y -i {str(self.file_path.as_posix())} -map 0:a -c:a copy {str(self.file_audio_path.as_posix())} -map 0:v -c:v copy {str(self.file_video_path.as_posix())}'
        argument_ffmpeg = shlex.split(format_ffmpeg)
        self.p.start(str(self.pathToFFmpeg / 'ffmpeg'), argument_ffmpeg)


    def read_yaml(self):
        """
        the yml files has the following keys:

        - CameraID
        - CameraIndex
        - CameraFPS
        - CameraWidth
        - CameraHeight
        - CameraCodex
        - MicrophoneID
        - MicrophoneIndex
        - MicrophoneRate
        - FFMPEGLocateFolder
        """
        
        with open(r'gui_preload.yml') as file:
            # The FullLoader parameter handles the conversion from YAML
            # scalar values to Python the dictionary format
            list_of_preloads= yaml.load(file, Loader=yaml.FullLoader)

        self.ui.CameraID.setText(list_of_preloads['CameraID'])
        self.ui.CameraFPS.setText(str(list_of_preloads['CameraFPS']))
        if list_of_preloads['CameraIndex']:
            self.ui.CameraIndex.setValue(int(list_of_preloads['CameraIndex']))
        self.ui.CameraFrameWidth.setText(str(list_of_preloads['CameraWidth']))
        self.ui.CameraFrameHeight.setText(str(list_of_preloads['CameraHeight']))

        self.ui.MicrophoneID.setText(list_of_preloads['MicrophoneID'])
        self.ui.MicrophoneRate.setText(str(list_of_preloads['MicrophoneRate']))
        if list_of_preloads['MicrophoneIndex']:
            self.ui.MicrophoneIndex.setValue(int(list_of_preloads['MicrophoneIndex']))

        if list_of_preloads['CameraCodex'] =='copy':
            self.ui.CameraCodec_Copy.setChecked(True)


        self.pathToFFmpeg = Path(list_of_preloads['FFMPEGLocateFolder'])
        self.ui.lineEdit.setText(str(self.pathToFFmpeg))


        with open(r'task_subtask.yml') as file:
            # The FullLoader parameter handles the conversion from YAML
            # scalar values to Python the dictionary format
            self.dictwithtaskandsubtasks= yaml.load(file, Loader=yaml.FullLoader)

        self.listoftask = list(self.dictwithtaskandsubtasks.keys())
        self.ui.comboBox_Task.addItems(self.listoftask)
        self.ui.comboBox_SubTask.addItems(self.dictwithtaskandsubtasks[self.ui.comboBox_Task.currentText()])

    def write_yaml(self):
        """
        This function will write the information from the GUI in 'gui_preload.yml' so that it can be automatically 
        populated the next time that you open the program. 
        This is the information that will be filled 
        - CameraID
        - CameraIndex
        - CameraFPS
        - CameraWidth
        - CameraHeight
        - CameraCodex
        - MicrophoneID
        - MicrophoneIndex
        - MicrophoneRate
        - FFMPEGLocateFolder
        """

        dict_with_options ={
            'CameraID' : self.ui.CameraID.text(),
            'CameraIndex' : self.ui.CameraIndex.value(),
            'CameraFPS': self.ui.CameraFPS.text(),
            'CameraWidth': self.ui.CameraFrameWidth.text(),
            'CameraHeight': self.ui.CameraFrameHeight.text(),
            'CameraCodex' : 'copy' if self.ui.CameraCodec_Copy.isChecked() else 'libx264',
            'MicrophoneID': self.ui.MicrophoneID.text(),
            'MicrophoneIndex': self.ui.MicrophoneIndex.value(),
            'MicrophoneRate' : self.ui.MicrophoneRate.text(),
            'FFMPEGLocateFolder' : self.ui.lineEdit.text()
        }

        with open('gui_preload.yml', "w") as f:
            f.write('# pre-filled information recorded from user\n')
            yaml.dump(dict_with_options, f)

    def change_combobox_task(self):  	
        self.ui.comboBox_SubTask.clear()
        self.ui.comboBox_SubTask.addItems(self.dictwithtaskandsubtasks[self.ui.comboBox_Task.currentText()])


    def closeEvent(self, event):
        #save information from the GUI for future sessions
        self.write_yaml()

        #close camera and microphone if they are still open
        self.CameraWorker.isCapture = False
        self.CameraWorker.isRecording = False
        if self.CameraWorker.camera :
            self.CameraWorker.camera.release()
            # report_session()

        self.MicrophoneWorker.isCapture = False
        self.MicrophoneWorker.isRecording = False
        if self.MicrophoneWorker.stream:
            self.MicrophoneWorker.stream.stop_stream()
            self.MicrophoneWorker.stream.close()
        if self.MicrophoneWorker.audio :
            self.MicrophoneWorker.audio.terminate()
            # report_session()


def main():
    app = QtWidgets.QApplication(sys.argv)
    main = MainWindow()
    main.show()
    sys.exit(app.exec_())

if __name__ == '__main__':         
    main()
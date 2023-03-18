
from PyQt5.QtGui import QPalette, QColor
import sys
import threading
import pyaudio
import numpy as np
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtWidgets import *
import pyqtgraph as pg
from time import sleep
from scipy.fft import fft, fftfreq

FREQ = 440

class GraphWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Graph Window')
        self.graphWidget = pg.PlotWidget()
        self.setCentralWidget(self.graphWidget)

        self.graphWidget.setYRange(min=0, max=2000)
        # self.graphWidget.setXRange(min=10, max=20000)

    def plotData(self, data):
        adata = data[10:1000]
        # print(Freq)
        self.graphWidget.plot(y=adata, clear=True)
        print(adata.argmax())
        # print(adata.argmax())

# play_lock = QMutex()

class SoundThread(QObject):
    is_locked = pyqtSignal()

    global FREQ
    def __init__(self, frequency):
        super().__init__()
        self.frequency = frequency
        self.running = False

    @pyqtSlot()
    def run(self):
        # play_lock.lock()
        self.running = True
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paFloat32, channels=1, rate=44100, output=True)

        while self.running:
            self.frequency = FREQ
            print(FREQ)
            samples = (np.sin(2 * np.pi * np.arange(44100) * self.frequency / 44100)).astype(np.float32)
            stream.write(samples.tobytes())


        stream.stop_stream()
        stream.close()
        p.terminate()
        # play_lock.unlock()
        self.is_locked.emit()

    def update_freq(self, freq):
        self.frequency = freq
        print(freq)

    def stop(self):
        self.running = False


class SoundRecord(QThread):
    dataReady = pyqtSignal(np.ndarray)
    is_locked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.running = False

    def run(self):
        self.running = True
        RATE = 44100
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
        # print("!!!")

        while self.running:
            frames = []
            for i in range(0, int(RATE / 1024)):
                data = stream.read(1024)
                frames.append(data)
            # 将波形数据转换成数组

            wave_data = np.frombuffer(b''.join(frames), dtype=np.short)
            wave_data = wave_data / np.max(wave_data)
            # print(wave_data)
            wave_datafft = fft(wave_data)

            freq_data = np.abs(wave_datafft)
            # print(wave_datafft)
            self.dataReady.emit(freq_data)

        stream.stop_stream()
        stream.close()
        p.terminate()
        self.is_locked.emit()

    def stop(self):

        self.running = False



class MainWindow(QWidget):

    def __init__(self):
        super().__init__()
        self.initUI()
        self.frequency = 440



    def initUI(self):
        self.sound_thread = None
        self.sound_record_thread = None

        layout = QVBoxLayout()

        self.frequency_label = QLabel("Frequency: 440 Hz")
        layout.addWidget(self.frequency_label)

        self.frequency_slider = QSlider(Qt.Horizontal)
        self.frequency_slider.setMinimum(20)
        self.frequency_slider.setMaximum(20000)
        self.frequency_slider.setValue(440)
        self.frequency_slider.valueChanged.connect(self.update_frequency)
        layout.addWidget(self.frequency_slider)

        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.play_sound)
        layout.addWidget(self.play_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_sound)
        layout.addWidget(self.stop_button)

        # Add two buttons to control the sound record
        self.record_button = QPushButton("Start Recording")
        self.record_button.clicked.connect(self.start_record)
        layout.addWidget(self.record_button)

        self.stop_record_button = QPushButton("Stop Recording")
        self.stop_record_button.clicked.connect(self.stop_record)
        layout.addWidget(self.stop_record_button)

        self.plot_button = QPushButton("Start Ploting")
        self.plot_button.clicked.connect(self.openGraphWindow)
        layout.addWidget(self.plot_button)

        self.setLayout(layout)

    def update_frequency(self, value):
        global FREQ
        self.frequency_label.setText(f"Frequency: {value} Hz")
        self.frequency = value
        FREQ = value
        # self.stop_sound()
        # self.play_sound()

    def play_sound(self):
        self.play_button.setEnabled(False)
        self.sound_play = SoundThread(self.frequency)
        self.play_thread = QThread()
        self.sound_play.moveToThread(self.play_thread)
        self.play_thread.started.connect(self.sound_play.run)
        self.sound_play.is_locked.connect(self.set_play_unlocked)
        # self.sound_play.run()
        self.play_thread.start()

    def set_play_unlocked(self):
        self.play_button.setEnabled(True)

    def stop_sound(self):
        if self.sound_play:
            self.sound_play.stop()
            self.sound_play = None
            self.play_thread.quit()
            self.play_thread.wait()

    def start_record(self):
        self.record_button.setEnabled(False)
        self.sound_record_thread = SoundRecord()
        self.play_record = QThread()
        self.sound_record_thread.moveToThread(self.play_record)
        self.play_record.started.connect(self.sound_record_thread.run)
        self.sound_record_thread.dataReady.connect(self.updateGraph)
        self.sound_record_thread.is_locked.connect(self.set_record_unlocked)
        self.play_record.start()

    def stop_record(self):
        if self.sound_record_thread:
            self.sound_record_thread.stop()
            self.sound_record_thread = None
            self.play_record.quit()
            self.play_record.wait()


    def set_record_unlocked(self):
        self.record_button.setEnabled(True)

    def openGraphWindow(self):
        self.graphWindow = GraphWindow()
        self.graphWindow.show()

    def updateGraph(self, data):
        if hasattr(self, 'graphWindow'):
            self.graphWindow.plotData(data)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 设置主题颜色
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(127, 127, 127))
    palette.setColor(QPalette.Highlight, QColor(142, 45, 197))
    palette.setColor(QPalette.HighlightedText, Qt.white)
    app.setPalette(palette)

    # 创建窗口
    window = MainWindow()
    window.show()

    # 运行程序
    sys.exit(app.exec_())
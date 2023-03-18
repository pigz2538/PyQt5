
from PyQt5.QtGui import *
import sys
import threading
import pyaudio
import numpy as np
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import pyqtgraph as pg
from time import sleep
from scipy.fft import fft, fftfreq
import wave

FREQ = 440


class EnviThread(QObject):
    is_locked = pyqtSignal()

    def __init__(self, second, wav_name):
        super().__init__()
        self.running = False
        self.second = second
        self.file_name = wav_name

    @pyqtSlot()
    def run(self):
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 44100
        RECORD_SECONDS = self.second
        WAVE_OUTPUT_FILENAME = self.file_name

        p = pyaudio.PyAudio()

        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)

        frames = []

        for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            data = stream.read(CHUNK)
            frames.append(data)

        stream.stop_stream()
        stream.close()
        p.terminate()

        wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()

        self.is_locked.emit()

    def stop(self):
        self.running = False

class GraphThread(QObject):
    is_locked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.running = False

    @pyqtSlot()
    def run(self):
        self.openGraphWindow()
        self.is_locked.emit()

    def openGraphWindow(self):
        self.graphWindow = GraphWindow()
        self.graphWindow.show()

    def updateGraph(self, data):
        if hasattr(self, 'graphWindow'):
            self.graphWindow.plotData(data)

    def stop(self):
        self.running = False


class GraphWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.resize(1000, 500)
        self.setWindowTitle('频谱图')

    def initUI(self):
        self.setWindowTitle('Graph Window')
        self.graphWidget = pg.PlotWidget(useOpenGL=True, )
        self.setCentralWidget(self.graphWidget)
        # self.graphWidget.resize(2000, 500)

        self.graphWidget.setYRange(min=0, max=5000)
        # self.graphWidget.setXRange(min=10, max=20000)

    def plotData(self, data):
        adata = data[10:1000]
        # print(Freq)
        self.graphWidget.plot(y=adata, clear=True)
        self.graphWidget.showGrid(x=True, y=True)
        self.graphWidget.addLine(x=adata.argmax(), label='{}Hz'.format(adata.argmax()),
                                 labelOpts={'color': 'g', 'border': pg.mkPen(width=1, color='g')},
                                 pen=pg.mkPen(width=2, color='r'))


class SoundThread(QObject):
    is_locked = pyqtSignal()

    global FREQ

    def __init__(self, frequency):
        super().__init__()
        self.frequency = frequency
        self.running = False

    @pyqtSlot()
    def run(self):
        RATE = 44100
        # play_lock.lock()
        self.running = True
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paFloat32, channels=1, rate=RATE, output=True)

        while self.running:
            self.frequency = FREQ
            # print(FREQ)
            samples = (np.sin(2 * np.pi * np.arange(RATE) * self.frequency / RATE)).astype(np.float32)
            stream.write(samples.tobytes())

        stream.stop_stream()
        stream.close()
        p.terminate()
        # play_lock.unlock()
        self.is_locked.emit()

    def stop(self):
        self.running = False


class SoundRecord(QThread):
    dataReady = pyqtSignal(np.ndarray)
    is_locked = pyqtSignal()

    def __init__(self, wave_name, envi_flag):
        super().__init__()
        self.running = False
        self.file_name = wave_name
        self.ifenvi = envi_flag

    def run(self):
        self.running = True

        RATE = 44100
        CHUNK = 1024
        freqmin = 10
        freqmax = 2000
        second = 5

        wav_file = wave.open(self.file_name, 'rb')
        # 获取 WAV 文件的参数
        nchannels = wav_file.getnchannels()  # 声道数
        sample_width = wav_file.getsampwidth()  # 采样宽度（字节数）
        framerate = wav_file.getframerate()  # 采样率
        nframes = wav_file.getnframes()  # 采样点数

        # 读取 WAV 文件的数据
        data = wav_file.readframes(nframes)

        # 将二进制数据转换为 NumPy 数组
        data_array = np.frombuffer(data, dtype=np.short)
        data_array = data_array / np.max(data_array)
        # 对数据进行傅里叶变换
        fft_result = np.abs(fft(data_array))
        fft_result = fft_result[freqmin:freqmax]


        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=CHUNK)
        # print("!!!")

        frames = []

        while self.running:
            if len(frames) >= int(RATE / CHUNK * second):
                frames.pop(0)
            else:
                frames.append(stream.read(CHUNK))
            # 将波形数据转换成数组

            wave_data = np.frombuffer(b''.join(frames), dtype=np.short)
            wave_data = wave_data
            wave_data = wave_data / np.max(wave_data)
            # print(wave_data)
            # wave_datafft = fft(wave_data) - fft_result
            wave_datafft = fft(wave_data)
            # print(len(wave_datafft))
            freq_data = np.abs(wave_datafft)
            freq_data = freq_data[freqmin:freqmax]
            if len(freq_data) > freqmax and self.ifenvi:
                freq_data = freq_data - fft_result

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
        self.wave_name = 'Enviroment.wav'
        self.add_envi = False
        self.setWindowTitle('声音收发程序（by 纯种猪）')
        self.resize(400, 500)

    def initUI(self):
        self.freqmin = 20
        self.freqmax = 20000
        self.sound_thread = None
        self.sound_record_thread = None

        layout = QVBoxLayout()

        self.frequency_label = QLabel("Frequency: 440 Hz")
        self.frequency_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.frequency_label)

        self.freq_number = QSpinBox()
        self.freq_number.valueChanged.connect(self.update_frequency)
        self.freq_number.setMinimum(self.freqmin)
        self.freq_number.setMaximum(self.freqmax)
        self.freq_number.setValue(440)
        layout.addWidget(self.freq_number)

        self.frequency_slider = QSlider(Qt.Horizontal)
        self.frequency_slider.setMinimum(self.freqmin)
        self.frequency_slider.setMaximum(self.freqmax)
        self.frequency_slider.setValue(440)
        self.frequency_slider.valueChanged.connect(self.update_frequency)
        self.frequency_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.frequency_slider)

        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.play_sound)
        self.play_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.play_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_sound)
        self.stop_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.stop_button)

        self.envi_button = QPushButton('Enviroment Audio')
        self.envi_button.clicked.connect(self.enviroment_audio)
        self.envi_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.envi_button)

        h_layout = QHBoxLayout()

        layout.addLayout(h_layout)

        self.ifenvi_button = QRadioButton()
        self.ifenvi_label = QLabel("Erase Noise")
        self.ifenvi_button.toggled.connect(self.if_envi)
        h_layout.addWidget(self.ifenvi_button)
        h_layout.addWidget(self.ifenvi_label)
        h_layout.setSpacing(10)
        h_layout.setAlignment(Qt.AlignHCenter)

        # Add two buttons to control the sound record
        self.record_button = QPushButton("Start Recording")
        self.record_button.clicked.connect(self.start_record)
        self.record_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.record_button)

        self.stop_record_button = QPushButton("Stop Recording")
        self.stop_record_button.clicked.connect(self.stop_record)
        self.stop_record_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.stop_record_button)

        self.plot_button = QPushButton("Ploting")
        self.plot_button.clicked.connect(self.openGraphWindow)
        self.plot_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.plot_button)

        self.setLayout(layout)

    def update_frequency(self, value):
        global FREQ
        self.frequency_label.setText(f"Frequency: {value} Hz")
        self.freq_number.setValue(value)
        self.frequency_slider.setValue(value)
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

    def if_envi(self):
        self.add_envi = True

    def start_record(self):
        self.record_button.setEnabled(False)
        self.ifenvi_button.setEnabled(False)
        self.sound_record_thread = SoundRecord(self.wave_name, self.add_envi)
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
        self.ifenvi_button.setEnabled(True)

    def openGraphWindow(self):
        self.graphWindow = GraphWindow()
        self.graphWindow.show()

    def updateGraph(self, data):
        if hasattr(self, 'graphWindow'):
            self.graphWindow.plotData(data)

    def enviroment_audio(self):
        second = 5
        self.envi_button.setEnabled(False)
        self.envi_record_thread = EnviThread(second, self.wave_name)
        self.envi_record = QThread()
        self.envi_record_thread.moveToThread(self.envi_record)
        self.envi_record.started.connect(self.envi_record_thread.run)
        self.envi_record_thread.is_locked.connect(self.set_envi_unlocked)
        self.envi_record.start()

    def set_envi_unlocked(self):
        if self.envi_record_thread:
            self.envi_record_thread.stop()
            self.envi_record_thread = None
            self.envi_record.quit()
            self.envi_record.wait()
        self.envi_button.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 创建一个新的字体
    font = QFont("Comic Sans MS")
    font.setPointSize(12)

    # 设置应用程序的默认字体
    app.setFont(font)
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
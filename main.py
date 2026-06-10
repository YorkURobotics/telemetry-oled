import sys
import can
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QGridLayout)
from PySide6.QtCore import QThread, Qt, Signal, QObject, QTimer
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtGui import QColor

#this commworker handles all of the CAN communication. 
class CommWorker(QObject):
    error_status = Signal(int, int)
    telemetry_received = Signal(dict, list)

    def run(self):     
        try:
            #Masks out only communication from SPARK devices.
            target_id = (2 << 24) | (8 << 16)
            mask = 0x1FFF0000   

            filters = [{
                "can_id": target_id,
                "can_mask": mask,
                "extended": True
            }]

            bus = can.interface.Bus(
                interface='slcan',
                channel='/dev/tty.usbmodemXXXX',
                bitrate=1000000,
                filters=filters
            )
        except Exception as e:
            print(f"CAN Bus Error: {e}")
            return
        self.running = True

        while self.running:
            msg = bus.recv(timeout=0.01)
            print(msg)
            if msg is None:
                continue
            
            can_id = msg.arbitration_id
            info = {
                "dev_id": (can_id >> 0) & 0x3F, #device ID of sparkmax [gets passed to btn]
                "index":  (can_id >> 6) & 0x0F, 
                "class":  (can_id >> 10) & 0x3F,
                "manu":   (can_id >> 16) & 0xFF,
                "type":   (can_id >> 24) & 0x1F,
            }
            
            if info["class"] == 61:
                if info["index"] == 0:  #error class is 61, index 0 (from ref sheet)
                    error_code = msg.data[0]    #looks like the message sends error code (error code is mapped to LEDs in ref.)
                    self.error_status.emit(info["dev_id"], error_code) #sends values to update_led_status
            self.telemetry_received.emit(info, list(msg.data))
    def stop(self):
            self.running = False
            

LED_MAP = {
    1: ("red", "blue", "slow"),
    2: ("red", "cyan", "slow"),
    3: ("red", "green", "slow"),
    4: ("red", "magenta", "slow"),
    5: ("red", "yellow", "slow"),
    6: ("cyan", "cyan", "normal"),
    7: ("cyan", "cyan", "solid"),
    8: ("red", "cyan", "normal"),
    9: ("green", "green", "normal"),
}

class RoverDash(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sparky - Health Monitor")
        self.resize(1024, 600)
        self.setStyleSheet("background-color: #0f0f0f; color: white;")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)


        # --- LEFT SIDE: MOTOR STATUS ---
        left_column = QVBoxLayout()
        self.motor_grid = QGridLayout()
        self.motor_buttons = {}
        
        for i in range(12): #create buttons btn1 - 12
            dev_id = i + 1
            btn = QPushButton(f"axis{dev_id}")
            btn.setFixedSize(60, 60)
            # btn.setStyleSheet(self.get_style("red")) # Default to red until heartbeat
            self.motor_grid.addWidget(btn, i // 4, i % 4)
            self.motor_buttons[dev_id] = btn


        left_column.addLayout(self.motor_grid)
        main_layout.addLayout(left_column, 1)

        # --- RIGHT SIDE: GRAPHS ---
        graph_column = QVBoxLayout()
        self.chart_grid = QGridLayout()
        self.series_temp = QLineSeries()
        self.chart_temp_view = self.create_graph("Temp (Â°C)", self.series_temp)
        self.chart_grid.addWidget(self.chart_temp_view)

        self.series_current = QLineSeries()  #cv represents current - voltage
        self.series_current.setName("Current (A)")
        self.series_current.setColor(QColor("#00e5ff")) # Cyan-ish for current

        self.series_voltage = QLineSeries()
        self.series_voltage.setName("Voltage (V))")
        self.series_voltage.setColor(QColor("#dc300e")) # red-ish for voltage

        self.chart_currVol_view = self.create_graph("Current & Voltage", [self.series_voltage, self.series_current])
        self.chart_grid.addWidget(self.chart_currVol_view)  

        graph_column.addLayout(self.chart_grid)
        main_layout.addLayout(graph_column, 2)

        self.data_count = 0

        # --- WORKER THREAD ---
        self.worker = CommWorker()
        self.thread = QThread()

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)

        self.worker.error_status.connect(self.update_led_status)
        self.worker.telemetry_received.connect(self.process_can_data)

        self.button_states = {}
        self.blink_timers = {}

        self.thread.start()

        # --- LOGIC ---
        
   
    def update_led_status(self, dev_id, error_code):
            color1, color2, speed = LED_MAP.get(error_code, ("red", None, "solid"))

            btn = self.motor_buttons.get(dev_id)
            if btn is None:
                return

            if dev_id in self.blink_timers:
                self.blink_timers[dev_id].stop()
                del self.blink_timers[dev_id]

            if speed == "solid" or color2 is None:
                btn.setStyleSheet(self.get_style(color1))
                return

            intervals = {
                "normal": 250,
                "slow": 500,
            }

            interval = intervals.get(speed, 500)

            state = 1
            
            def blink():
                nonlocal state
                state = not state

                color = color1 if state else color2
                btn.setStyleSheet(self.get_style(color))

            timer = QTimer(self)
            timer.timeout.connect(blink)
            timer.start(interval)

            self.blink_timers[dev_id] = timer
            blink()

    def get_style(self, color):
        colors = {
            "red": "#ff3333",
            "green": "#00ff88",
            "blue": "#3399ff",
            "cyan": "#00e5ff",
            "magenta": "#ff33cc",
            "yellow": "#ffff33",
            "off": "#222222",
        }

        hex_color = colors.get(color, "#ff3333")

        return f"""
        QPushButton {{
                background-color: {hex_color};
                color: black;
                border-radius: 8px;
                font-weight: bold;
            }}
        """
        
        
    def create_graph(self, title, series_input):
        chart = QChart()
        chart.setTitle(title)
        chart.setTheme(QChart.ChartThemeDark)
        
        # Ensure we are working with a list even if one series is passed
        series_list = series_input if isinstance(series_input, list) else [series_input]
        
        axis_x = QValueAxis()
        axis_x.setRange(0, 100)
        chart.addAxis(axis_x, Qt.AlignBottom)

        axis_y = QValueAxis()
        axis_y.setRange(0, 100) # Adjust based on your battery/motor limits
        chart.addAxis(axis_y, Qt.AlignLeft)

        for s in series_list:
            chart.addSeries(s)
            s.attachAxis(axis_x)
            s.attachAxis(axis_y)

        view = QChartView(chart)
        view.setRenderHint(view.renderHints().Antialiasing)
        return view
    
    
    def process_can_data(self, info, data):
        #WORK IN PROGRESS
        dev_id = info['dev_id']
        idx = info['index']
        cls = info['class']

        if cls == 1:
            if idx == 3 and dev_id == 6 and len(data) >= 1: # Temperature
                val = data[0] 
                self.series_temp.append(self.data_count, val)
                self.data_count += 1
            if idx==4 and dev_id == 6 and len(data)>=1: #current Voltage
                vol=data[0]
                amp=data[1]
                self.series_current.append(self.data_count, vol)
                self.series_voltage.append(self.data_count, amp)

            #Auto-scroll & Increment X-Axis
            self.data_count += 1
            if self.data_count > 100:
                new_min, new_max = self.data_count - 100, self.data_count
                self.chart_temp_view.chart().axisX().setRange(new_min, new_max)
                self.chart_currVol_view.chart().axisX().setRange(new_min, new_max)

    def closeEvent(self, event):
        self.worker.stop()      # tell worker loop to exit
        self.thread.quit()      # stop event loop
        self.thread.wait()      # wait for thread to finish

        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RoverDash()
    window.show()
    sys.exit(app.exec())
import sys
import can
import threading
#import struct       #ONLY IF FLOATS ARE IN THE PAYLOAD
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QGridLayout)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtGui import QColor # <--- The missing piece

class CommWorker(QObject):
    telemetry_received = Signal(int, dict, list)

    def run(self):
        try:
            # Filter logic: 
            # We want Class 1 (Telemetry) and Class 63 (Heartbeat).
            # To keep it simple, we filter for Type=2, Manu=8.
            # Mask 0x1F000000 checks Type, 0x00FF0000 checks Manu.
            target_id = (2 << 24) | (8 << 16) 
            mask = 0x1FFF0000 
            
            filters = [{"can_id": target_id, "can_mask": mask, "extended": True}]
            #On mac, need to use UDP (dependency is removed from requirements.txt)
            bus = can.interface.Bus(channel='224.0.0.1', interface='udp_multicast',filter=filters)
        except Exception as e:
            print(f"CAN Bus Error: {e}")
            return

        while True:
            msg = bus.recv(timeout=1.0)
            print(msg)
            if msg:
                # Bit mapping from your whiteboard
                info = {
                    "dev_id": (msg.arbitration_id >> 0) & 0x3F,
                    "index":  (msg.arbitration_id >> 6) & 0x0F,
                    "class":  (msg.arbitration_id >> 10) & 0x3F,
                    "manu":   (msg.arbitration_id >> 16) & 0xFF,
                    "type":   (msg.arbitration_id >> 24) & 0x07, 
                }
                self.telemetry_received.emit(msg.arbitration_id, info, list(msg.data))

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
        
        for i in range(11):     #replace this with the exact dev ids once you can get them
            dev_id = i + 1
            btn = QPushButton(f"M{dev_id}")
            btn.setFixedSize(60, 60)
            btn.setStyleSheet(self.get_style("red")) # Default to red until heartbeat
            self.motor_grid.addWidget(btn, i // 4, i % 4)
            self.motor_buttons[dev_id] = btn

        btn12 = QPushButton("0x12") #e.g. button with dev id of 12
        btn12.setFixedSize(60,60)
        btn12.setStyleSheet(self.get_style("red")) # Default to red until heartbeat  
        self.motor_grid.addWidget(btn12)
        self.motor_buttons[12]=btn12
        
        left_column.addLayout(self.motor_grid)
        main_layout.addLayout(left_column, 1)

        # --- RIGHT SIDE: GRAPHS ---
        graph_column = QVBoxLayout()
        self.chart_grid = QGridLayout()
        self.series_temp = QLineSeries()
        self.chart_temp_view = self.create_graph("Temp (°C)", self.series_temp)
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
        self.worker_thread = threading.Thread(target=self.worker.run, daemon=True)
        self.worker.telemetry_received.connect(self.process_can_data)
        self.worker_thread.start()

    def get_style(self, color):
        hex_color = "#00ff88" if color == "green" else "#ff3333"
        return f"background-color: {hex_color}; color: black; border-radius: 30px; font-weight: bold; border: 1px solid white;"

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
    
    def process_can_data(self, arb_id, info, data):
        dev_id = info['dev_id']
        idx = info['index']
        cls = info['class']
        
        # 1. Update Motor Status (Heartbeat)
        if cls == 63:   #heartbeat
            if dev_id in self.motor_buttons:
                self.motor_buttons[dev_id].setStyleSheet(self.get_style("green"))
        
        # 2. Update Graphs
        if cls == 1:
            if idx == 3 and dev_id == 6 and len(data) >= 1: # Temperature
                # If data is a float, use: struct.unpack('<f', bytes(data[0:4]))[0]
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RoverDash()
    window.show()
    sys.exit(app.exec())
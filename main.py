import sys
import can
import time
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QPushButton, QGridLayout)
from PySide6.QtCore import QThread, Signal, QObject, QTimer

#this commworker handles all of the CAN communication. 
class CommWorker(QObject):
    package = Signal(int, int,str)

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
                channel='rover-test',
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

            if info["class"] == 61:     #error
                if info["index"] == 0:  #index 0 means error code is payload(from ref sheet)
                    error_code = msg.data[0]    #looks like the message sends error code (error code is mapped to LEDs in ref.)
                    self.package.emit(info["dev_id"], error_code,"Error") #sends values to update_led_status
            elif info["class"] == 1:  #telem
                if info["index"] == 4:  #volcurr
                    volp1 = msg.data[0]
                    volp2 = msg.data[1]
                    vol = (volp2<<8) | (volp1)  #MSB Little-Endian Concatenation
                    self.package.emit(info["dev_id"],vol,"Voltage")

    def stop(self):
            self.running = False
#this FakeWorker is a testing unit. see CANTesterUnit.py
class FakeWorker(QObject):
    package = Signal(int, int, str)

    def run(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.send)
        self.timer.start(1000)

        self.count = 0

    def send(self):
        self.count += 1
        self.package.emit(1, 1220 + self.count, "Voltage")
        self.package.emit(7, 1200 + self.count, "Voltage")
        self.package.emit(6, 1180 + self.count, "Voltage")
        self.package.emit(9, 1220 + self.count, "Voltage")
        error = (self.count % 9) + 1
        self.package.emit(6, 7, "Error")
        self.package.emit(8, 7, "Error")
        self.package.emit(11, 7, "Error")
        self.package.emit(4, 7, "Error")
        self.package.emit(2, 2, "Error")            #tested :)

    def stop(self):
        self.timer.stop()
#which button is where?     
button_positions = {
    0: (1, 0),
    2: (1, 1),
    3: (1, 2),
    4: (1, 3),
    5: (1, 4),

    6: (3, 0),
    7: (3, 1),
    8: (3, 2),

    9: (5, 0),
    10: (5, 1),
    11: (5, 2),
    12: (5, 3),

    13: (7, 0),
    14: (7, 1),
}
#Cartier
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
        self.setWindowTitle("YURS SPARKY 2026 telemoled")
        self.resize(1024, 600)
        self.setStyleSheet("background-color: #0f0f0f; color: white;")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        self.status_grid = QGridLayout()
        self.motor_buttons = {}
        # --- MOTOR DEFs ---
        for dev_id, position in button_positions.items():
            btn = QPushButton(f"axis{dev_id}")
            self.status_grid.addWidget(btn, *position)
            self.motor_buttons[dev_id] = btn

        main_layout.addLayout(self.status_grid)

        # --- WORKER THREAD ---
        self.worker = FakeWorker()
        self.thread = QThread()

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)

        self.worker.package.connect(self.package_received)

        self.button_states = {}
        self.blink_timers = {}
        self.voltages = {}

        self.thread.start()

        # --- LOGIC ---
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
                }} """

    def package_received(self, dev_id, value, type):
        if (type == "Error"):
                    color1, color2, speed = LED_MAP.get(value, ("red", None, "solid"))

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

    
                    
        if (type == "Voltage"):
                btn = self.motor_buttons.get(dev_id)
                self.voltages[dev_id] = value
                if btn is None:
                    return
                if dev_id <= 5:
                    btn.setText(f"axis{dev_id} DRIVE MOTOR\n{value} V")
                if 6 <= dev_id <= 8:
                    btn.setText(f"axis{dev_id} ARMS! \n{value} V")
                if 9 <= dev_id <= 12:
                    btn.setText(f"axis{dev_id} GRIPPERS ;) \n{value} V")
                if 13 <= dev_id <= 14:
                    btn.setText(f"axis{dev_id}--- SCIENCE ---! \n{value} V")

        
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
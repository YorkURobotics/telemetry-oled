import sys
import can
from PySide6.QtWidgets import (QApplication, QLabel, QMainWindow, QWidget, QVBoxLayout, 
                             QPushButton, QGridLayout)
from PySide6.QtCore import QThread, Signal, QObject, QTimer

#this commworker handles all of the CAN communication. 
class CommWorker(QObject):
    error_status = Signal(int, int)
    volcurr = Signal(int,int)

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
                    self.error_status.emit(info["dev_id"], error_code) #sends values to update_led_status
            elif info["class"] == 1:  #telem
                if info["index"] == 4:  #volcurr
                    volp1 = msg.data[0]
                    volp2 = msg.data[1]
                    vol = (volp2<<8) | (volp1)  #MSB Little-Endian Concatenation
                    self.volcurr.emit(info["dev_id"],vol)

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
        self.setWindowTitle("YURS SPARKY DigitalDash")
        self.resize(1024, 600)
        self.setStyleSheet("background-color: #0f0f0f; color: white;")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # ---  MOTOR STATUS ---
        self.motor_buttons={}
        status_grid = QGridLayout()

        #0 2 3 4 5 are DRIVE axis
        status_grid.addWidget(QLabel("Drive Motors"), 0, 0, 1, 6)

        axis0 = QPushButton(f"axis0")
        status_grid.addWidget(axis0,1,0)
        self.motor_buttons[0] = axis0

        
        axis2 = QPushButton(f"axis2")
        status_grid.addWidget(axis2,1,1)
        self.motor_buttons[2] = axis2

        axis3 = QPushButton(f"axis3")
        status_grid.addWidget(axis3,1,2)
        self.motor_buttons[3] = axis3

        axis4 = QPushButton(f"axis4")
        status_grid.addWidget(axis4,1,3)
        self.motor_buttons[4] = axis4

        axis5 = QPushButton(f"axis5")
        status_grid.addWidget(axis5,1,4)
        self.motor_buttons[5] = axis5
        
        #ARM axis' are 6 7 8

        status_grid.addWidget(QLabel("ARMs"), 2, 0, 1, 6)

        axis6 = QPushButton(f"axis6")
        status_grid.addWidget(axis6,3,0)
        self.motor_buttons[6] = axis6

        axis7 = QPushButton(f"axis7")
        status_grid.addWidget(axis7,3,1)
        self.motor_buttons[7] = axis7

        axis8 = QPushButton(f"axis8")
        status_grid.addWidget(axis8,3,2)
        self.motor_buttons[8] = axis8

        #GRIPPER 9 10 11 12
        status_grid.addWidget(QLabel("Grippers"), 4, 0, 1, 6)

        axis9 = QPushButton(f"axis9")
        status_grid.addWidget(axis9,5,0)
        self.motor_buttons[9] = axis9

        axis10 = QPushButton(f"axis10")
        status_grid.addWidget(axis10,5,1)
        self.motor_buttons[10] = axis10

        axis11 = QPushButton(f"axis11")
        status_grid.addWidget(axis11,5,2)
        self.motor_buttons[11] = axis11

        axis12 = QPushButton(f"axis12")
        status_grid.addWidget(axis12,5,3)
        self.motor_buttons[12] = axis12
        

        #SCIENCE 13 14
        status_grid.addWidget(QLabel("Science"), 6, 0, 1, 6)

        axis13 = QPushButton(f"axis13")
        status_grid.addWidget(axis13,7,0)
        self.motor_buttons[13] = axis13

        axis14 = QPushButton(f"axis14")
        status_grid.addWidget(axis14,7,1)
        self.motor_buttons[14] = axis14

        main_layout.addLayout(status_grid)

        # --- WORKER THREAD ---
        self.worker = CommWorker()
        self.thread = QThread()

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)

        self.worker.error_status.connect(self.update_led_status)
        self.worker.volcurr.connect(self.update_volcurr)

        self.button_states = {}
        self.blink_timers = {}
        self.voltages = {}

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
    
    def update_volcurr(self, dev_id, vol):
        btn = self.motor_buttons.get(dev_id)
        self.voltages[dev_id] = vol
        if btn is None:
            return
        
        btn.setText(f"axis{dev_id}\n{vol}V")

    
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
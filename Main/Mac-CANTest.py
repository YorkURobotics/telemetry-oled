import can
import time
import random
import struct

def generate_fake_can():
    # Use 'virtual' for macOS compatibility
    try:
        bus = can.interface.Bus(channel='224.0.0.1', interface='udp_multicast')
    except:
        # If vcan0 isn't defined in your configs, this usually just works
        bus = can.interface.Bus(channel='224.0.0.1', interface='udp_multicast')

    print("Bus started. Sending fake Rover telemetry...")

    # Constants from your whiteboard
    TYPE = 2
    MANU = 8
    DEV_ID = 6 # Targeting Motor 6 as per your UI code
    
    count = 0
    while True:
        # 1. Generate Heartbeat (Class 63, Index 0)
        # ID Construction: (Type << 24) | (Manu << 16) | (Class << 10) | (Index << 6) | DevID
        heartbeat_id = (TYPE << 24) | (MANU << 16) | (63 << 10) | (0 << 6) | DEV_ID
        msg_hb = can.Message(arbitration_id=heartbeat_id, data=[1], is_extended_id=True)
        bus.send(msg_hb)
        #print(msg_hb)

        #another heartbeat
        heartbeat_id = (TYPE << 24) | (MANU << 16) | (63 << 10) | (0 << 6) | 9
        msg_hb = can.Message(arbitration_id=heartbeat_id, data=[1], is_extended_id=True)
        bus.send(msg_hb)
        # 2. Generate Temp (Class 1, Index 3)
        temp_id = (TYPE << 24) | (MANU << 16) | (1 << 10) | (3 << 6) | DEV_ID
        fake_temp = int(40 + 10 * random.random()) # 40-50 degrees
        msg_temp = can.Message(arbitration_id=temp_id, data=[fake_temp], is_extended_id=True)
        bus.send(msg_temp)

        # 3. Generate Volt/Curr (Class 1, Index 4)
        power_id = (TYPE << 24) | (MANU << 16) | (1 << 10) | (4 << 6) | DEV_ID
        fake_volt = int(20 + random.random() * 4) # 20-24V
        fake_curr = int(random.random() * 50)    # 0-50A
        msg_power = can.Message(arbitration_id=power_id, data=[fake_volt, fake_curr], is_extended_id=True)
        bus.send(msg_power)

        time.sleep(0.1) # Send at 10Hz

if __name__ == "__main__":
    generate_fake_can()
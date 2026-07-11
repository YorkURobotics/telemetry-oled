import time
import can


def build_can_id(dev_id, msg_class, index, manufacturer=8, device_type=2):
    return (
        (device_type << 24)
        | (manufacturer << 16)
        | (msg_class << 10)
        | (index << 6)
        | dev_id
    )


bus = can.interface.Bus(
    interface="slcan",
    channel="rover-test",
    bitrate=1_000_000,
)

try:
    while True:
        # Send voltage telemetry to every configured motor
        for dev_id in [0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]:
            voltage = 1200 + dev_id

            voltage_msg = can.Message(
                arbitration_id=build_can_id(
                    dev_id=dev_id,
                    msg_class=1,
                    index=4,
                ),
                data=[
                    voltage & 0xFF,
                    (voltage >> 8) & 0xFF,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                ],
                is_extended_id=True,
            )

            bus.send(voltage_msg)

        # Send a different LED/error state to axis 6
        error_msg = can.Message(
            arbitration_id=build_can_id(
                dev_id=6,
                msg_class=61,
                index=0,
            ),
            data=[3, 0, 0, 0, 0, 0, 0, 0],
            is_extended_id=True,
        )

        bus.send(error_msg)

        print("Sent test telemetry and error frames")
        time.sleep(1)

except KeyboardInterrupt:
    print("Stopping CAN test sender")

finally:
    bus.shutdown()

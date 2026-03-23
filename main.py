import dearpygui.dearpygui as dpg
import can
import threading
import queue


dpg.create_context()
bwid = 50

# --- THEMES ---
with dpg.theme() as green_led:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_Button, (34, 139, 34, 255))
        dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 50)

with dpg.theme() as red_led:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_Button, (200, 0, 0, 255))
        dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 50)

# --- UI LAYOUT ---
with dpg.window(label="Telemetry Master", tag="Primary Window"):
    with dpg.group(horizontal=True):
        with dpg.group(width=250):
            with dpg.child_window(height=400, border=True):
                dpg.add_text("Spark Maxes", color=(255, 255, 255))
                dpg.add_separator()
            
                with dpg.table(header_row=False, borders_innerH=False, borders_innerV=False):
                    for i in range(4): dpg.add_table_column()

                    # DRIVE Section
                    with dpg.table_row(): dpg.add_text("DRIVE", color=(0, 255, 255))
                    with dpg.table_row():
                        # We give these specific tags so we can find them later
                        for i in range(1, 5):
                            tag_id = f"btn_sp{i}"       #REPLACE THIS FOR LOOP WITH EXACT CAN ID VALUES LATER
                            dpg.add_button(label=f"SP{i}", width=bwid, height=bwid, tag=tag_id)
                            dpg.bind_item_theme(tag_id, green_led)

                    # ARM Section
                    with dpg.table_row(): dpg.add_text("ARM", color=(0, 255, 255))
                    with dpg.table_row():
                        for i in range(5, 8):       #REPLACE THIS FOR LOOP WITH EXACT CAN ID VALUES LATER
                            tag_id = f"btn_sp{i}"
                            dpg.add_button(label=f"SP{i}", width=bwid, height=bwid, tag=tag_id)
                            dpg.bind_item_theme(tag_id, green_led)

                    #GRIP Section
                    with dpg.table_row(): dpg.add_text("GRIP", color=(0, 255, 255))
                    with dpg.table_row():
                        for i in range(9, 11):       #REPLACE THIS FOR LOOP WITH EXACT CAN ID VALUES LATER
                            tag_id = f"btn_sp{i}"
                            dpg.add_button(label=f"SP{i}", width=bwid, height=bwid, tag=tag_id)
                            dpg.bind_item_theme(tag_id, green_led)

                    #SCIENCE SECTION
                    with dpg.table_row(): dpg.add_text("DRIVE", color=(0, 255, 255))
                    with dpg.table_row():
                            #REPLACE THIS ID WITH EXACT CAN ID VALUES LATER
                            tag_id="btn_sp19"
                            dpg.add_button(label="btn_sp19", width=bwid, height=bwid, tag=tag_id)
                            dpg.bind_item_theme(tag_id, green_led)

            with dpg.child_window(height=-1, border=True):
                dpg.add_text("Science Module", color=(255, 255, 255))
                dpg.add_separator()

        with dpg.child_window(width=-1, border=True):
            dpg.add_text("EBOX DATA", color=(0, 255, 255))
            dpg.add_separator()

# --- CAN Bit Extractor ---
def extract_bits (bit, sbit_loc, bit_mask):

    return (bit >> sbit_loc) & bit_mask

# --- THE LOGIC ---

#FROM C Header, pass this to return as needed
'''
    BITS 29 - 24 is type
    '' 16 - 23 is manufacturer
    '' 10-15 is class
    '' 6 - 9 is index
    and 0 - 5 is device id
'''
TYPE_POS = 24
MANU_POS = 16
CLASS_POS = 10
INDEX_POS = 6
DEVID_POS = 0

def get_telemetry_info(arb_id):
    return {
        "type": (arb_id >> TYPE_POS) & 0x1F,    #5 bits
        "manu": (arb_id >> MANU_POS) & 0xFF,    #8 bits
        "class": (arb_id >> CLASS_POS) & 0x3F,  #6 bits
        "index": (arb_id >> INDEX_POS) & 0x0F,  #4 bits
        "dev_id": (arb_id >> DEVID_POS) & 0x3F  #6 bits
    }

#_ _ _ _ _ | _ _ _ _ _ _ _ | _ _ _ _ _ _ | _ _ _ _ | _ _ _ _ _ _ |
#type           Menu           Class        Index   Device ID

#1. Create a queue
    
telemetry_queue = queue.Queue()

def can_worker():

    try: 
        # Constants from  C header - change when DBC is implemented
        '''

        
         Creates a filter that ONLY lets through "Status 1" (where faults live)
         This ignores the "Heartbeat" and "Encoder" data entirely at the hardware level.
    
         This ID represents: Type(02) + Mfr(05) + API(061) + DeviceID(00)
         Binary:             0000 0010 + 0000 0101 + 0011 1101 + 0000 0000
        HEX:                   0   2     0      5      3   D       0   0x
        '''
        target_id = 0x02053D00


        #from CAN, we only want
        filters = [
            {
                "can_id": target_id, 
                "can_mask": 0x1FFFFFC0, # Check Type/Mfr/API, ignore Device ID
                "extended": True}
            ]
        
        bus = can.interface.Bus(channel='can0', bustype='socketcan', can_filters=filters)
    except:
        print("BUS NOT FOUND! (did you run sudo ip link...)?")
        bus = None
    while True:
        # This BLOCKS. It stays here until a message arrives, instead of always polling
        msg = bus.recv(timeout=1.0) 
        if msg:
            info = get_telemetry_info(msg.arbitration_id)
                #TELEMETRY:
            if msg.arbitration_id == 0x02080546:    #iD for Voltage / Current 
                    print (f"VolCurr = {msg.data} from device {info["dev_id"]}")
            if info["type"]== 2:
                if info["manu"] == 8:
                    #for all sparkmaxes, 0x0208 or above
                    if info["index"] == 3:  #temperature, for example
                        print(f"TEMP: {msg.arbitration_id} from device {info["dev_id"]}")
                    
                #telemetry_queue.put((device_id, data)) # - gets passed into update_telemetry_ui
                

    # 2. Start the thread before the UI loop
thread = threading.Thread(target=can_worker, daemon=True)
thread.start()

# 3. Update the UI function to just check the Queue
def update_telemetry_ui():
    # Process everything currently in the queue
    while not telemetry_queue.empty():
        try:
            device_id, data = telemetry_queue.get_nowait()
            target_tag = f"btn_sp{device_id}"       #Going to have to change all the button values to the individual device IDs.
            
            if dpg.does_item_exist(target_tag):
                if data > 0:        #Data only passed if there is an issue
                    dpg.bind_item_theme(target_tag, red_led)
                    dpg.configure_item(target_tag, label=f"ID:{device_id}\nERR")
                else:
                    dpg.bind_item_theme(target_tag, green_led)
                    dpg.configure_item(target_tag, label=f"SP{device_id}")
        except queue.Empty:
            break


    

# --- RENDER LOOP ---
dpg.create_viewport(title='YURS Telemetry', width=1200, height=800)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("Primary Window", True)

# Manual Render Loop (Crucial for live telemetry)
while dpg.is_dearpygui_running():
    update_telemetry_ui
    dpg.render_dearpygui_frame()

dpg.destroy_context()
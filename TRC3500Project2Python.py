import serial
import serial.tools.list_ports
import json
import sys
import os

# --- CONFIGURATION ---
BAUD_RATE = 230400 
CALIBRATION_FILE = "calibration_profiles.json"

CLASS_NAMES = [
    "10cm Dist, 30cm Height",
    "10cm Dist, 10cm Height",
    "30cm Dist, 30cm Height",
    "30cm Dist, 10cm Height"
]

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def auto_detect_com_port():
    print("--- Auto-Detecting STM32 ---")
    devices = serial.tools.list_ports.comports()
    
    for device in devices:
        device_split = str(device).split()
        if len(device_split) > 2 and (device_split[2] == "STMicroelectronics" or "STLink" in str(device)):
            STM32_serial_port = device_split[0]
            print(f"[+] STM Detected on port: {STM32_serial_port}")
            return STM32_serial_port
            
    print("[-] Error: Could not automatically detect an STM32.")
    print("[-] Please check your USB connection and ST-Link drivers.")
    sys.exit(1)

def main():
    clear_screen()
    com_port = auto_detect_com_port()
    
    try:
        ser = serial.Serial(com_port, BAUD_RATE, timeout=1)
        print(f"[+] Successfully opened {com_port} at {BAUD_RATE} baud.")
    except Exception as e:
        print(f"[-] Failed to open {com_port}: {e}")
        sys.exit(1)

    print("\nWaiting for STM32 to boot and Auto-Zero...")
    
    while True:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if "STM32_READY" in line:
            parts = line.split('|')
            print(f"[+] {parts[0]}! (Measured {parts[1]})\n")
            break

    while True:
        print("\n=== ACOUSTIC DSP TEST RIG ===")
        print("[1] Start New Calibration (Learn 4 Scenarios)")
        print("[2] Load Existing Calibration from File (START TESTING)")
        print("[3] Exit Program")
        
        choice = input("\nEnter choice (1, 2, or 3): ").strip()
        
        if choice == '1':
            print("\n>>> INITIATING CALIBRATION MODE <<<")
            ser.write(b"CMD:CALIBRATE\n")
            
            current_stage = 0
            print(f"\n[ACTION REQUIRED] Please drop the coin 3 times for: {CLASS_NAMES[current_stage]}")
            
            while True:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if not line: continue
                
                if line.startswith("CAL_DROP"):
                    parts = line.split('|')
                    drop_num = parts[0].split(':')[1]
                    energy = parts[1].split(':')[1]
                    print(f"  -> Drop {drop_num}/3 recorded (Energy: {energy})")
                    print("     [!] Cooling down 3s... wait for READY.")
                    
                elif line == "READY_FOR_NEXT":
                    print("  >>> READY: Drop the next coin! <<<")

                elif line.startswith("CAL_STAGE_DONE"):
                    parts = line.split('|')
                    centroid = parts[1].split(':')[1]
                    print(f"[+] Profile Locked! Centroid Energy: {centroid}")
                    
                    current_stage += 1
                    if current_stage < 4:
                        print(f"\n[ACTION REQUIRED] Please drop the coin 3 times for: {CLASS_NAMES[current_stage]}")
                        
                elif line.startswith("CAL_COMPLETE"):
                    data = line.split(':')[1]
                    profiles = data.split(',')
                    save_data = {f"class_{i}": profiles[i] for i in range(4)}
                    with open(CALIBRATION_FILE, 'w') as f:
                        json.dump(save_data, f, indent=4)
                    print(f"\n[+] Calibration saved to {CALIBRATION_FILE}")
                    print("[+] Returning to Main Menu...\n")
                    break
            continue 
                    
        elif choice == '2':
            try:
                with open(CALIBRATION_FILE, 'r') as f:
                    data = json.load(f)
                
                cmd = f"CMD:LOAD,{data['class_0']},{data['class_1']},{data['class_2']},{data['class_3']}\n"
                ser.write(cmd.encode('utf-8'))
                
                while True:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line == "ACK:LOADED_AND_TESTING":
                        print("=== SYSTEM IS NOW IN LIVE TEST MODE ===\n")
                        break
            except FileNotFoundError:
                print(f"[-] Error: {CALIBRATION_FILE} not found. Please calibrate first.")
                continue

        elif choice == '3':
            print("\nExiting program... Goodbye!")
            ser.close()
            sys.exit(0)
        else:
            continue

        # --- LIVE TEST MODE LOOP ---
        print("Waiting for drops... (Press Ctrl+C to stop testing)\n")
        try:
            while True:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if not line: continue
                
                if line.startswith("TEST_RESULT"):
                    parts = line.split('|')
                    energy = parts[1].split(':')[1]
                    class_idx = int(parts[2].split(':')[1])
                    
                    print("-" * 50)
                    print(f"DROP DETECTED!")
                    print(f"Calculated Energy : {energy}")
                    print(f"Predicted Class   : >> {CLASS_NAMES[class_idx]} <<")
                    print("-" * 50)
                    print("[!] Cooling down 5s... wait for READY.")
                
                elif line == "READY_FOR_NEXT":
                    print(">>> READY: Drop the next coin! <<<\n")
                    
        except KeyboardInterrupt:
            print("\n\n[!] Interrupt caught. Resetting STM32...")
            ser.write(b"CMD:INITIAL\n")
            while True:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line == "ACK:INITIAL":
                    break
            continue

if __name__ == "__main__":
    main()